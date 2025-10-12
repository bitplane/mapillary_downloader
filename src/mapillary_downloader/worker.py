"""Worker process for parallel image download and conversion."""

from pathlib import Path
import requests
from requests.exceptions import RequestException
import time
from mapillary_downloader.exif_writer import write_exif_to_image
from mapillary_downloader.webp_converter import convert_to_webp


def download_and_convert_image(image_data, output_dir, quality, convert_webp, access_token):
    """Download and optionally convert a single image.

    This function is designed to run in a worker process.

    Args:
        image_data: Image metadata dict from API
        output_dir: Base output directory path
        quality: Quality level (256, 1024, 2048, original)
        convert_webp: Whether to convert to WebP
        access_token: Mapillary API access token

    Returns:
        Tuple of (image_id, bytes_downloaded, success, error_msg)
    """
    image_id = image_data["id"]
    quality_field = f"thumb_{quality}_url"

    try:
        # Get image URL
        image_url = image_data.get(quality_field)
        if not image_url:
            return (image_id, 0, False, f"No {quality} URL")

        # Determine output path
        output_dir = Path(output_dir)
        sequence_id = image_data.get("sequence")
        if sequence_id:
            img_dir = output_dir / sequence_id
            img_dir.mkdir(parents=True, exist_ok=True)
        else:
            img_dir = output_dir

        output_path = img_dir / f"{image_id}.jpg"

        # Download image
        session = requests.Session()
        session.headers.update({"Authorization": f"OAuth {access_token}"})

        max_retries = 10
        base_delay = 1.0
        bytes_downloaded = 0

        for attempt in range(max_retries):
            try:
                response = session.get(image_url, stream=True, timeout=60)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                break
            except RequestException as e:
                if attempt == max_retries - 1:
                    return (image_id, 0, False, f"Download failed: {e}")

                delay = base_delay * (2**attempt)
                time.sleep(delay)

        # Write EXIF metadata
        write_exif_to_image(output_path, image_data)

        # Convert to WebP if requested
        if convert_webp:
            webp_path = convert_to_webp(output_path)
            if not webp_path:
                return (image_id, bytes_downloaded, False, "WebP conversion failed")

        return (image_id, bytes_downloaded, True, None)

    except Exception as e:
        return (image_id, 0, False, str(e))
