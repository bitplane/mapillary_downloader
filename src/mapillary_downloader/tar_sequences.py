"""Tar sequence directories for efficient Internet Archive uploads."""

import logging
import tarfile
from pathlib import Path
from mapillary_downloader.utils import format_size

logger = logging.getLogger("mapillary_downloader")


def tar_sequence_directories(collection_dir):
    """Tar all sequence directories in a collection for faster IA uploads.

    Args:
        collection_dir: Path to collection directory (e.g., mapillary-user-quality/)

    Returns:
        Tuple of (tarred_count, total_files_tarred)
    """
    collection_dir = Path(collection_dir)

    if not collection_dir.exists():
        logger.error(f"Collection directory not found: {collection_dir}")
        return 0, 0

    # Find all bucket directories (skip special dirs)
    # Now we tar entire bucket dirs (e.g., a/, b/, etc) to get ~62 tar files
    skip_dirs = {".meta", "__pycache__"}
    bucket_dirs = []

    for item in collection_dir.iterdir():
        if item.is_dir() and item.name not in skip_dirs:
            # Check if this is a bucket dir (single char)
            if len(item.name) == 1:
                bucket_dirs.append(item)

    if not bucket_dirs:
        logger.info("No bucket directories to tar")
        return 0, 0

    # Sort bucket directories alphabetically for consistent progress tracking
    bucket_dirs = sorted(bucket_dirs, key=lambda x: x.name)

    logger.info(f"Tarring {len(bucket_dirs)} bucket directories...")

    tarred_count = 0
    total_files = 0
    total_tar_bytes = 0

    for bucket_dir in bucket_dirs:
        bucket_name = bucket_dir.name
        tar_path = collection_dir / f"{bucket_name}.tar"

        # Count files in bucket
        files_to_tar = sorted([f for f in bucket_dir.rglob("*") if f.is_file()], key=lambda x: str(x))
        file_count = len(files_to_tar)

        if file_count == 0:
            logger.warning(f"Skipping empty bucket directory: {bucket_name}")
            continue

        try:
            logger.info(f"Tarring bucket '{bucket_name}' ({file_count} files)...")

            # Create reproducible uncompressed tar (WebP already compressed)
            with tarfile.open(tar_path, "w") as tar:
                for file_path in files_to_tar:
                    # Get path relative to collection_dir for tar archive
                    arcname = file_path.relative_to(collection_dir)

                    # Create TarInfo for reproducibility
                    tarinfo = tar.gettarinfo(str(file_path), arcname=str(arcname))

                    # Normalize for reproducibility across platforms
                    tarinfo.uid = 0
                    tarinfo.gid = 0
                    tarinfo.uname = ""
                    tarinfo.gname = ""
                    # mtime already set on file by worker, preserve it

                    # Add file to tar
                    with open(file_path, "rb") as f:
                        tar.addfile(tarinfo, f)

            # Verify tar was created and has size
            if tar_path.exists() and tar_path.stat().st_size > 0:
                tar_size = tar_path.stat().st_size
                total_tar_bytes += tar_size

                # Remove original bucket directory
                for file in bucket_dir.rglob("*"):
                    if file.is_file():
                        file.unlink()

                # Remove empty subdirs and main dir
                for subdir in list(bucket_dir.rglob("*")):
                    if subdir.is_dir():
                        try:
                            subdir.rmdir()
                        except OSError:
                            pass  # Not empty yet

                bucket_dir.rmdir()

                tarred_count += 1
                total_files += file_count

                logger.info(f"Tarred bucket '{bucket_name}': {file_count:,} files, {format_size(tar_size)}")
            else:
                logger.error(f"Tar file empty or not created: {tar_path}")
                if tar_path.exists():
                    tar_path.unlink()

        except Exception as e:
            logger.error(f"Error tarring bucket {bucket_name}: {e}")
            if tar_path.exists():
                tar_path.unlink()

    logger.info(
        f"Tarred {tarred_count} sequences ({total_files:,} files, {format_size(total_tar_bytes)} total tar size)"
    )
    return tarred_count, total_files
