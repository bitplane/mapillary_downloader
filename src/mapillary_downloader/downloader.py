"""Main downloader logic."""

import json
import logging
import shutil
import threading
import time
from pathlib import Path
import requests
from mapillary_downloader import paths
from mapillary_downloader.chunks import ChunkManifest
from mapillary_downloader.collection import CollectionId, CollectionPaths
from mapillary_downloader.finalizer import finalize_collection
from mapillary_downloader.limits import DownloadLimits
from mapillary_downloader.utils import format_size, format_time, get_cache_dir, safe_json_save
from mapillary_downloader.ia_check import check_ia_exists
from mapillary_downloader.worker import worker_process
from mapillary_downloader.worker_pool import AdaptiveWorkerPool
from mapillary_downloader.metadata_reader import MetadataReader
from mapillary_downloader.logging_config import add_file_handler

logger = logging.getLogger("mapillary_downloader")


def clean_log_only_dirs():
    """Remove cache directories that contain only log files."""
    cache_dir = get_cache_dir()
    removed = 0

    for path in sorted(cache_dir.iterdir()):
        if not path.is_dir() or not path.name.startswith("mapillary-"):
            continue

        contents = list(path.iterdir())
        if not contents:
            continue

        if all(f.name.startswith(paths.LOG_FILE_PREFIX) for f in contents):
            log_count = len(contents)
            shutil.rmtree(path)
            logger.info("Removed %s (%d log files)", path.name, log_count)
            removed += 1

    if removed:
        logger.info("Removed %d directories", removed)
    else:
        logger.info("No log-only directories found")


