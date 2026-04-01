#!/usr/bin/env python3
"""Scrape Mapillary location IDs for cities from geonames.

Reads cities.txt, searches Mapillary's location API for each one,
and builds up a {id: [type, name]} mapping in locations.json.

Resumable — skips cities already processed. Saves after each city.
"""

import json
import logging
import time

from mapillary_downloader.client_web import call_with_retry, location_search
from mapillary_downloader.utils import get_cache_dir, safe_json_save

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CITIES_FILE = get_cache_dir() / "cities.txt"
OUTPUT_FILE = get_cache_dir() / "locations.json"
DELAY = 10.0


def load_progress():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {"_city_index": 0, "locations": {}}


def main():
    cities = CITIES_FILE.read_text().strip().splitlines()
    data = load_progress()
    start_index = data["_city_index"]

    logger.info(
        "Loaded %d existing locations, resuming from city %d/%d", len(data["locations"]), start_index, len(cities)
    )

    for i in range(start_index, len(cities)):
        if i > start_index:
            time.sleep(DELAY)

        city = cities[i]
        logger.info("[%d/%d] Searching: %s", i + 1, len(cities), city)

        results = call_with_retry(location_search, city)
        changed = False
        if results is not None:
            for r in results:
                loc_id = r["key"]
                if loc_id not in data["locations"]:
                    data["locations"][loc_id] = [r["type"], r["name"]]
                    logger.info("  + %s: %s (%s)", loc_id, r["name"], r["type"])
                    changed = True

        prev_index = data["_city_index"]
        data["_city_index"] = i + 1
        if changed or data["_city_index"] != prev_index:
            safe_json_save(OUTPUT_FILE, data)

    logger.info("Done. %d locations discovered.", len(data["locations"]))


if __name__ == "__main__":
    main()
