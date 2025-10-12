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


def convert_to_webp(jpg_path, output_path=None, delete_original=True):
    """Convert a JPG image to WebP format, preserving EXIF metadata.

    Args:
        jpg_path: Path to the JPG file
        output_path: Optional path for the WebP output. If None, uses jpg_path with .webp extension
        delete_original: Whether to delete the original JPG after conversion (default: True)

    Returns:
        Path object to the new WebP file, or None if conversion failed
    """
    jpg_path = Path(jpg_path)

    if output_path is None:
        webp_path = jpg_path.with_suffix(".webp")
    else:
        webp_path = Path(output_path)
        # Ensure output directory exists
        webp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Convert with cwebp, preserving all metadata
        result = subprocess.run(
            ["cwebp", "-metadata", "all", str(jpg_path), "-o", str(webp_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.error(f"cwebp conversion failed for {jpg_path}: {result.stderr}")
            return None

        # Delete original JPG after successful conversion if requested
        if delete_original:
            jpg_path.unlink()
        return webp_path

    except subprocess.TimeoutExpired:
        logger.error(f"cwebp conversion timed out for {jpg_path}")
        return None
    except Exception as e:
        logger.error(f"Error converting {jpg_path} to WebP: {e}")
        return None
