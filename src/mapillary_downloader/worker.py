"""Worker process for parallel image download and conversion."""

import os
import tempfile
from pathlib import Path
import requests
from requests.exceptions import RequestException
from mapillary_downloader.exif_writer import write_exif_to_image
from mapillary_downloader.webp_converter import convert_to_webp


def worker_process(work_queue, result_queue, worker_id):
    """Worker process that pulls from queue and processes images.

    Args:
        work_queue: Queue to pull work items from
        result_queue: Queue to push results to
        worker_id: Unique worker identifier
    """
    # Create session once per worker (reuse HTTP connections)
    session = requests.Session()

    while True:
        work_item = work_queue.get()

        # None is the shutdown signal
        if work_item is None:
            break

        # Unpack work item
        image_data, output_dir, quality, convert_webp, access_token = work_item

        # Update session auth for this request
        session.headers.update({"Authorization": f"OAuth {access_token}"})

        # Process the image
        result = download_and_convert_image(image_data, output_dir, quality, convert_webp, session)

        # Push result back
        result_queue.put(result)


def download_and_convert_image(image_data, output_dir, quality, convert_webp, session):
    """Download and optionally convert a single image.

    This function is designed to run in a worker process.

    Args:
        image_data: Image metadata dict from API
        output_dir: Base output directory path
        quality: Quality level (256, 1024, 2048, original)
        convert_webp: Whether to convert to WebP
        session: requests.Session with auth already configured

    Returns:
        Tuple of (image_id, bytes_downloaded, success, error_msg)
    """
    image_id = image_data["id"]
    quality_field = f"thumb_{quality}_url"

    temp_dir = None
    try:
        # Get image URL
        image_url = image_data.get(quality_field)
        if not image_url:
            return (image_id, 0, False, f"No {quality} URL")

        # Determine final output directory
        output_dir = Path(output_dir)
        sequence_id = image_data.get("sequence")
        if sequence_id:
            img_dir = output_dir / sequence_id
            img_dir.mkdir(parents=True, exist_ok=True)
        else:
            img_dir = output_dir

        # If converting to WebP, use /tmp for intermediate JPEG
        # Otherwise write JPEG directly to final location
        if convert_webp:
            temp_dir = tempfile.mkdtemp(prefix="mapillary_downloader_")
            jpg_path = Path(temp_dir) / f"{image_id}.jpg"
            final_path = img_dir / f"{image_id}.webp"
        else:
            jpg_path = img_dir / f"{image_id}.jpg"
            final_path = jpg_path

        # Download image (using session passed from worker)
        bytes_downloaded = 0

        try:
            # 60 second timeout for entire download (connection + read)
            response = session.get(image_url, stream=True, timeout=60)
            response.raise_for_status()

            with open(jpg_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
        except RequestException as e:
            return (image_id, 0, False, f"Download failed: {e}")

        # Write EXIF metadata
        write_exif_to_image(jpg_path, image_data)

        # Convert to WebP if requested
        if convert_webp:
            webp_path = convert_to_webp(jpg_path, output_path=final_path, delete_original=False)
            if not webp_path:
                return (image_id, bytes_downloaded, False, "WebP conversion failed")

        # Set file mtime to captured_at timestamp for reproducibility
        if "captured_at" in image_data:
            # captured_at is in milliseconds, convert to seconds
            mtime = image_data["captured_at"] / 1000
            os.utime(final_path, (mtime, mtime))

        return (image_id, bytes_downloaded, True, None)

    except Exception as e:
        return (image_id, 0, False, str(e))
    finally:
        # Clean up temp directory if it was created
        if temp_dir and Path(temp_dir).exists():
            try:
                for file in Path(temp_dir).glob("*"):
                    file.unlink()
                Path(temp_dir).rmdir()
            except Exception:
                pass  # Best effort cleanup
