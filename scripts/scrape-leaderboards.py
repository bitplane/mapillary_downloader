#!/usr/bin/env python3
"""Scrape Mapillary leaderboards for a list of location IDs.

Usage:
    ./scripts/get-ids.py --pattern 'United Kingdom$' | xargs ./scripts/scrape-leaderboards.py
    ./scripts/scrape-leaderboards.py 812057 608447 805930
"""

import json
import logging
import sys
import time

from mapillary_downloader.client_web import call_with_retry, get_leaderboard
from mapillary_downloader.utils import get_cache_dir, safe_json_save

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_FILE = get_cache_dir() / "leaderboards.json"
LOCATIONS_FILE = get_cache_dir() / "locations.json"
DELAY = 1.0


def load_data():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {}


def load_locations():
    if LOCATIONS_FILE.exists():
        with open(LOCATIONS_FILE) as f:
            return json.load(f).get("locations", {})
    return {}


def main():
    if len(sys.argv) < 2:
        print("Usage: scrape-leaderboards.py ID [ID ...]", file=sys.stderr)
        sys.exit(1)

    loc_ids = sys.argv[1:]
    locations = load_locations()
    data = load_data()

    logger.info("Got %d IDs to process, %d already scraped", len(loc_ids), len(data))

    last_mtime = OUTPUT_FILE.stat().st_mtime if OUTPUT_FILE.exists() else 0

    first = True
    for i, loc_id in enumerate(loc_ids):
        if loc_id in data:
            continue

        if not first:
            time.sleep(DELAY)
        first = False

        # Reload if file was modified externally
        if OUTPUT_FILE.exists():
            mtime = OUTPUT_FILE.stat().st_mtime
            if mtime != last_mtime:
                data = load_data()
                last_mtime = mtime
                if loc_id in data:
                    continue

        loc_info = locations.get(loc_id, ["unknown", f"ID {loc_id}"])
        name = loc_info[1]
        logger.info("[%d/%d] Fetching leaderboard: %s (%s)", i + 1, len(loc_ids), name, loc_id)

        leaderboard = call_with_retry(get_leaderboard, loc_id)
        if leaderboard is not None:
            users = sum(len(leaderboard[k]) for k in ("lifetime", "month", "week"))
            data[loc_id] = {"name": name, "leaderboard": leaderboard}
            safe_json_save(OUTPUT_FILE, data)
            last_mtime = OUTPUT_FILE.stat().st_mtime
            logger.info("  %d user entries", users)

    logger.info("Done. %d leaderboards scraped.", len(data))


if __name__ == "__main__":
    main()
