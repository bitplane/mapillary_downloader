"""Check if collections exist on Internet Archive."""

import logging
import requests

logger = logging.getLogger("mapillary_downloader")


def check_ia_exists(session, collection_name):
    """Check if a collection exists on Internet Archive.

    Args:
        session: requests.Session for connection pooling
        collection_name: Name of the collection (e.g., mapillary-username-original-webp)

    Returns:
        Boolean indicating if the collection exists on IA
    """
    ia_url = f"https://archive.org/metadata/{collection_name}"

    try:
        response = session.get(ia_url, timeout=10)
        # If we get a 200, the item exists
        if response.status_code == 200:
            data = response.json()
            # Check if it's a valid item (not just metadata for non-existent item)
            if "metadata" in data and data.get("is_dark") is not True:
                return True
        return False
    except requests.RequestException as e:
        logger.warning(f"Failed to check IA for {collection_name}: {e}")
        # On error, assume it doesn't exist (better to download than skip)
        return False
