"""Internet Archive statistics for mapillary_downloader collections."""

import json
import logging
import re
import requests
from mapillary_downloader.utils import safe_json_save, http_get_with_retry, format_size
from mapillary_downloader.downloader import get_cache_dir

logger = logging.getLogger("mapillary_downloader")

CACHE_FILE = get_cache_dir() / ".stats.json"


def search_ia_collections(session):
    """Search IA for all mapillary_downloader collections.

    Args:
        session: requests.Session for connection pooling

    Returns:
        List of dicts with: identifier, description, item_size, collection
    """
    logger.info("Searching archive.org for mapillary_downloader collections...")

    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": "mapillary_downloader:*",
        "fl[]": ["identifier", "description", "item_size", "collection"],
        "rows": 10000,
        "output": "json",
    }

    response = http_get_with_retry(session, url, params=params, max_retries=3)
    data = response.json()

    collections = data["response"]["docs"]
    logger.info(f"Found {len(collections):,} collections on archive.org")

    return collections


def fetch_uploader(session, identifier):
    """Fetch uploader email from item metadata.

    Args:
        session: requests.Session for connection pooling
        identifier: IA item identifier

    Returns:
        Uploader email or None
    """
    url = f"https://archive.org/metadata/{identifier}/metadata/uploader"
    try:
        response = http_get_with_retry(session, url, max_retries=2)
        data = response.json()
        return data.get("result")
    except Exception:
        return None


def parse_collection_info(identifier):
    """Parse username, quality, webp from collection identifier.

    Returns:
        dict with username, quality, is_webp or None if invalid
    """
    match = re.match(r"mapillary-(.+)-(256|1024|2048|original)(?:-webp)?$", identifier)
    if match:
        return {"username": match.group(1), "quality": match.group(2), "is_webp": "-webp" in identifier}
    return None


def extract_image_count(description):
    """Extract image count from IA description field.

    Description format: "Contains 12,345 images in..."
    """
    if not description:
        return None

    match = re.search(r"Contains ([\d,]+) images", description)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def load_cache():
    """Load cached collection data.

    Returns:
        dict of {collection_id: {size, uploader, images, quality, username}}
    """
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
    return {}


def update_cache(ia_collections):
    """Update cache with new IA search results.

    Merges new collections into existing cache.

    Returns:
        Updated cache dict
    """
    cache = load_cache()

    for item in ia_collections:
        identifier = item.get("identifier")
        if not identifier:
            continue

        info = parse_collection_info(identifier)
        if not info:
            logger.debug(f"Skipping non-mapillary collection: {identifier}")
            continue

        # Parse item data
        size_bytes = item.get("item_size", 0)
        if isinstance(size_bytes, str):
            size_bytes = int(size_bytes)

        image_count = extract_image_count(item.get("description"))

        # Get IA collection(s) - can be a string or list
        ia_collection = item.get("collection", [])
        if isinstance(ia_collection, str):
            ia_collection = [ia_collection]

        # Preserve existing uploader if we have it cached
        existing = cache.get(identifier, {})

        # Update cache entry
        cache[identifier] = {
            "size": size_bytes,
            "uploader": existing.get("uploader"),  # Preserve cached uploader
            "images": image_count,
            "quality": info["quality"],
            "username": info["username"],
            "is_webp": info["is_webp"],
            "ia_collection": ia_collection,
        }

    # Save updated cache
    safe_json_save(CACHE_FILE, cache)
    logger.info(f"Updated cache with {len(cache):,} collections")

    return cache


def aggregate_stats(cache):
    """Aggregate statistics from cached collection data.

    Returns:
        dict with total and per-quality stats
    """
    stats = {
        "total": {"collections": 0, "total_images": 0, "unique_images": 0, "bytes": 0},
        "by_quality": {},
        "users": set(),
    }

    # Track images per user for deduplication
    user_images = {}  # {username: max_images_across_qualities}

    for collection_id, data in cache.items():
        images = data.get("images") or 0
        size = data.get("size") or 0
        quality = data.get("quality", "unknown")
        username = data.get("username")

        # Track user coverage
        if username:
            stats["users"].add(username)
            # Keep maximum image count across all qualities for this user
            if username not in user_images or images > user_images[username]:
                user_images[username] = images

        # Total stats (collections, total images, and bytes)
        stats["total"]["collections"] += 1
        stats["total"]["total_images"] += images
        stats["total"]["bytes"] += size

        # Per-quality stats
        if quality not in stats["by_quality"]:
            stats["by_quality"][quality] = {"collections": 0, "images": 0, "bytes": 0}

        stats["by_quality"][quality]["collections"] += 1
        stats["by_quality"][quality]["images"] += images
        stats["by_quality"][quality]["bytes"] += size

    # Unique images is sum of max images per user
    stats["total"]["unique_images"] = sum(user_images.values())

    return stats


