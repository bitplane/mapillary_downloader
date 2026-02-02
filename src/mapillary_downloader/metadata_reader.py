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
        self.is_complete = self._check_complete()

    def _check_complete(self):
        """Check if metadata file has completion marker.

        Returns:
            True if completion marker found, False otherwise
        """
        if not self.metadata_file.exists():
            return False

        # Check last few lines for completion marker (it should be at the end)
        try:
            if self.metadata_file.suffix == ".gz":
                file_handle = gzip.open(self.metadata_file, "rt")
            else:
                file_handle = open(self.metadata_file)

            with file_handle as f:
                # Read last 10 lines to find completion marker
                lines = []
                for line in f:
                    lines.append(line)
                    if len(lines) > 10:
                        lines.pop(0)

                # Check if any of the last lines is the completion marker
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("__complete__"):
                            return True
                    except json.JSONDecodeError:
                        continue

            return False
        except Exception:
            return False

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
