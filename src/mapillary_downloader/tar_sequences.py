"""Tar sequence directories for efficient Internet Archive uploads."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from mapillary_downloader.utils import format_size

logger = logging.getLogger("mapillary_downloader")


def tar_date_directory(collection_dir, date_dir):
    """Tar a single date directory using GNU tar.

    Args:
        collection_dir: Path to collection directory (working directory for tar)
        date_dir: Path to date directory to tar

    Returns:
        Tuple of (tar_path, file_count) on success, or (None, 0) on failure
    """
    date_name = date_dir.name

    # Find next available tar filename (don't overwrite existing tars)
    tar_path = collection_dir / f"{date_name}.tar"
    if tar_path.exists():
        addendum = 1
        while True:
            tar_path = collection_dir / f"{date_name}.{addendum}.tar"
            if not tar_path.exists():
                break
            addendum += 1
        logger.info(f"Existing tar for {date_name}, creating addendum: {tar_path.name}")

    # Count files first to skip empty dirs
    file_count = sum(1 for f in date_dir.rglob("*") if f.is_file())
    if file_count == 0:
        logger.warning(f"Skipping empty date directory: {date_name}")
        return None, 0

    logger.info(f"Tarring date '{date_name}' ({file_count} files)...")

    result = subprocess.run(
        [
            "tar",
            "cf",
            str(tar_path),
            "--sort=name",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            date_name,
        ],
        cwd=collection_dir,
        capture_output=True,
    )

    if result.returncode != 0:
        logger.error(f"tar failed for {date_name}: {result.stderr.decode()}")
        if tar_path.exists():
            tar_path.unlink()
        return None, 0

    if not tar_path.exists() or tar_path.stat().st_size == 0:
        logger.error(f"Tar file empty or not created: {tar_path}")
        if tar_path.exists():
            tar_path.unlink()
        return None, 0

    # Remove original date directory
    shutil.rmtree(date_dir)

    return tar_path, file_count


def tar_sequence_directories(collection_dir):
    """Tar all date directories in a collection for faster IA uploads.

    Organizes by capture date (YYYY-MM-DD) for incremental archive.org uploads.

    Args:
        collection_dir: Path to collection directory (e.g., mapillary-user-quality/)

    Returns:
        Tuple of (tarred_count, total_files_tarred)
    """
    collection_dir = Path(collection_dir)

    if not collection_dir.exists():
        logger.error(f"Collection directory not found: {collection_dir}")
        return 0, 0

    # Find all date directories (skip special dirs)
    skip_dirs = {".meta", "__pycache__"}
    date_dirs = []

    for item in collection_dir.iterdir():
        if item.is_dir() and item.name not in skip_dirs:
            if re.match(r"\d{4}-\d{2}-\d{2}$", item.name) or item.name == "unknown-date":
                date_dirs.append(item)

    if not date_dirs:
        logger.info("No date directories to tar")
        return 0, 0

    date_dirs = sorted(date_dirs, key=lambda x: x.name)

    logger.info(f"Tarring {len(date_dirs)} date directories...")

    tarred_count = 0
    total_files = 0
    total_tar_bytes = 0

    for date_dir in date_dirs:
        tar_path, file_count = tar_date_directory(collection_dir, date_dir)
        if tar_path:
            tar_size = tar_path.stat().st_size
            total_tar_bytes += tar_size
            tarred_count += 1
            total_files += file_count
            logger.info(f"Tarred date '{date_dir.name}': {file_count:,} files, {format_size(tar_size)}")

    logger.info(f"Tarred {tarred_count} dates ({total_files:,} files, {format_size(total_tar_bytes)} total tar size)")
    return tarred_count, total_files
