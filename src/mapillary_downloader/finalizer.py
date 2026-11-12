"""Finalize staged Mapillary collections into archive-ready output."""

import gzip
import logging
import shutil

from PIL import Image

from mapillary_downloader import paths
from mapillary_downloader.ia_meta import generate_ia_metadata
from mapillary_downloader.tar_sequences import tar_sequence_directories
from mapillary_downloader.utils import format_size

logger = logging.getLogger("mapillary_downloader")


def create_thumbnail(collection_dir, convert_webp):
    """Create a 256x256 JPEG thumbnail at the collection root for IA."""
    dest = collection_dir / paths.IA_THUMBNAIL
    ext = ".webp" if convert_webp else ".jpg"
    for path in collection_dir.rglob(f"*{ext}"):
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((256, 256))
            img.save(dest, "JPEG")
        logger.info("Thumbnail: %s", dest.name)
        return
    logger.warning("No images found for thumbnail")


def compress_metadata(collection_dir):
    """Gzip metadata.jsonl if present, preserving the existing output name."""
    metadata_file = collection_dir / paths.METADATA_JSONL
    if not metadata_file.exists():
        return

    original_size = metadata_file.stat().st_size
    if original_size <= 0:
        return

    logger.info("Compressing metadata.jsonl...")
    gzipped_file = collection_dir / paths.METADATA_JSONL_GZ

    with open(metadata_file, "rb") as f_in:
        with gzip.open(gzipped_file, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)

    compressed_size = gzipped_file.stat().st_size
    metadata_file.unlink()

    savings = 100 * (1 - compressed_size / original_size)
    logger.info(
        f"Compressed metadata: {format_size(original_size)} -> {format_size(compressed_size)} "
        f"({savings:.1f}% savings)"
    )


def write_meta_tag(meta_dir, tag, values):
    """Write one IA-style metadata tag."""
    tag_dir = meta_dir / tag
    tag_dir.mkdir(parents=True, exist_ok=True)

    if not isinstance(values, list):
        values = [values]

    for idx, value in enumerate(values):
        (tag_dir / str(idx)).write_text(str(value))


def write_simple_meta(collection_dir, title, description, *, username=None, source_url=None):
    """Write IA-style metadata tags without image-count phrasing."""
    meta_dir = collection_dir / ".meta"
    write_meta_tag(meta_dir, "title", title)
    write_meta_tag(meta_dir, "description", description)
    write_meta_tag(meta_dir, "subject", ["mapillary", "street-view", "computer-vision", "geospatial", "photography"])
    if username:
        write_meta_tag(meta_dir, "creator", username)
    write_meta_tag(meta_dir, "licenseurl", "https://creativecommons.org/licenses/by-sa/4.0/")
    write_meta_tag(meta_dir, "mediatype", "data")
    write_meta_tag(meta_dir, "collection", "mapillary-images")
    if source_url:
        write_meta_tag(meta_dir, "source", source_url)


def copy_master_state(state_dir, payload_dir):
    """Copy master state files into a final payload collection."""
    for name in (
        paths.METADATA_JSONL,
        paths.METADATA_JSONL_GZ,
        paths.PROGRESS_JSON,
        paths.API_CURSOR,
        paths.CHUNKS_JSON,
    ):
        src = state_dir / name
        if src.exists():
            shutil.copy2(src, payload_dir / name)

    for log_file in state_dir.glob(f"{paths.LOG_FILE_PREFIX}*"):
        if log_file.is_file():
            shutil.copy2(log_file, payload_dir / log_file.name)


def finalize_collection(
    staging_dir,
    final_dir,
    *,
    convert_webp,
    tar_sequences,
    before_move=None,
    state_dir=None,
    include_master_state=True,
    chunk_title=None,
    chunk_description=None,
    chunk_username=None,
):
    """Prepare a staged collection and move it to its final destination."""
    work_dir = staging_dir
    if staging_dir.name != final_dir.name:
        work_dir = staging_dir.parent / final_dir.name
        if not work_dir.exists():
            shutil.move(str(staging_dir), str(work_dir))
        else:
            logger.info("Resuming finalization in %s", work_dir)

    if state_dir and include_master_state:
        copy_master_state(state_dir, work_dir)

    create_thumbnail(work_dir, convert_webp)

    if tar_sequences:
        tar_sequence_directories(work_dir)

    if include_master_state:
        compress_metadata(work_dir)
        generate_ia_metadata(work_dir)
    elif chunk_title and chunk_description:
        source_url = f"https://www.mapillary.com/app/user/{chunk_username}" if chunk_username else None
        write_simple_meta(work_dir, chunk_title, chunk_description, username=chunk_username, source_url=source_url)

    if before_move:
        before_move()

    logger.info("Moving to final destination...")
    if final_dir.exists():
        raise FileExistsError(f"Destination already exists: {final_dir}")

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(work_dir), str(final_dir))
    logger.info(f"Done: {final_dir}")
