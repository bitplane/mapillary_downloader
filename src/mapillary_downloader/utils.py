"""Utility functions for formatting and display."""

import json
import logging
import os
import time
from pathlib import Path
import requests
from requests.exceptions import RequestException

logger = logging.getLogger("mapillary_downloader")


def format_size(bytes_count):
    """Format bytes as human-readable size.

    Args:
        bytes_count: Number of bytes

    Returns:
        Formatted string (e.g. "1.23 GB", "456.78 MB")
    """
    if bytes_count >= 1_000_000_000:
        return f"{bytes_count / 1_000_000_000:.2f} GB"
    if bytes_count >= 1_000_000:
        return f"{bytes_count / 1_000_000:.2f} MB"
    if bytes_count >= 1_000:
        return f"{bytes_count / 1000:.2f} KB"
    return f"{bytes_count} B"


def format_time(seconds):
    """Format seconds as human-readable time.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted string (e.g. "2h 15m", "45m 30s", "30s")
    """
    if seconds < 60:
        return f"{int(seconds)}s"

    minutes = int(seconds / 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = int(minutes / 60)
    remaining_minutes = minutes % 60

    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"


def safe_json_save(file_path, data):
    """Atomically save JSON data to file.

    Writes to temp file, then atomic rename to prevent corruption.

    Args:
        file_path: Path to JSON file
        data: Data to serialize to JSON
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    temp_file = file_path.with_suffix(".json.tmp")
    with open(temp_file, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp_file.replace(file_path)


def http_get_with_retry(url, params=None, max_retries=5, base_delay=1.0, timeout=60):
    """HTTP GET with exponential backoff retry.

    Args:
        url: URL to fetch
        params: Optional query parameters
        max_retries: Maximum retry attempts (default: 5)
        base_delay: Initial delay in seconds (default: 1.0)
        timeout: Request timeout in seconds (default: 60)

    Returns:
        requests.Response object

    Raises:
        requests.RequestException: If all retries exhausted
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except RequestException as e:
            if attempt == max_retries - 1:
                raise

            delay = base_delay * (2**attempt)
            logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
            logger.info(f"Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
