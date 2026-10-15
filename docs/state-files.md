# State Files

These filenames and directory names are durable operational state. Existing
archives, resumed jobs, and scraped discovery caches depend on them. Refactors
should centralize these names, but must not rename them without a compatibility
path.

## Collection State

- `mapillary-{username}-{quality}[-webp]/` - staging and final collection name.
- `metadata.jsonl` - uncompressed metadata cache while downloading.
- `metadata.jsonl.gz` - compressed metadata after finalization.
- `progress.json` - per-quality downloaded image IDs.
- `.api_cursor` - API pagination resume cursor.
- `chunks.json` - chunked output manifest.
- `payload/` - active image payload for capped/chunked runs.
- `__ia_thumb__.jpg` - Internet Archive item thumbnail.
- `download.log.{timestamp}` - per-run collection log.

## Discovery Caches

All discovery caches live under the `mapillary_downloader` XDG cache directory.

- `planet-latest_geonames.tsv.gz` - cached OSMNames dump.
- `locations.tsv` - location query variants.
- `locations.json` - scraped Mapillary location IDs.
- `leaderboards.json` - scraped Mapillary location leaderboards.
- `.stats.json` - cached archive.org collection statistics.

The discovery files are intentionally reused between runs to avoid repeating
large scraping jobs.

Profile totals can be added with `scripts/update-user-counts.py USER [USER ...]`.
Each lifetime entry keeps its regional `count`; optional `total_count` stores the
user's global profile image total. `get-users.py` prefers this total when present,
falling back to the largest regional count. The updater skips users whose total
is already cached, saves after each successful lookup, and pauses five seconds
between requests (`--delay` overrides this). Rerunning the same user list resumes
unfinished lookups. `--file` selects another leaderboard JSON for release work.
