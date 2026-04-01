#!/usr/bin/env python3
"""Extract unique city names from the geonames TSV dump.

Writes cities.txt to the cache directory.
Requires download-geonames.py to have been run first.
"""

import csv
import gzip
import sys

from mapillary_downloader.utils import get_cache_dir

GEONAMES_FILE = "planet-latest_geonames.tsv.gz"

cache_dir = get_cache_dir()
geonames_path = cache_dir / GEONAMES_FILE
output_path = cache_dir / "cities.txt"

if not geonames_path.exists():
    print(f"Geonames file not found: {geonames_path}")
    print("Run download-geonames.py first.")
    sys.exit(1)

cities = set()
csv.field_size_limit(sys.maxsize)

with gzip.open(geonames_path, "rt") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for row in reader:
        if row["class"] == "place" and row["type"] == "city":
            cities.add(row["name"])

cities = sorted(cities)
output_path.write_text("\n".join(cities) + "\n")
print(f"Wrote {len(cities)} cities to {output_path}")
