#!/usr/bin/env python3
"""Scrape Mapillary leaderboards for a list of location IDs.

Usage:
    ./scripts/get-ids.py --pattern 'United Kingdom$' | xargs ./scripts/scrape-leaderboards.py
    ./scripts/scrape-leaderboards.py 812057 608447 805930
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import requests

from mapillary_downloader.client_web import get_leaderboard
from mapillary_downloader.utils import get_cache_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_FILE = get_cache_dir() / "leaderboards.json"
LOCATIONS_FILE = get_cache_dir() / "locations.json"
DELAY = 5.0
MAX_RETRIES = 3


def load_data():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {}


def save_data(data):
    tmp = OUTPUT_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.rename(OUTPUT_FILE)


def load_locations():
    if LOCATIONS_FILE.exists():
        with open(LOCATIONS_FILE) as f:
            return json.load(f).get("locations", {})
    return {}


def fetch_with_retry(loc_id):
    delay = DELAY
    for attempt in range(MAX_RETRIES):
        try:
            return get_leaderboard(loc_id)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                logger.error("Got 400 for %s, stopping.", loc_id)
                sys.exit(1)
            logger.warning("Attempt %d/%d for %s failed: %s", attempt + 1, MAX_RETRIES, loc_id, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("All retries exhausted for %s", loc_id)
                return None
        except Exception as e:
            logger.warning("Attempt %d/%d for %s failed: %s", attempt + 1, MAX_RETRIES, loc_id, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("All retries exhausted for %s", loc_id)
                return None


def main():
    if len(sys.argv) < 2:
        print("Usage: scrape-leaderboards.py ID [ID ...]", file=sys.stderr)
        sys.exit(1)

    loc_ids = sys.argv[1:]
    locations = load_locations()
    data = load_data()

    logger.info("Got %d IDs to process, %d already scraped", len(loc_ids), len(data))

    last_mtime = OUTPUT_FILE.stat().st_mtime if OUTPUT_FILE.exists() else 0

    for i, loc_id in enumerate(loc_ids):
        if loc_id in data:
            continue

        loc_info = locations.get(loc_id, ["unknown", f"ID {loc_id}"])
        name = loc_info[1]
        logger.info("[%d/%d] Fetching leaderboard: %s (%s)", i + 1, len(loc_ids), name, loc_id)

        leaderboard = fetch_with_retry(loc_id)
        if leaderboard is not None:
            users = sum(len(leaderboard[k]) for k in ("lifetime", "month", "week"))
            data[loc_id] = {"name": name, "leaderboard": leaderboard}
            save_data(data)
            logger.info("  %d user entries", users)

        time.sleep(DELAY)

        # Reload if file was modified externally
        if OUTPUT_FILE.exists():
            mtime = OUTPUT_FILE.stat().st_mtime
            if mtime != last_mtime:
                data = load_data()
                last_mtime = mtime

    logger.info("Done. %d leaderboards scraped.", len(data))


if __name__ == "__main__":
    main()
