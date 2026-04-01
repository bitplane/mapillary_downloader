#!/usr/bin/env python3
"""Extract users from scraped leaderboards.

Usage:
    ./scripts/get-users.py                              # all users
    ./scripts/get-users.py --pattern 'United Kingdom$'  # UK users only

Output: headerless TSV, count<TAB>username, sorted by count ascending.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mapillary_downloader.utils import get_cache_dir

parser = argparse.ArgumentParser(description="Extract users from leaderboards")
parser.add_argument("--pattern", default=".*", help="Regex pattern to match against location name (default: .*)")
args = parser.parse_args()

leaderboards_file = get_cache_dir() / "leaderboards.json"
if not leaderboards_file.exists():
    print("No leaderboards.json found. Run scrape-leaderboards.py first.", file=sys.stderr)
    sys.exit(1)

data = json.load(open(leaderboards_file))
pattern = re.compile(args.pattern)

users = {}
for loc_id, entry in data.items():
    if not pattern.search(entry["name"]):
        continue
    for user_entry in entry["leaderboard"]["lifetime"]:
        username = user_entry["user"]["username"]
        count = user_entry["count"]
        if username not in users or count > users[username]:
            users[username] = count

for username, count in sorted(users.items(), key=lambda x: x[1]):
    print(f"{count}\t{username}")
