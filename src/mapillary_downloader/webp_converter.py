"""WebP image conversion utilities."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("mapillary_downloader")


def check_cwebp_available():
    """Check if cwebp binary is available.

    Returns:
        bool: True if cwebp is found, False otherwise
    """
    return shutil.which("cwebp") is not None


def convert_to_webp(jpg_path, output_path, delete_original=True):
    """Convert a JPG image to WebP format, preserving EXIF metadata.

    Args:
        jpg_path: Path to the JPG file
        output_path: Path for the WebP output
        delete_original: Whether to delete the original JPG after conversion (default: True)

    Returns:
        Path object to the new WebP file, or None if conversion failed
    """
    jpg_path = Path(jpg_path)
    webp_path = Path(output_path)
    webp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Convert with cwebp, preserving all metadata
        result = subprocess.run(
            ["cwebp", "-metadata", "all", str(jpg_path), "-o", str(webp_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"cwebp conversion failed for {jpg_path}: {result.stderr}")
            return None

        # Delete original JPG after successful conversion if requested
        if delete_original:
            jpg_path.unlink()
        return webp_path

    except Exception as e:
        logger.error(f"Error converting {jpg_path} to WebP: {e}")
        return None
