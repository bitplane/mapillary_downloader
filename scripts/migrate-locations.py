#!/usr/bin/env python3
"""One-shot migration from cities.txt to locations.tsv, preserving scrape progress.

Reads the legacy files (cities.txt + locations.json with _city_index), regenerates
locations.tsv by streaming the OSMNames dump once, and rewrites locations.json with
the new _row_index=0 and the existing locations dict intact.

Rows already processed under the old scheme (index < old _city_index) have their
col 1 stripped — the native name was already queried, so next pass picks up from
the Latin variants. Row ordering for that prefix comes from the existing cities.txt
(authoritative), NOT from a fresh OSMNames sort, so row-index alignment is
guaranteed even if the geonames dump was regenerated between runs.

Run once, then delete. Not wired into the pipeline.
"""

import csv
import gzip
import json
import shutil
import sys

from mapillary_downloader.locations import get_variants
from mapillary_downloader.utils import get_cache_dir

GEONAMES_FILE = "planet-latest_geonames.tsv.gz"

cache_dir = get_cache_dir()
geonames_path = cache_dir / GEONAMES_FILE
cities_path = cache_dir / "cities.txt"
old_json_path = cache_dir / "locations.json"
new_tsv_path = cache_dir / "locations.tsv"


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


if not cities_path.exists():
    fail(f"Not found: {cities_path} — nothing to migrate from.")

if not old_json_path.exists():
    fail(f"Not found: {old_json_path} — nothing to migrate.")

if not geonames_path.exists():
    fail(f"Not found: {geonames_path} — run download-geonames.py first.")

if new_tsv_path.exists():
    fail(f"Already exists: {new_tsv_path} — refusing to overwrite.")

with open(old_json_path) as f:
    old_data = json.load(f)

old_index = old_data.get("_city_index", 0)
locations = old_data.get("locations", {})
print(f"Old _city_index = {old_index}, preserving {len(locations)} locations")

cities_lines = cities_path.read_text().splitlines()
print(f"cities.txt has {len(cities_lines)} rows; {old_index} processed, {len(cities_lines) - old_index} pending")

print("Streaming OSMNames dump...")
csv.field_size_limit(sys.maxsize)
rows_by_name = {}
with gzip.open(geonames_path, "rt") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for row in reader:
        if row["class"] == "place" and row["type"] == "city":
            name = row["name"]
            if name and name not in rows_by_name:
                rows_by_name[name] = row

print(f"Indexed {len(rows_by_name)} city rows from geonames")

# Build new TSV using cities.txt as authoritative ordering for the processed prefix
tmp_path = new_tsv_path.with_suffix(".tsv.tmp")
missing_in_geonames = 0
with open(tmp_path, "w", newline="") as out:
    writer = csv.writer(out, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

    # Processed prefix: strip col 1, keep variants only
    for name in cities_lines[:old_index]:
        row = rows_by_name.get(name)
        if row is None:
            missing_in_geonames += 1
            writer.writerow([])
            continue
        variants = get_variants(row)
        # Drop col 1 (native) — already queried in the old run
        writer.writerow(variants[1:])

    # Pending suffix: full rows, either from cities.txt+geonames or geonames-only
    # Use cities.txt ordering to preserve row count and behaviour; if new geonames
    # has cities not in old cities.txt, they get tacked on afterwards sorted.
    pending_names = cities_lines[old_index:]
    for name in pending_names:
        row = rows_by_name.get(name)
        if row is None:
            writer.writerow([name])
            continue
        writer.writerow(get_variants(row))

    # Any geonames cities that weren't in cities.txt at all (dump was updated)
    old_names = set(cities_lines)
    extra = sorted(n for n in rows_by_name if n not in old_names)
    for name in extra:
        writer.writerow(get_variants(rows_by_name[name]))
    if extra:
        print(f"Appended {len(extra)} new cities found in the current geonames dump")

tmp_path.replace(new_tsv_path)

# Rewrite locations.json: snapshot .bak, set _row_index=0, preserve locations
bak_path = old_json_path.with_suffix(".json.bak")
shutil.copy2(old_json_path, bak_path)
print(f"Snapshot: {bak_path}")

new_json = {"_row_index": 0, "locations": locations}
tmp_json = old_json_path.with_suffix(".json.tmp")
with open(tmp_json, "w") as f:
    json.dump(new_json, f, indent=2)
tmp_json.replace(old_json_path)

cities_path.unlink()

total_rows = len(cities_lines) + len(extra)
print(f"Wrote {new_tsv_path} with {total_rows} rows")
print(f"Rewrote {old_json_path} with _row_index=0")
print(f"Deleted {cities_path}")
if missing_in_geonames:
    print(f"Note: {missing_in_geonames} rows in processed prefix were not found in current geonames; emitted empty.")
