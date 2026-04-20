#!/usr/bin/env python3
"""Extract city query variants from the OSMNames TSV dump.

Writes locations.tsv to the cache directory. Each row is a city; columns are
query variants in priority order (native name, English Wikipedia title, first
clean-ASCII alt, first Latin-with-diacritics alt). Downstream, scrape-locations.py
tries them left-to-right.

Requires download-geonames.py to have been run first.
"""

import csv
import gzip
import sys

from mapillary_downloader.locations import get_variants
from mapillary_downloader.utils import get_cache_dir

GEONAMES_FILE = "planet-latest_geonames.tsv.gz"

cache_dir = get_cache_dir()
geonames_path = cache_dir / GEONAMES_FILE
output_path = cache_dir / "locations.tsv"

if not geonames_path.exists():
    print(f"Geonames file not found: {geonames_path}")
    print("Run download-geonames.py first.")
    sys.exit(1)

csv.field_size_limit(sys.maxsize)

rows_by_name = {}
with gzip.open(geonames_path, "rt") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for row in reader:
        if row["class"] == "place" and row["type"] == "city":
            name = row["name"]
            if name and name not in rows_by_name:
                rows_by_name[name] = row

names = sorted(rows_by_name)
tmp_path = output_path.with_suffix(".tsv.tmp")

with open(tmp_path, "w", newline="") as out:
    writer = csv.writer(out, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
    for name in names:
        writer.writerow(get_variants(rows_by_name[name]))

tmp_path.replace(output_path)
print(f"Wrote {len(names)} rows to {output_path}")
