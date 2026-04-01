#!/usr/bin/env python3
"""Download the OSMNames geonames planet dump if not already cached."""

import logging

import requests

from mapillary_downloader.utils import get_cache_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GEONAMES_URL = "https://github.com/geometalab/OSMNames/releases/download/v2.0/planet-latest_geonames.tsv.gz"
GEONAMES_FILE = "planet-latest_geonames.tsv.gz"


def download_geonames():
    path = get_cache_dir() / GEONAMES_FILE
    if path.exists():
        logger.info("Already cached: %s", path)
        return path

    logger.info("Downloading geonames from %s", GEONAMES_URL)
    resp = requests.get(GEONAMES_URL, stream=True)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    tmp = path.with_suffix(".tmp")
    downloaded = 0

    with open(tmp, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 / total
                logger.info("%.1f%% (%d / %d MB)", pct, downloaded >> 20, total >> 20)

    tmp.rename(path)
    logger.info("Saved to %s", path)
    return path


if __name__ == "__main__":
    path = download_geonames()
    print(f"Geonames file: {path}")
