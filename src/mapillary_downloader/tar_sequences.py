"""Tar sequence directories for efficient Internet Archive uploads."""

import logging
import subprocess
from pathlib import Path

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
    skip_dirs = {".meta", "__pycache__"}
    sequence_dirs = []

    for item in collection_dir.iterdir():
        if item.is_dir() and item.name not in skip_dirs:
            sequence_dirs.append(item)

    if not sequence_dirs:
        logger.info("No sequence directories to tar")
        return 0, 0

    logger.info(f"Tarring {len(sequence_dirs)} sequence directories...")

    tarred_count = 0
    total_files = 0

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
            # Create uncompressed tar (WebP already compressed)
            # Use -C to change directory so paths in tar are relative
            # Use -- to prevent sequence IDs starting with - from being interpreted as options
            result = subprocess.run(
                ["tar", "-cf", str(tar_path), "-C", str(collection_dir), "--", seq_name],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per tar
            )

            if result.returncode != 0:
                logger.error(f"Failed to tar {seq_name}: {result.stderr}")
                continue

            # Verify tar was created and has size
            if tar_path.exists() and tar_path.stat().st_size > 0:
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

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout tarring {seq_name}")
            if tar_path.exists():
                tar_path.unlink()
        except Exception as e:
            logger.error(f"Error tarring {seq_name}: {e}")
            if tar_path.exists():
                tar_path.unlink()

    logger.info(f"Tarred {tarred_count} sequences ({total_files:,} files total)")
    return tarred_count, total_files
