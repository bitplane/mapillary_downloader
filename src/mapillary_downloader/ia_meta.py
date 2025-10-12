"""Internet Archive metadata generation for Mapillary collections."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from importlib.metadata import version

logger = logging.getLogger("mapillary_downloader")


def parse_collection_name(directory):
    """Parse username and quality from directory name.

    Args:
        directory: Path to collection directory (e.g., mapillary-username-original)

    Returns:
        Tuple of (username, quality) or (None, None) if parsing fails
    """
    match = re.match(r"mapillary-(.+)-(256|1024|2048|original)$", Path(directory).name)
    if match:
        return match.group(1), match.group(2)
    return None, None


def get_date_range(metadata_file):
    """Get first and last captured_at dates from metadata.jsonl.

    Args:
        metadata_file: Path to metadata.jsonl file

    Returns:
        Tuple of (first_date, last_date) as ISO format strings, or (None, None)
    """
    if not Path(metadata_file).exists():
        return None, None

    timestamps = []
    with open(metadata_file) as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                if "captured_at" in data:
                    timestamps.append(data["captured_at"])

    if not timestamps:
        return None, None

    # Convert from milliseconds to seconds, then to datetime
    first_ts = min(timestamps) / 1000
    last_ts = max(timestamps) / 1000

    first_date = datetime.fromtimestamp(first_ts).strftime("%Y-%m-%d")
    last_date = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d")

    return first_date, last_date


def count_images(metadata_file):
    """Count number of images in metadata.jsonl.

    Args:
        metadata_file: Path to metadata.jsonl file

    Returns:
        Number of images
    """
    if not Path(metadata_file).exists():
        return 0

    count = 0
    with open(metadata_file) as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def write_meta_tag(meta_dir, tag, values):
    """Write metadata tag files in rip format.

    Args:
        meta_dir: Path to .meta directory
        tag: Tag name
        values: Single value or list of values
    """
    tag_dir = meta_dir / tag
    tag_dir.mkdir(parents=True, exist_ok=True)

    if not isinstance(values, list):
        values = [values]

    for idx, value in enumerate(values):
        (tag_dir / str(idx)).write_text(str(value))


def generate_ia_metadata(collection_dir):
    """Generate Internet Archive metadata for a Mapillary collection.

    Args:
        collection_dir: Path to collection directory (e.g., ./mapillary_data/mapillary-username-original)

    Returns:
        True if successful, False otherwise
    """
    collection_dir = Path(collection_dir)
    username, quality = parse_collection_name(collection_dir)

    if not username or not quality:
        logger.error(f"Could not parse username/quality from directory: {collection_dir.name}")
        return False

    metadata_file = collection_dir / "metadata.jsonl"
    if not metadata_file.exists():
        logger.error(f"metadata.jsonl not found in {collection_dir}")
        return False

    logger.info(f"Generating IA metadata for {collection_dir.name}...")

    # Get date range and image count
    first_date, last_date = get_date_range(metadata_file)
    image_count = count_images(metadata_file)

    if not first_date or not last_date:
        logger.warning("Could not determine date range from metadata")
        first_date = last_date = "unknown"

    # Create .meta directory
    meta_dir = collection_dir / ".meta"
    meta_dir.mkdir(exist_ok=True)

    # Generate metadata tags
    write_meta_tag(
        meta_dir,
        "title",
        f"Mapillary images by {username}",
    )

    description = (
        f"Street-level imagery from Mapillary user '{username}'. "
        f"Contains {image_count:,} images captured between {first_date} and {last_date}. "
        f"Images are organized by sequence ID and include EXIF metadata with GPS coordinates, "
        f"camera information, and compass direction.\n\n"
        f"Downloaded using mapillary_downloader (https://bitplane.net/dev/python/mapillary_downloader/). "
        f"Uploaded using rip (https://bitplane.net/dev/sh/rip)."
    )
    write_meta_tag(meta_dir, "description", description)

    # Subject tags
    write_meta_tag(
        meta_dir,
        "subject",
        ["mapillary", "street-view", "computer-vision", "geospatial", "photography"],
    )

    write_meta_tag(meta_dir, "creator", username)
    write_meta_tag(meta_dir, "date", first_date)
    write_meta_tag(meta_dir, "coverage", f"{first_date} - {last_date}")
    write_meta_tag(meta_dir, "licenseurl", "https://creativecommons.org/licenses/by-sa/4.0/")
    write_meta_tag(meta_dir, "mediatype", "data")
    write_meta_tag(meta_dir, "collection", "opensource_media")

    # Source and scanner metadata
    write_meta_tag(meta_dir, "source", f"https://www.mapillary.com/app/user/{username}")

    downloader_version = version("mapillary_downloader")
    write_meta_tag(
        meta_dir,
        "scanner",
        [
            f"mapillary_downloader {downloader_version} https://bitplane.net/dev/python/mapillary_downloader/",
            "rip https://bitplane.net/dev/sh/rip",
        ],
    )

    # Add searchable tag for batch collection management
    write_meta_tag(meta_dir, "mapillary_downloader", downloader_version)

    logger.info(f"IA metadata generated in {meta_dir}")
    return True
