#!/usr/bin/env python3
"""Scrape Mapillary location IDs for cities from geonames.

Reads cities.txt, searches Mapillary's location API for each one,
and builds up a {id: [type, name]} mapping in locations.json.

Resumable — skips cities already processed. Saves after each city.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Ensure the package is importable when run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mapillary_downloader.client_web import location_search
from mapillary_downloader.utils import get_cache_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CITIES_FILE = get_cache_dir() / "cities.txt"
OUTPUT_FILE = get_cache_dir() / "locations.json"
DELAY = 2.0
MAX_RETRIES = 3


def load_progress():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {"_city_index": 0, "locations": {}}


def save_progress(data):
    tmp = OUTPUT_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.rename(OUTPUT_FILE)


def search_with_retry(city):
    delay = DELAY
    for attempt in range(MAX_RETRIES):
        try:
            return location_search(city)
        except Exception as e:
            logger.warning("Attempt %d/%d for %r failed: %s", attempt + 1, MAX_RETRIES, city, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("All retries exhausted for %r", city)
                return None


def main():
    cities = CITIES_FILE.read_text().strip().splitlines()
    data = load_progress()
    start_index = data["_city_index"]

    logger.info(
        "Loaded %d existing locations, resuming from city %d/%d", len(data["locations"]), start_index, len(cities)
    )

    for i in range(start_index, len(cities)):
        city = cities[i]
        logger.info("[%d/%d] Searching: %s", i + 1, len(cities), city)

        results = search_with_retry(city)
        if results is not None:
            for r in results:
                loc_id = r["key"]
                if loc_id not in data["locations"]:
                    data["locations"][loc_id] = [r["type"], r["name"]]
                    logger.info("  + %s: %s (%s)", loc_id, r["name"], r["type"])

        data["_city_index"] = i + 1
        save_progress(data)
        time.sleep(DELAY)

    logger.info("Done. %d locations discovered.", len(data["locations"]))


if __name__ == "__main__":
    main()
