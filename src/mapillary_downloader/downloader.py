"""Main downloader logic."""

import gzip
import json
import logging
import os
import shutil
import time
from pathlib import Path
from mapillary_downloader.utils import format_size, format_time
from mapillary_downloader.ia_meta import generate_ia_metadata
from mapillary_downloader.ia_check import check_ia_exists
from mapillary_downloader.worker import worker_process
from mapillary_downloader.worker_pool import AdaptiveWorkerPool
from mapillary_downloader.metadata_reader import MetadataReader
from mapillary_downloader.tar_sequences import tar_sequence_directories
from mapillary_downloader.logging_config import add_file_handler

logger = logging.getLogger("mapillary_downloader")


def get_cache_dir():
    """Get XDG cache directory for staging downloads.

    Returns:
        Path to cache directory for mapillary_downloader
    """
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        cache_dir = Path(xdg_cache)
    else:
        cache_dir = Path.home() / ".cache"

    mapillary_cache = cache_dir / "mapillary_downloader"
    mapillary_cache.mkdir(parents=True, exist_ok=True)
    return mapillary_cache


class MapillaryDownloader:
    """Handles downloading Mapillary data for a user."""

    def __init__(
        self,
        client,
        output_dir,
        username=None,
        quality=None,
        workers=None,
        tar_sequences=True,
        convert_webp=False,
        check_ia=True,
    ):
        """Initialize the downloader.

        Args:
            client: MapillaryClient instance
            output_dir: Base directory to save downloads (final destination)
            username: Mapillary username (for collection directory)
            quality: Image quality (for collection directory)
            workers: Number of parallel workers (default: half of cpu_count)
            tar_sequences: Whether to tar sequence directories after download (default: True)
            convert_webp: Whether to convert images to WebP (affects collection name)
            check_ia: Whether to check if collection exists on Internet Archive (default: True)
        """
        self.client = client
        self.base_output_dir = Path(output_dir)
        self.username = username
        self.quality = quality
        self.workers = workers if workers is not None else max(1, os.cpu_count() // 2)
        self.tar_sequences = tar_sequences
        self.convert_webp = convert_webp
        self.check_ia = check_ia

        # Determine collection name
        if username and quality:
            collection_name = f"mapillary-{username}-{quality}"
            if convert_webp:
                collection_name += "-webp"
            self.collection_name = collection_name
        else:
            self.collection_name = None

        # Set up staging directory in cache
        cache_dir = get_cache_dir()
        if self.collection_name:
            self.staging_dir = cache_dir / self.collection_name
            self.final_dir = self.base_output_dir / self.collection_name
        else:
            self.staging_dir = cache_dir / "download"
            self.final_dir = self.base_output_dir

        # Work in staging directory during download
        self.output_dir = self.staging_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Staging directory: {self.staging_dir}")
        logger.info(f"Final destination: {self.final_dir}")

        # Set up file logging for archival with timestamp for incremental runs
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_file = self.output_dir / f"download.log.{timestamp}"
        add_file_handler(log_file)
        logger.info(f"Logging to: {log_file}")

        self.metadata_file = self.output_dir / "metadata.jsonl"
        self.progress_file = self.output_dir / "progress.json"
        self.downloaded = self._load_progress()

    def _load_progress(self):
        """Load previously downloaded image IDs for this quality."""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                data = json.load(f)
                # Support both old format (single list) and new format (per-quality dict)
                if isinstance(data, dict):
                    if "downloaded" in data:
                        # Old format: {"downloaded": [...]}
                        return set(data["downloaded"])
                    else:
                        # New format: {"256": [...], "1024": [...], ...}
                        return set(data.get(str(self.quality), []))
                else:
                    # Very old format: just a list
                    return set(data)
        return set()

    def _save_progress(self):
        """Save progress to disk atomically, per-quality."""
        # Load existing progress for all qualities
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                data = json.load(f)
                # Convert old format to new format if needed
                if isinstance(data, dict) and "downloaded" in data:
                    # Old format: {"downloaded": [...]} - migrate to per-quality
                    progress = {}
                else:
                    progress = data if isinstance(data, dict) else {}
        else:
            progress = {}

        # Update this quality's progress
        progress[str(self.quality)] = list(self.downloaded)

        # Write atomically
        temp_file = self.progress_file.with_suffix(".json.tmp")
        with open(temp_file, "w") as f:
            json.dump(progress, f)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(self.progress_file)

    def download_user_data(self, bbox=None, convert_webp=False):
        """Download all images for a user using streaming queue-based architecture.

        Args:
            bbox: Optional bounding box [west, south, east, north]
            convert_webp: Convert images to WebP format after download
        """
        if not self.username or not self.quality:
            raise ValueError("Username and quality must be provided during initialization")

        # Check if collection already exists on Internet Archive
        if self.check_ia and self.collection_name:
            logger.info(f"Checking if {self.collection_name} exists on Internet Archive...")
            if check_ia_exists(self.collection_name):
                logger.info("Collection already exists on archive.org, skipping download")
                return

        # Check if collection already exists in final destination
        if self.final_dir.exists():
            logger.info(f"Collection already exists at {self.final_dir}, skipping download")
            return

        quality_field = f"thumb_{self.quality}_url"

        logger.info(f"Downloading images for user: {self.username}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Quality: {self.quality}")
        logger.info(f"Using {self.workers} parallel workers")

        start_time = time.time()

        # Step 1: Check if API fetch is already complete
        reader = MetadataReader(self.metadata_file)
        api_complete = reader.is_complete
        if api_complete:
            logger.info("API fetch already complete, will only download")
        else:
            logger.info("API fetch incomplete, will fetch and download in parallel")

        # Step 2: Start worker pool
        # Since workers do both I/O (download) and CPU (WebP), need many more workers
        # Cap at 128 for now - will build proper dynamic scaling on a new branch later
        pool = AdaptiveWorkerPool(worker_process, min_workers=self.workers, max_workers=128, monitoring_interval=10)
        pool.start()

        # Step 3: Download images from metadata file while fetching new from API
        downloaded_count = 0
        total_bytes = 0
        failed_count = 0
        submitted = 0
        batch_start = time.time()

        logger.info("Starting parallel download and API fetch...")

        try:
            # Step 3a: Fetch metadata from API in parallel (write-only, don't block on queue)
            if not api_complete:
                import threading

                api_fetch_complete = threading.Event()
                new_images_count = [0]  # Mutable so thread can update it

                def fetch_api_metadata():
                    """Fetch metadata from API and write to file (runs in thread)."""
                    try:
                        logger.info("API fetch thread: Starting...")
                        with open(self.metadata_file, "a") as meta_f:
                            for image in self.client.get_user_images(self.username, bbox=bbox):
                                new_images_count[0] += 1

                                # Save metadata (don't dedupe here, let the tailer handle it)
                                meta_f.write(json.dumps(image) + "\n")
                                meta_f.flush()

                                if new_images_count[0] % 1000 == 0:
                                    logger.info(f"API: Fetched {new_images_count[0]} images from API")

                            # Mark as complete
                            MetadataReader.mark_complete(self.metadata_file)
                            logger.info(f"API fetch complete: {new_images_count[0]} images")
                    finally:
                        api_fetch_complete.set()

                # Start API fetch in background thread
                api_thread = threading.Thread(target=fetch_api_metadata, daemon=True)
                api_thread.start()
            else:
                logger.info("API fetch already complete, skipping API thread")
                api_fetch_complete = None

            # Step 3b: Tail metadata file and submit to workers
            logger.info("Starting metadata tail and download queue feeder...")
            last_position = 0

            # Helper to process results from queue
            def process_results():
                nonlocal downloaded_count, total_bytes, failed_count
                while True:
                    result = pool.get_result(timeout=0.001)
                    if result is None:
                        break

                    image_id, bytes_dl, success, error_msg = result

                    if success:
                        self.downloaded.add(image_id)
                        downloaded_count += 1
                        total_bytes += bytes_dl

                        # Log every download for first 10, then every 100
                        should_log = downloaded_count <= 10 or downloaded_count % 100 == 0
                        if should_log:
                            elapsed = time.time() - batch_start
                            rate = downloaded_count / elapsed if elapsed > 0 else 0
                            logger.info(
                                f"Downloaded: {downloaded_count} ({format_size(total_bytes)}) "
                                f"- Rate: {rate:.1f} images/sec"
                            )

                        if downloaded_count % 100 == 0:
                            self._save_progress()
                            pool.check_throughput(downloaded_count)
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to download {image_id}: {error_msg}")

            # Tail the metadata file and submit to workers
            while True:
                # Check if API fetch is done and we've processed everything
                if api_fetch_complete and api_fetch_complete.is_set():
                    # Read any remaining lines
                    if self.metadata_file.exists():
                        with open(self.metadata_file) as f:
                            f.seek(last_position)
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue

                                try:
                                    image = json.loads(line)
                                except json.JSONDecodeError:
                                    # Incomplete line, will retry
                                    continue

                                # Skip completion marker
                                if image.get("__complete__"):
                                    continue

                                image_id = image.get("id")
                                if not image_id:
                                    continue

                                # Skip if already downloaded or no quality URL
                                if image_id in self.downloaded:
                                    continue
                                if not image.get(quality_field):
                                    continue

                                # Submit to workers
                                work_item = (
                                    image,
                                    str(self.output_dir),
                                    self.quality,
                                    convert_webp,
                                    self.client.access_token,
                                )
                                pool.submit(work_item)
                                submitted += 1

                                if submitted % 1000 == 0:
                                    logger.info(f"Queue: Submitted {submitted} images")

                                # Process results while submitting
                                process_results()

                            last_position = f.tell()

                    # API done and all lines processed, break
                    break

                # API still running or API was already complete, tail the file
                if self.metadata_file.exists():
                    with open(self.metadata_file) as f:
                        f.seek(last_position)
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue

                            try:
                                image = json.loads(line)
                            except json.JSONDecodeError:
                                # Incomplete line, will retry next iteration
                                continue

                            # Skip completion marker
                            if image.get("__complete__"):
                                continue

                            image_id = image.get("id")
                            if not image_id:
                                continue

                            # Skip if already downloaded or no quality URL
                            if image_id in self.downloaded:
                                continue
                            if not image.get(quality_field):
                                continue

                            # Submit to workers
                            work_item = (
                                image,
                                str(self.output_dir),
                                self.quality,
                                convert_webp,
                                self.client.access_token,
                            )
                            pool.submit(work_item)
                            submitted += 1

                            if submitted % 1000 == 0:
                                logger.info(f"Queue: Submitted {submitted} images")

                            # Process results while submitting
                            process_results()

                        last_position = f.tell()

                # Sleep briefly before next tail iteration
                time.sleep(0.1)

                # Process any results that came in
                process_results()

            # Send shutdown signals
            logger.info(f"Submitted {submitted} images, waiting for workers to finish...")
            for _ in range(pool.current_workers):
                pool.submit(None)

            # Collect remaining results
            completed = downloaded_count + failed_count

            while completed < submitted:
                result = pool.get_result(timeout=5)
                if result is None:
                    # Check throughput periodically
                    pool.check_throughput(downloaded_count)
                    continue

                image_id, bytes_dl, success, error_msg = result
                completed += 1

                if success:
                    self.downloaded.add(image_id)
                    downloaded_count += 1
                    total_bytes += bytes_dl

                    if downloaded_count % 10 == 0:
                        elapsed = time.time() - batch_start
                        rate = downloaded_count / elapsed if elapsed > 0 else 0
                        remaining = submitted - completed
                        eta_seconds = remaining / rate if rate > 0 else 0

                        logger.info(
                            f"Downloaded: {downloaded_count}/{submitted} ({format_size(total_bytes)}) "
                            f"- ETA: {format_time(eta_seconds)}"
                        )
                        self._save_progress()
                        pool.check_throughput(downloaded_count)
                else:
                    failed_count += 1
                    logger.warning(f"Failed to download {image_id}: {error_msg}")

        finally:
            # Shutdown worker pool
            pool.shutdown()

        self._save_progress()
        elapsed = time.time() - start_time

        logger.info(f"Complete! Downloaded {downloaded_count} ({format_size(total_bytes)}), " f"failed {failed_count}")
        logger.info(f"Total time: {format_time(elapsed)}")

        # Tar sequence directories for efficient IA uploads
        if self.tar_sequences:
            tar_sequence_directories(self.output_dir)

        # Gzip metadata.jsonl to save space
        if self.metadata_file.exists():
            logger.info("Compressing metadata.jsonl...")
            original_size = self.metadata_file.stat().st_size
            gzipped_file = self.metadata_file.with_suffix(".jsonl.gz")

            with open(self.metadata_file, "rb") as f_in:
                with gzip.open(gzipped_file, "wb", compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)

            compressed_size = gzipped_file.stat().st_size
            self.metadata_file.unlink()

            savings = 100 * (1 - compressed_size / original_size)
            logger.info(
                f"Compressed metadata: {format_size(original_size)} → {format_size(compressed_size)} "
                f"({savings:.1f}% savings)"
            )

        # Generate IA metadata
        generate_ia_metadata(self.output_dir)

        # Move from staging to final destination
        logger.info("Moving collection from staging to final destination...")
        if self.final_dir.exists():
            logger.warning(f"Destination already exists, removing: {self.final_dir}")
            shutil.rmtree(self.final_dir)

        self.final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.staging_dir), str(self.final_dir))
        logger.info(f"Collection moved to: {self.final_dir}")