def format_stats(session, stats, cache):
    """Format statistics as human-readable text.

    Args:
        session: requests.Session for connection pooling
        stats: Dict from aggregate_stats()
        cache: Dict of collection data

    Returns:
        Formatted string
    """
    TOTAL_MAPILLARY_IMAGES = 2_000_000_000  # 2 billion

    output = []
    output.append("=" * 70)
    output.append("Mapillary Downloader - Archive.org Statistics")
    output.append("=" * 70)
    output.append("")

    # Total stats
    total = stats["total"]
    unique_pct = (total["unique_images"] / TOTAL_MAPILLARY_IMAGES * 100) if total["unique_images"] else 0

    output.append(f"Total Collections: {total['collections']:,}")
    output.append(f"Total Users:       {len(stats['users']):,}")
    output.append(f"Total Images:      {total['total_images']:,}")
    output.append(f"Unique Images:     {total['unique_images']:,} ({unique_pct:.3f}% of 2B)")
    output.append(f"Total Size:        {format_size(total['bytes'])}")
    output.append("")

    # Per-quality breakdown
    output.append("By Quality:")
    output.append("-" * 70)

    # Sort by quality (original first, then numeric)
    qualities = sorted(stats["by_quality"].items(), key=lambda x: (x[0] != "original", x[0]))

    for quality, data in qualities:
        pct = (data["images"] / TOTAL_MAPILLARY_IMAGES * 100) if data["images"] else 0
        output.append(
            f"  {quality:8s}  {data['collections']:3d} collections  "
            f"{data['images']:12,d} images ({pct:.3f}%)  "
            f"{format_size(data['bytes']):>8s}"
        )

    output.append("")

    # Find items not in mapillary-images and fetch uploaders
    not_in_mapillary_images = []
    need_uploader_fetch = []

    for identifier, data in cache.items():
        ia_collections = data.get("ia_collection", [])
        if "mapillary-images" not in ia_collections:
            not_in_mapillary_images.append(identifier)
            if not data.get("uploader"):
                need_uploader_fetch.append(identifier)

    # Fetch missing uploaders
    if need_uploader_fetch:
        logger.info(f"Fetching uploader info for {len(need_uploader_fetch)} items...")
        for i, identifier in enumerate(need_uploader_fetch, 1):
            logger.info(f"  [{i}/{len(need_uploader_fetch)}] {identifier}")
            uploader = fetch_uploader(session, identifier)
            if uploader:
                cache[identifier]["uploader"] = uploader
        # Save updated cache with uploaders
        safe_json_save(CACHE_FILE, cache)

    # Group by uploader (only for items not in mapillary-images)
    by_uploader = {}
    for identifier in not_in_mapillary_images:
        uploader = cache[identifier].get("uploader") or "unknown"
        if uploader not in by_uploader:
            by_uploader[uploader] = {"items": [], "images": 0, "size": 0}
        by_uploader[uploader]["items"].append(identifier)
        by_uploader[uploader]["images"] += cache[identifier].get("images") or 0
        by_uploader[uploader]["size"] += cache[identifier].get("size") or 0

    # By uploader (only those with items outside mapillary-images)
    if by_uploader:
        output.append("Uploaders with items outside mapillary-images:")
        output.append("-" * 70)
        for uploader, data in sorted(by_uploader.items(), key=lambda x: -len(x[1]["items"])):
            output.append(
                f"  {uploader}: {len(data['items'])} items, " f"{data['images']:,} images, {format_size(data['size'])}"
            )
        output.append("")

    # Items not in mapillary-images, grouped by uploader
    if not_in_mapillary_images:
        output.append(f"Items NOT in mapillary-images ({len(not_in_mapillary_images)}):")
        output.append("-" * 70)
        for uploader, data in sorted(by_uploader.items(), key=lambda x: x[0].lower()):
            output.append(f"{uploader}:")
            for identifier in sorted(data["items"]):
                output.append(identifier)
            output.append("")
    else:
        output.append("All items are in mapillary-images collection!")
        output.append("")

    output.append(f"Cache: {CACHE_FILE}")

    return "\n".join(output)


def show_stats(refresh=True):
    """Show archive.org statistics for mapillary_downloader collections.

    Args:
        refresh: If True, fetch fresh data from IA. If False, use cache only.
    """
    session = requests.Session()

    if refresh:
        try:
            ia_collections = search_ia_collections(session)
            cache = update_cache(ia_collections)
        except Exception as e:
            logger.error(f"Failed to fetch IA data: {e}")
            logger.info("Using cached data...")
            cache = load_cache()
    else:
        cache = load_cache()

    if not cache:
        logger.error("No cached data and failed to fetch from IA")
        return

    stats = aggregate_stats(cache)
    print(format_stats(session, stats, cache))
