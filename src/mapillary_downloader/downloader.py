"""Main downloader logic."""

import json
import logging
import os
import time
from pathlib import Path
from collections import deque
from mapillary_downloader.exif_writer import write_exif_to_image
from mapillary_downloader.utils import format_size, format_time

logger = logging.getLogger("mapillary_downloader")


class MapillaryDownloader:
    """Handles downloading Mapillary data for a user."""

    def __init__(self, client, output_dir):
        """Initialize the downloader.

        Args:
            client: MapillaryClient instance
            output_dir: Directory to save downloads
        """
        self.client = client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.output_dir / "metadata.jsonl"
        self.progress_file = self.output_dir / "progress.json"
        self.downloaded = self._load_progress()

    def _load_progress(self):
        """Load previously downloaded image IDs."""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                return set(json.load(f).get("downloaded", []))
        return set()

    def _save_progress(self):
        """Save progress to disk atomically."""
        temp_file = self.progress_file.with_suffix(".json.tmp")
        with open(temp_file, "w") as f:
            json.dump({"downloaded": list(self.downloaded)}, f)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(self.progress_file)

    def download_user_data(self, username, quality="original", bbox=None):
        """Download all images for a user.

        Args:
            username: Mapillary username
            quality: Image quality to download (256, 1024, 2048, original)
            bbox: Optional bounding box [west, south, east, north]
        """
        quality_field = f"thumb_{quality}_url"

        logger.info(f"Downloading images for user: {username}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Quality: {quality}")

        processed = 0
        downloaded_count = 0
        skipped = 0
        total_bytes = 0

        # Track download times for adaptive ETA (last 50 downloads)
        download_times = deque(maxlen=50)
        start_time = time.time()

        # Track which image IDs we've seen in metadata to avoid re-fetching
        seen_ids = set()

        # First, process any existing metadata without re-fetching from API
        if self.metadata_file.exists():
            logger.info("Processing existing metadata file...")
            with open(self.metadata_file) as f:
                for line in f:
                    if line.strip():
                        image = json.loads(line)
                        image_id = image["id"]
                        seen_ids.add(image_id)
                        processed += 1

                        if image_id in self.downloaded:
                            skipped += 1
                            continue

                        # Download this un-downloaded image
                        image_url = image.get(quality_field)
                        if not image_url:
                            logger.warning(f"No {quality} URL for image {image_id}")
                            continue

                        sequence_id = image.get("sequence")
                        if sequence_id:
                            img_dir = self.output_dir / sequence_id
                            img_dir.mkdir(exist_ok=True)
                        else:
                            img_dir = self.output_dir

                        output_path = img_dir / f"{image_id}.jpg"

                        download_start = time.time()
                        bytes_downloaded = self.client.download_image(image_url, output_path)
                        if bytes_downloaded:
                            download_time = time.time() - download_start
                            download_times.append(download_time)

                            write_exif_to_image(output_path, image)

                            self.downloaded.add(image_id)
                            downloaded_count += 1
                            total_bytes += bytes_downloaded

                            progress_str = (
                                f"Processed: {processed}, Downloaded: {downloaded_count} ({format_size(total_bytes)})"
                            )
                            logger.info(progress_str)

                            if downloaded_count % 10 == 0:
                                self._save_progress()

        # Always check API for new images (will skip duplicates via seen_ids)
        logger.info("Checking for new images from API...")
        with open(self.metadata_file, "a") as meta_f:
            for image in self.client.get_user_images(username, bbox=bbox):
                image_id = image["id"]

                # Skip if we already have this in our metadata file
                if image_id in seen_ids:
                    continue

                seen_ids.add(image_id)
                processed += 1

                # Save new metadata
                meta_f.write(json.dumps(image) + "\n")
                meta_f.flush()

                # Skip if already downloaded
                if image_id in self.downloaded:
                    skipped += 1
                    continue

                # Download image
                image_url = image.get(quality_field)
                if not image_url:
                    logger.warning(f"No {quality} URL for image {image_id}")
                    continue

                # Use sequence ID for organization
                sequence_id = image.get("sequence")
                if sequence_id:
                    img_dir = self.output_dir / sequence_id
                    img_dir.mkdir(exist_ok=True)
                else:
                    img_dir = self.output_dir

                output_path = img_dir / f"{image_id}.jpg"

                download_start = time.time()
                bytes_downloaded = self.client.download_image(image_url, output_path)
                if bytes_downloaded:
                    download_time = time.time() - download_start
                    download_times.append(download_time)

                    # Write EXIF metadata to the downloaded image
                    write_exif_to_image(output_path, image)

                    self.downloaded.add(image_id)
                    downloaded_count += 1
                    total_bytes += bytes_downloaded

                    # Calculate progress
                    progress_str = (
                        f"Processed: {processed}, Downloaded: {downloaded_count} ({format_size(total_bytes)})"
                    )

                    logger.info(progress_str)

                    # Save progress every 10 images
                    if downloaded_count % 10 == 0:
                        self._save_progress()

        self._save_progress()
        elapsed = time.time() - start_time
        logger.info(
            f"Complete! Processed {processed} images, downloaded {downloaded_count} ({format_size(total_bytes)}), skipped {skipped}"
        )
        logger.info(f"Total time: {format_time(elapsed)}")
