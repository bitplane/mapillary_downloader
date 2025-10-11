"""Mapillary API client."""

import logging
import time
import requests
from requests.exceptions import RequestException

logger = logging.getLogger("mapillary_downloader")


class MapillaryClient:
    """Client for interacting with Mapillary API v4."""

    def __init__(self, access_token):
        """Initialize the client with an access token.

        Args:
            access_token: Mapillary API access token
        """
        self.access_token = access_token
        self.base_url = "https://graph.mapillary.com"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"OAuth {access_token}"})

    def get_user_images(self, username, bbox=None, limit=2000):
        """Get images uploaded by a specific user.

        Args:
            username: Mapillary username
            bbox: Optional bounding box [west, south, east, north]
            limit: Number of results per page (max 2000)

        Yields:
            Image data dictionaries
        """
        params = {
            "creator_username": username,
            "limit": limit,
            "fields": ",".join(
                [
                    "id",
                    "captured_at",
                    "compass_angle",
                    "computed_compass_angle",
                    "geometry",
                    "computed_geometry",
                    "altitude",
                    "computed_altitude",
                    "is_pano",
                    "sequence",
                    "camera_type",
                    "camera_parameters",
                    "make",
                    "model",
                    "exif_orientation",
                    "computed_rotation",
                    "height",
                    "width",
                    "thumb_256_url",
                    "thumb_1024_url",
                    "thumb_2048_url",
                    "thumb_original_url",
                ]
            ),
        }

        if bbox:
            params["bbox"] = ",".join(map(str, bbox))

        url = f"{self.base_url}/images"
        total_fetched = 0

        while url:
            max_retries = 10
            base_delay = 1.0

            for attempt in range(max_retries):
                try:
                    response = self.session.get(url, params=params)
                    response.raise_for_status()
                    break
                except RequestException as e:
                    if attempt == max_retries - 1:
                        raise

                    delay = base_delay * (2**attempt)
                    logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)

            data = response.json()
            images = data.get("data", [])
            total_fetched += len(images)
            logger.info(f"Fetched metadata for {total_fetched:,} images...")

            for image in images:
                yield image

            # Get next page URL
            url = data.get("paging", {}).get("next")
            params = None  # Don't send params on subsequent requests, URL has them

            # Rate limiting: 10,000 requests/minute for search API
            time.sleep(0.01)

    def download_image(self, image_url, output_path):
        """Download an image from a URL.

        Args:
            image_url: URL of the image to download
            output_path: Path to save the image

        Returns:
            Number of bytes downloaded if successful, 0 otherwise
        """
        max_retries = 10
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = self.session.get(image_url, stream=True)
                response.raise_for_status()

                total_bytes = 0
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        total_bytes += len(chunk)

                return total_bytes
            except RequestException as e:
                if attempt == max_retries - 1:
                    logger.error(f"Error downloading {image_url} after {max_retries} attempts: {e}")
                    return 0

                delay = base_delay * (2**attempt)
                logger.warning(f"Download failed (attempt {attempt + 1}/{max_retries}): {e}")
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