class MapillaryDownloader:
    """Handles downloading Mapillary data for a user."""

    def __init__(
        self,
        client,
        output_dir,
        username=None,
        quality=None,
        max_workers=128,
        tar_sequences=True,
        convert_webp=False,
        check_ia=True,
        limits=None,
    ):
        """Initialize the downloader.

        Args:
            client: MapillaryClient instance
            output_dir: Base directory to save downloads (final destination)
            username: Mapillary username (for collection directory)
            quality: Image quality (for collection directory)
            max_workers: Maximum number of parallel workers (default: 128)
            tar_sequences: Whether to tar sequence directories after download (default: True)
            convert_webp: Whether to convert images to WebP (affects collection name)
            check_ia: Whether to check if collection exists on Internet Archive (default: True)
        """
        self.client = client
        self.base_output_dir = Path(output_dir)
        self.username = username
        self.quality = quality
        self.max_workers = max_workers
        self.tar_sequences = tar_sequences
        self.convert_webp = convert_webp
        self.check_ia = check_ia
        self.limits = limits or DownloadLimits()

        if username and quality:
            self.collection_id = CollectionId(username=username, quality=quality, is_webp=convert_webp)
            self.collection_name = self.collection_id.name
        else:
            self.collection_id = None
            self.collection_name = None

        cache_dir = get_cache_dir()
        if self.collection_id:
            self.paths = CollectionPaths.for_collection(self.base_output_dir, self.collection_id, cache_dir)
        else:
            self.paths = CollectionPaths.anonymous(self.base_output_dir, cache_dir)

        self.staging_dir = self.paths.staging_dir
        self.final_dir = self.paths.final_dir

        self.chunked = bool(self.collection_id and self.limits.is_chunked)
        self.chunk_manifest = None
        if self.chunked:
            self.output_dir = self.paths.payload_dir
        else:
            self.output_dir = self.staging_dir

        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Staging directory: {self.staging_dir}")
        logger.info(f"Final destination: {self.final_dir}")

        # Set up file logging for archival with timestamp for incremental runs
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_file = self.output_dir / f"{paths.LOG_FILE_PREFIX}{timestamp}"
        self.file_handler = add_file_handler(log_file)
        logger.info(f"Logging to: {log_file}")

        self.metadata_file = self.paths.metadata_file
        self.progress_file = self.paths.progress_file
        self.cursor_file = self.paths.cursor_file
        self.downloaded = self._load_progress()
        self.baseline_bytes = self._baseline_bytes()
        self._last_save_time = time.time()

    def _close_file_handler(self):
        """Close and detach this downloader's per-run file log handler."""
        if self.file_handler is None:
            return
        self.file_handler.close()
        logger.removeHandler(self.file_handler)
        self.file_handler = None

    def _load_progress(self):
        """Load previously downloaded image IDs for this quality."""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                data = json.load(f)
            return set(data.get(str(self.quality), []))
        return set()

    def _baseline_bytes(self):
        """Sum sizes of already-downloaded payload files."""
        total = 0
        skip_names = {
            paths.METADATA_JSONL,
            paths.METADATA_JSONL_GZ,
            paths.PROGRESS_JSON,
            paths.API_CURSOR,
            paths.CHUNKS_JSON,
            paths.IA_THUMBNAIL,
        }
        for f in self.output_dir.rglob("*"):
            if not f.is_file():
                continue
            if f.name in skip_names or f.name.startswith(paths.LOG_FILE_PREFIX):
                continue
            if ".meta" in f.parts:
                continue
            total += f.stat().st_size
        return total

    def _free_space_ok(self):
        """Return True if the staging filesystem has enough free space."""
        if self.limits.min_free_space_bytes is None:
            return True
        usage = shutil.disk_usage(self.staging_dir)
        return usage.free >= self.limits.min_free_space_bytes

    def _init_chunk_manifest(self, bbox):
        if not self.chunked:
            return None
        if not self.paths.chunks_file.exists() and self.final_dir.exists():
            logger.info(f"Collection already exists at {self.final_dir}, skipping download")
            self._close_file_handler()
            return None
        self.chunk_manifest = ChunkManifest.for_paths(
            self.paths,
            self.collection_id,
            bbox=bbox,
            max_size_bytes=self.limits.max_size_bytes,
            max_images=self.limits.max_images,
        )
        if self.chunk_manifest.is_complete:
            logger.info("Chunked collection already marked complete, skipping download")
            self._close_file_handler()
            self.chunk_manifest = None
            return None

        finalizing = self.chunk_manifest.finalizing
        if finalizing:
            finalizing_name = finalizing.get("name")
            finalizing_dir = self.base_output_dir / finalizing_name
            work_dir = self.staging_dir / finalizing_name
            if finalizing_dir.exists():
                logger.info("Reconciling completed finalization for %s", finalizing_name)
                self.chunk_manifest.mark_completed(
                    finalizing_name,
                    finalizing.get("images", 0),
                    finalizing.get("bytes", 0),
                    final=finalizing.get("final", False),
                )
                if finalizing.get("final", False):
                    self._close_file_handler()
                    self.chunk_manifest = None
                    return None
            elif work_dir.exists():
                raise RuntimeError(f"Finalization work directory exists and needs repair: {work_dir}")
            else:
                self.chunk_manifest.clear_finalizing()

        while self.chunk_manifest.next_output_dir(self.base_output_dir).exists():
            logger.info("Chunk output already exists locally: %s", self.chunk_manifest.next_name())
            self.chunk_manifest.advance()

        if self.check_ia:
            session = requests.Session()
            if not self.paths.chunks_file.exists() and check_ia_exists(session, self.collection_name):
                logger.info("Collection already exists on archive.org, skipping download")
                self._close_file_handler()
                return None
            while check_ia_exists(session, self.chunk_manifest.next_name()):
                logger.info("Chunk already exists on archive.org: %s", self.chunk_manifest.next_name())
                self.chunk_manifest.advance()

        self.chunk_manifest.save()
        logger.info("Chunked output enabled: next chunk %s", self.chunk_manifest.next_name())
        return self.chunk_manifest

    def _save_progress(self):
        """Save progress to disk atomically, per-quality."""
        progress = {}
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    progress = data

        progress[str(self.quality)] = list(self.downloaded)

        safe_json_save(self.progress_file, progress)

    def _submit_metadata_batch(
        self,
        file_handle,
        quality_field,
        pool,
        process_results,
        base_submitted,
        should_stop_submitting=None,
    ):
        """Read metadata lines from current position, submit to workers.

        Args:
            file_handle: Open file positioned at read point
            quality_field: Field name for quality URL (e.g., "thumb_1024_url")
            pool: Worker pool to submit to
            process_results: Callback to drain result queue
            base_submitted: Running total for cumulative logging

        Returns:
            tuple: (submitted_count, skipped_count) for this batch
        """
        submitted = 0
        skipped = 0

        while True:
            line = file_handle.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                image = json.loads(line)
            except json.JSONDecodeError:
                continue

            if image.get("__complete__"):
                continue

            image_id = image.get("id")
            if not image_id:
                continue

            if image_id in self.downloaded:
                skipped += 1
                continue

            if not image.get(quality_field):
                continue

            if should_stop_submitting and should_stop_submitting(image):
                break

            work_item = (
                image,
                str(self.output_dir),
                self.quality,
                self.convert_webp,
                self.client.access_token,
            )
            pool.submit(work_item)
            submitted += 1

            total = base_submitted + submitted
            if total % 1000 == 0:
                logger.info(f"Queue: submitted {total:,} images")

            process_results()

        return submitted, skipped

    def download_user_data(self, bbox=None):
        """Download all images for a user using streaming queue-based architecture.

        Args:
            bbox: Optional bounding box [west, south, east, north]
        """
        if not self.username or not self.quality:
            raise ValueError("Username and quality must be provided during initialization")

        self._init_chunk_manifest(bbox)
        if self.chunked and self.chunk_manifest is None:
            return

        # Check if collection already exists in final destination
        if not self.chunked and self.final_dir.exists():
            logger.info(f"Collection already exists at {self.final_dir}, skipping download")
            self._close_file_handler()
            return

        # Check if collection already exists on Internet Archive
        if self.check_ia and self.collection_name and not self.chunked:
            logger.info(f"Checking if {self.collection_name} exists on Internet Archive...")
            if check_ia_exists(requests.Session(), self.collection_name):
                logger.info("Collection already exists on archive.org, skipping download")
                self._close_file_handler()
                return

        quality_field = f"thumb_{self.quality}_url"

        logger.info(f"Downloading {self.username} @ {self.quality} (max {self.max_workers} workers)")

        start_time = time.time()

        # Step 1: Check if API fetch is already complete
        reader = MetadataReader(self.metadata_file)
        api_complete = reader.is_complete

        # Step 2: Start worker pool
        pool = AdaptiveWorkerPool(worker_process, max_workers=self.max_workers, monitoring_interval=10)
        pool.start()

        # Step 3: Download images from metadata file while fetching new from API
        downloaded_count = 0
        total_bytes = 0
        total_output_bytes = 0
        failed_count = 0
        submitted = 0
        skipped_count = 0
        batch_limit_reached = False
        free_space_exhausted = False
        stop_after_sequence = None
        last_submitted_sequence = None

        try:
            # Step 3a: Fetch metadata from API in parallel (write-only, don't block on queue)
            api_fetch_complete = threading.Event()
            api_fetch_error = [None]  # Mutable so thread can store exception
            api_fetch_stopped_early = [False]

            if not api_complete:
                new_images_count = [0]  # Mutable so thread can update it

                # Load cursor for resume
                start_url = None
                if self.cursor_file.exists():
                    start_url = self.cursor_file.read_text().strip()
                    if start_url:
                        logger.info("Found API cursor, will resume from saved position")

                def save_cursor(next_url):
                    """Save pagination cursor atomically for resume."""
                    if next_url:
                        tmp = self.cursor_file.with_suffix(".tmp")
                        tmp.write_text(next_url)
                        tmp.replace(self.cursor_file)
                    elif self.cursor_file.exists():
                        self.cursor_file.unlink()

                def fetch_api_metadata():
                    """Fetch metadata from API and write to file (runs in thread)."""
                    try:
                        logger.debug("API fetch thread starting")
                        with open(self.metadata_file, "a") as meta_f:
                            for image in self.client.get_user_images(
                                self.username, self.quality, bbox=bbox, start_url=start_url, on_page=save_cursor
                            ):
                                if batch_limit_reached or free_space_exhausted:
                                    logger.info("Stopping API fetch for current batch")
                                    api_fetch_stopped_early[0] = True
                                    break
                                new_images_count[0] += 1

                                # Save metadata (don't dedupe here, let the tailer handle it)
                                meta_f.write(json.dumps(image) + "\n")
                                meta_f.flush()

                                if new_images_count[0] % 1000 == 0:
                                    logger.info(f"API: fetched {new_images_count[0]:,} image URLs")

                            if not api_fetch_stopped_early[0]:
                                # Mark as complete and remove cursor
                                MetadataReader.mark_complete(self.metadata_file)
                                if self.cursor_file.exists():
                                    self.cursor_file.unlink()
                                logger.info(f"API fetch complete: {new_images_count[0]:,} images")
                    except Exception as e:
                        api_fetch_error[0] = e
                        logger.error(f"API fetch failed: {e}")
                    finally:
                        api_fetch_complete.set()

                # Start API fetch in background thread
                api_thread = threading.Thread(target=fetch_api_metadata, daemon=True)
                api_thread.start()
            else:
                api_fetch_complete.set()

            # Step 3b: Tail metadata file and submit to workers
            logger.debug("Starting metadata tail and download queue feeder")
            last_position = 0

            # Helper to process results from queue
            def process_results():
                nonlocal downloaded_count, total_bytes, total_output_bytes, failed_count
                nonlocal batch_limit_reached, stop_after_sequence, free_space_exhausted
                # Drain ALL available results to prevent queue from filling up
                while True:
                    result = pool.get_result(timeout=0)  # Non-blocking
                    if result is None:
                        break

                    if len(result) == 4:
                        image_id, bytes_dl, success, error_msg = result
                        output_bytes = bytes_dl
                        sequence_id = None
                    else:
                        image_id, bytes_dl, output_bytes, sequence_id, success, error_msg = result

                    if success:
                        self.downloaded.add(image_id)
                        downloaded_count += 1
                        total_bytes += bytes_dl
                        total_output_bytes += output_bytes

                        # Log the first image, 100, then every 1,000.
                        total_downloaded = len(self.downloaded)
                        should_log = downloaded_count in (1, 100) or downloaded_count % 1000 == 0
                        if should_log:
                            logger.info(
                                f"Downloaded: {total_downloaded:,} "
                                f"({format_size(total_bytes)} this session, "
                                f"{format_size(self.baseline_bytes + total_bytes)} total)"
                            )

                        if downloaded_count % 100 == 0:
                            pool.check_throughput(downloaded_count)
                            # Save progress every 5 minutes
                            if time.time() - self._last_save_time >= 300:
                                self._save_progress()
                                self._last_save_time = time.time()

                        if self.limits.max_size_bytes is not None:
                            if self.baseline_bytes + total_output_bytes >= self.limits.max_size_bytes:
                                batch_limit_reached = True
                                stop_after_sequence = sequence_id
                        if self.limits.max_images is not None and downloaded_count >= self.limits.max_images:
                            batch_limit_reached = True
                            stop_after_sequence = sequence_id
                        if not self._free_space_ok():
                            free_space_exhausted = True
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to download {image_id}: {error_msg}")

            def should_stop_submitting(image):
                nonlocal last_submitted_sequence
                process_results()

                if free_space_exhausted:
                    return True

                sequence_id = image.get("sequence") or image.get("id")
                if batch_limit_reached:
                    if stop_after_sequence is None or sequence_id != stop_after_sequence:
                        return True

                last_submitted_sequence = sequence_id
                return False

            # Tail the metadata file and submit to workers
            while True:
                if self.metadata_file.exists():
                    with open(self.metadata_file) as f:
                        f.seek(last_position)
                        batch_submitted, batch_skipped = self._submit_metadata_batch(
                            f, quality_field, pool, process_results, submitted, should_stop_submitting
                        )
                        submitted += batch_submitted
                        skipped_count += batch_skipped
                        last_position = f.tell()

                if api_fetch_complete.is_set() or batch_limit_reached or free_space_exhausted:
                    break

                time.sleep(0.1)
                process_results()

            # The API thread may have written its final lines after the last
            # tail read but before it set the completion event.
            if self.metadata_file.exists():
                with open(self.metadata_file) as f:
                    f.seek(last_position)
                    batch_submitted, batch_skipped = self._submit_metadata_batch(
                        f, quality_field, pool, process_results, submitted, should_stop_submitting
                    )
                    submitted += batch_submitted
                    skipped_count += batch_skipped
                    last_position = f.tell()

            # Send shutdown signals
            logger.debug(f"Submitted {submitted:,} images, waiting for workers")
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

                if len(result) == 4:
                    image_id, bytes_dl, success, error_msg = result
                    output_bytes = bytes_dl
                    sequence_id = None
                else:
                    image_id, bytes_dl, output_bytes, sequence_id, success, error_msg = result
                completed += 1

                if success:
                    self.downloaded.add(image_id)
                    downloaded_count += 1
                    total_bytes += bytes_dl
                    total_output_bytes += output_bytes

                    if downloaded_count in (1, 100) or downloaded_count % 1000 == 0:
                        logger.info(
                            f"Downloaded: {len(self.downloaded):,} "
                            f"({format_size(total_bytes)} this session, "
                            f"{format_size(self.baseline_bytes + total_bytes)} total)"
                        )
                    if downloaded_count % 100 == 0:
                        pool.check_throughput(downloaded_count)
                        # Save progress every 5 minutes
                        if time.time() - self._last_save_time >= 300:
                            self._save_progress()
                            self._last_save_time = time.time()
                    if self.limits.max_size_bytes is not None:
                        if self.baseline_bytes + total_output_bytes >= self.limits.max_size_bytes:
                            batch_limit_reached = True
                            stop_after_sequence = sequence_id
                    if self.limits.max_images is not None and downloaded_count >= self.limits.max_images:
                        batch_limit_reached = True
                        stop_after_sequence = sequence_id
                else:
                    failed_count += 1
                    logger.warning(f"Failed to download {image_id}: {error_msg}")

        finally:
            # Shutdown worker pool
            pool.shutdown()
            self._save_progress()

        elapsed = time.time() - start_time

        logger.info(
            f"Session: {downloaded_count:,} downloaded ({format_size(total_bytes)}), "
            f"{len(self.downloaded):,} total, skipped {skipped_count:,}, failed {failed_count:,}"
        )
        if self.chunked:
            logger.info("Batch output size: %s", format_size(self.baseline_bytes + total_output_bytes))
        logger.info(f"Total time: {format_time(elapsed)}")

        if free_space_exhausted:
            logger.error(
                "Minimum free space reached, leaving staging payload for retry: %s",
                self.output_dir,
            )
            self._close_file_handler()
            raise RuntimeError("Minimum free space reached")

        # If API fetch failed, leave staging dir for retry. A clean run with no
        # downloadable image URLs is still finalized so IA can mark it archived.
        if api_fetch_error[0] is not None:
            logger.error("API fetch failed, leaving staging dir for retry: %s", self.staging_dir)
            self._close_file_handler()
            raise api_fetch_error[0]

        if self.chunked:
            chunk_name = self.chunk_manifest.next_name()
            final_dir = self.base_output_dir / chunk_name
            is_final = api_fetch_complete.is_set() and not api_fetch_stopped_early[0] and not batch_limit_reached
            self.chunk_manifest.mark_finalizing(
                chunk_name,
                images=downloaded_count,
                bytes_count=self.baseline_bytes + total_output_bytes,
                final=is_final,
            )
            finalize_collection(
                self.output_dir,
                final_dir,
                convert_webp=self.convert_webp,
                tar_sequences=self.tar_sequences,
                before_move=self._close_file_handler,
                state_dir=self.staging_dir,
                include_master_state=is_final,
                chunk_title=f"Mapillary images by {self.username} ({chunk_name})",
                chunk_description=(
                    f"Intermediate Mapillary download chunk {chunk_name}. "
                    "Master metadata is kept with the final chunk."
                ),
                chunk_username=self.username,
            )
            self.chunk_manifest.mark_completed(
                chunk_name,
                downloaded_count,
                self.baseline_bytes + total_output_bytes,
                final=is_final,
            )
            if is_final:
                logger.info("Chunked download complete")
            else:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Batch limit reached, exiting cleanly. Re-run to continue.")
            return

        finalize_collection(
            self.output_dir,
            self.final_dir,
            convert_webp=self.convert_webp,
            tar_sequences=self.tar_sequences,
            before_move=self._close_file_handler,
        )
