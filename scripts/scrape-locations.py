#!/usr/bin/env python3
"""Scrape Mapillary location IDs for every variant row in locations.tsv.

Reads locations.tsv (one city per row, each row a tab-separated list of query
variants in priority order), searches Mapillary's location API for each row,
and merges matching IDs into {id: [type, name]} in locations.json.

Default mode: iterate variants left-to-right per row, stop on the first
non-empty result. Use --exhaustive to try every variant and union the results
(roughly 4x slower but recovers hits where Mapillary's index is patchy).

Resumable via `_row_index` in locations.json.
"""

import argparse
import csv
import json
import logging
import sys
import time

from mapillary_downloader.client_web import call_with_retry, location_search
from mapillary_downloader.utils import get_cache_dir, safe_json_save

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

LOCATIONS_TSV = get_cache_dir() / "locations.tsv"
OUTPUT_FILE = get_cache_dir() / "locations.json"
DELAY = 0.2


def load_progress():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {"_row_index": 0, "locations": {}}


def load_rows():
    with open(LOCATIONS_TSV, newline="") as f:
        return [row for row in csv.reader(f, delimiter="\t")]


def merge_results(results, locations):
    """Merge search results into the locations dict. Returns count added."""
    added = 0
    for r in results:
        loc_id = r["key"]
        if loc_id not in locations:
            locations[loc_id] = [r["type"], r["name"]]
            logger.info("  + %s: %s (%s)", loc_id, r["name"], r["type"])
            added += 1
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exhaustive",
        action="store_true",
        help="Try every variant per row and union results (slower, more thorough)",
    )
    args = parser.parse_args()

    if not LOCATIONS_TSV.exists():
        print(f"Not found: {LOCATIONS_TSV}", file=sys.stderr)
        print("Run extract-locations.py first.", file=sys.stderr)
        sys.exit(1)

    rows = load_rows()
    data = load_progress()
    start_index = data["_row_index"]

    logger.info(
        "Loaded %d existing locations, resuming from row %d/%d",
        len(data["locations"]),
        start_index,
        len(rows),
    )

    if args.exhaustive:
        remaining = len(rows) - start_index
        max_variants = max((len(r) for r in rows), default=0)
        est_seconds = remaining * max_variants * DELAY
        logger.warning(
            "Exhaustive mode: up to %d variants per row × %d rows × %.1fs ≈ %.1f hours",
            max_variants,
            remaining,
            DELAY,
            est_seconds / 3600,
        )

    for i in range(start_index, len(rows)):
        variants = [v for v in rows[i] if v]
        if not variants:
            data["_row_index"] = i + 1
            safe_json_save(OUTPUT_FILE, data)
            continue

        logger.info("[%d/%d] %s", i + 1, len(rows), variants[0])

        row_added = 0
        for variant in variants:
            if variant != variants[0]:
                time.sleep(DELAY)
                logger.info("  → variant: %s", variant)

            results = call_with_retry(location_search, variant)
            if results is None:
                # Retry-exhausted error: skip this variant; let operator investigate
                continue

            row_added += merge_results(results, data["locations"])

            if results and not args.exhaustive:
                break

        data["_row_index"] = i + 1
        safe_json_save(OUTPUT_FILE, data)

        if i + 1 < len(rows):
            time.sleep(DELAY)

    logger.info("Done. %d locations discovered.", len(data["locations"]))


if __name__ == "__main__":
    main()
