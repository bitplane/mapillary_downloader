#!/usr/bin/env python3
"""Query location IDs from the scraped locations.json cache.

Usage:
    ./scripts/get-ids.py                          # all cities
    ./scripts/get-ids.py --pattern 'United Kingdom$'  # UK cities
    ./scripts/get-ids.py --type address --pattern 'Japan$'
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mapillary_downloader.utils import get_cache_dir

parser = argparse.ArgumentParser(description="Query location IDs from locations.json")
parser.add_argument("--pattern", default=".*", help="Regex pattern to match against name (default: .*)")
parser.add_argument("--type", default="city", help="Location type to filter (default: city)")
args = parser.parse_args()

data = json.load(open(get_cache_dir() / "locations.json"))
pattern = re.compile(args.pattern)

for loc_id, (loc_type, name) in sorted(data["locations"].items(), key=lambda x: x[1][1]):
    if loc_type == args.type and pattern.search(name):
        print(loc_id)
