"""Streaming metadata reader with filtering."""

import gzip
import json
import logging
from pathlib import Path

logger = logging.getLogger("mapillary_downloader")


class MetadataReader:
    """Streams metadata.jsonl line-by-line with filtering.

    This avoids loading millions of image dicts into memory.
    """

    COMPLETION_MARKER = {"__complete__": True}

    def __init__(self, metadata_file):
        """Initialize metadata reader.

        Args:
            metadata_file: Path to metadata.jsonl or metadata.jsonl.gz
        """
        self.metadata_file = Path(metadata_file)
        self.is_complete = False

    def iter_images(self, quality_field=None, downloaded_ids=None):
        """Stream images from metadata file with filtering.

        Args:
            quality_field: Optional field to check exists (e.g., 'thumb_1024_url')
            downloaded_ids: Optional set of already downloaded IDs to skip

        Yields:
            Image metadata dicts that pass filters
        """
        if not self.metadata_file.exists():
            return

        # Handle gzipped files
        if self.metadata_file.suffix == ".gz":
            file_handle = gzip.open(self.metadata_file, "rt")
        else:
            file_handle = open(self.metadata_file)

        with file_handle as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                image = json.loads(line)

                # Check for completion marker
                if image.get("__complete__"):
                    self.is_complete = True
                    logger.debug("Found API fetch completion marker")
                    continue

                image_id = image.get("id")
                if not image_id:
                    continue

                # Filter by downloaded status
                if downloaded_ids and image_id in downloaded_ids:
                    continue

                # Filter by quality field availability
                if quality_field and not image.get(quality_field):
                    continue

                yield image

    def get_all_ids(self):
        """Get set of all image IDs in metadata file.

        Returns:
            Set of image IDs (for building seen_ids)
        """
        ids = set()

        if not self.metadata_file.exists():
            return ids

        # Handle gzipped files
        if self.metadata_file.suffix == ".gz":
            file_handle = gzip.open(self.metadata_file, "rt")
        else:
            file_handle = open(self.metadata_file)

        with file_handle as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                image = json.loads(line)

                # Skip completion marker
                if image.get("__complete__"):
                    self.is_complete = True
                    continue

                image_id = image.get("id")
                if image_id:
                    ids.add(image_id)

        return ids

    @staticmethod
    def mark_complete(metadata_file):
        """Append completion marker to metadata file.

        Args:
            metadata_file: Path to metadata.jsonl
        """
        metadata_file = Path(metadata_file)
        if metadata_file.exists():
            with open(metadata_file, "a") as f:
                f.write(json.dumps(MetadataReader.COMPLETION_MARKER) + "\n")
                f.flush()
            logger.info("Marked metadata file as complete")
