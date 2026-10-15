#!/usr/bin/env python3
"""Cache global profile totals alongside regional leaderboard counts."""

import argparse
import json
import logging
import math
import time

from mapillary_downloader import paths
from mapillary_downloader.client_web import call_with_retry, get_profile_image_count
from mapillary_downloader.utils import get_cache_dir, safe_json_save

logger = logging.getLogger(__name__)


def lifetime_entries(data, username):
    """Find every lifetime appearance, leaving weekly/monthly counts intact."""
    return [
        entry
        for location in data.values()
        for entry in location["leaderboard"]["lifetime"]
        if entry["user"]["username"] == username
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("usernames", nargs="+", help="Users already present in the leaderboard cache")
    parser.add_argument("--delay", type=float, default=5.0, help="Seconds between users (default: 5)")
    parser.add_argument("--file", type=str, help="Leaderboard JSON (default: the local cache)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.delay) or args.delay < 0:
        parser.error("--delay must be a finite, non-negative number")
    filename = args.file or get_cache_dir() / paths.LEADERBOARDS_JSON
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        with open(filename) as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        logger.error("Cannot read leaderboard cache: %s", exc)
        return 1

    failed = False
    requested = False
    for username in dict.fromkeys(args.usernames):
        entries = lifetime_entries(data, username)
        if not entries:
            logger.error("%s is not in the lifetime leaderboards; skipping", username)
            failed = True
            continue
        if any("total_count" in entry for entry in entries):
            logger.info("%s: total already cached; skipping", username)
            continue
        if requested:
            time.sleep(args.delay)
        requested = True
        count = call_with_retry(get_profile_image_count, username)
        if count is None:
            failed = True
            continue
        # Preserve changes made while the profile request was in flight.
        with open(filename) as f:
            data = json.load(f)
        entries = lifetime_entries(data, username)
        if not entries:
            logger.error("%s disappeared from the cache; skipping", username)
            failed = True
            continue
        for entry in entries:
            entry["total_count"] = count
        safe_json_save(filename, data)
        logger.info("%s: %d total images", username, count)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
