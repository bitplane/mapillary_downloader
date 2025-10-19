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

    # Find all sequence directories (skip special dirs)
    # Now organized as first_char/sequence_id/ due to bucketing
    skip_dirs = {".meta", "__pycache__"}
    sequence_dirs = []

    for bucket_dir in collection_dir.iterdir():
        if bucket_dir.is_dir() and bucket_dir.name not in skip_dirs:
            # Check if this is a bucket dir (single char) or a sequence dir (for backward compat)
            if len(bucket_dir.name) == 1:
                # This is a bucket dir, look for sequences inside it
                for seq_dir in bucket_dir.iterdir():
                    if seq_dir.is_dir() and seq_dir.name not in skip_dirs:
                        sequence_dirs.append(seq_dir)
            else:
                # Old format - sequence dir directly under collection_dir
                sequence_dirs.append(bucket_dir)

    if not sequence_dirs:
        logger.info("No sequence directories to tar")
        return 0, 0

    logger.info(f"Tarring {len(sequence_dirs)} sequence directories...")

    tarred_count = 0
    total_files = 0
    total_tar_bytes = 0

    for seq_dir in sequence_dirs:
        seq_name = seq_dir.name
        tar_path = collection_dir / f"{seq_name}.tar"

        # Handle naming collision - find next available name
        counter = 1
        while tar_path.exists():
            counter += 1
            tar_path = collection_dir / f"{seq_name}.{counter}.tar"

        # Count files in sequence
        files = list(seq_dir.glob("*"))
        file_count = len([f for f in files if f.is_file()])

        if file_count == 0:
            logger.warning(f"Skipping empty directory: {seq_name}")
            continue

        try:
            # Create reproducible uncompressed tar (WebP already compressed)
            # Sort files by name for deterministic ordering
            files_to_tar = sorted([f for f in seq_dir.rglob("*") if f.is_file()], key=lambda x: x.name)

            if not files_to_tar:
                logger.warning(f"Skipping directory with no files: {seq_name}")
                continue

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

                # Remove original directory
                for file in seq_dir.rglob("*"):
                    if file.is_file():
                        file.unlink()

                # Remove empty subdirs and main dir
                for subdir in list(seq_dir.rglob("*")):
                    if subdir.is_dir():
                        try:
                            subdir.rmdir()
                        except OSError:
                            pass  # Not empty yet

                seq_dir.rmdir()

                tarred_count += 1
                total_files += file_count

                if tarred_count % 10 == 0:
                    logger.info(f"Tarred {tarred_count}/{len(sequence_dirs)} sequences...")
            else:
                logger.error(f"Tar file empty or not created: {tar_path}")
                if tar_path.exists():
                    tar_path.unlink()

        except Exception as e:
            logger.error(f"Error tarring {seq_name}: {e}")
            if tar_path.exists():
                tar_path.unlink()

    logger.info(
        f"Tarred {tarred_count} sequences ({total_files:,} files, {format_size(total_tar_bytes)} total tar size)"
    )
    return tarred_count, total_files
