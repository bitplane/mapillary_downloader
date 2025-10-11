"""Main downloader logic."""

import json
import os
from pathlib import Path


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

        print(f"Downloading images for user: {username}")
        print(f"Output directory: {self.output_dir}")
        print(f"Quality: {quality}")

        total = 0
        skipped = 0

        with open(self.metadata_file, "a") as meta_f:
            for image in self.client.get_user_images(username, bbox=bbox):
                image_id = image["id"]
                total += 1

                if image_id in self.downloaded:
                    skipped += 1
                    continue

                # Save metadata
                meta_f.write(json.dumps(image) + "\n")
                meta_f.flush()

                # Download image
                image_url = image.get(quality_field)
                if not image_url:
                    print(f"No {quality} URL for image {image_id}")
                    continue

                # Use sequence ID for organization
                sequence_id = image.get("sequence")
                if sequence_id:
                    img_dir = self.output_dir / sequence_id
                    img_dir.mkdir(exist_ok=True)
                else:
                    img_dir = self.output_dir

                output_path = img_dir / f"{image_id}.jpg"

                if self.client.download_image(image_url, output_path):
                    self.downloaded.add(image_id)
                    print(f"Downloaded {total}: {image_id}")

                    # Save progress every 10 images
                    if len(self.downloaded) % 10 == 0:
                        self._save_progress()

        self._save_progress()
        print(f"\nComplete! Downloaded {len(self.downloaded)} images (skipped {skipped} existing)")
