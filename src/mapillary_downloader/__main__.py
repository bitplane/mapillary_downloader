"""CLI entry point."""

import argparse
import os
import sys
from importlib.metadata import version
from mapillary_downloader.client import MapillaryClient
from mapillary_downloader.downloader import MapillaryDownloader
from mapillary_downloader.logging_config import setup_logging
from mapillary_downloader.webp_converter import check_cwebp_available


def main():
    """Main CLI entry point."""
    # Set up logging
    logger = setup_logging()

    parser = argparse.ArgumentParser(description="Download your Mapillary data before it's gone")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('mapillary-downloader')}",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("MAPILLARY_TOKEN"),
        help="Mapillary API access token (or set MAPILLARY_TOKEN env var)",
    )
    parser.add_argument("usernames", nargs="+", help="Mapillary username(s) to download")
    parser.add_argument("--output", default="./mapillary_data", help="Output directory (default: ./mapillary_data)")
    parser.add_argument(
        "--quality",
        choices=["256", "1024", "2048", "original"],
        default="original",
        help="Image quality to download (default: original)",
    )
    parser.add_argument("--bbox", help="Bounding box: west,south,east,north")
    parser.add_argument(
        "--no-webp",
        action="store_true",
        help="Don't convert to WebP (WebP conversion is enabled by default, saves ~70%% disk space)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: half of CPU cores)",
    )
    parser.add_argument(
        "--no-tar",
        action="store_true",
        help="Don't tar sequence directories (keep individual files)",
    )

    args = parser.parse_args()

    # Check for token
    if not args.token:
        logger.error("Error: Mapillary API token required. Use --token or set MAPILLARY_TOKEN environment variable")
        sys.exit(1)

    bbox = None
    if args.bbox:
        try:
            bbox = [float(x) for x in args.bbox.split(",")]
            if len(bbox) != 4:
                raise ValueError
        except ValueError:
            logger.error("Error: bbox must be four comma-separated numbers")
            sys.exit(1)

    # WebP is enabled by default, disabled with --no-webp
    convert_webp = not args.no_webp

    # Check for cwebp binary if WebP conversion is enabled
    if convert_webp:
        if not check_cwebp_available():
            logger.error(
                "Error: cwebp binary not found. Install webp package (e.g., apt install webp) or use --no-webp"
            )
            sys.exit(1)
        logger.info("WebP conversion enabled - images will be converted after download")

    try:
        client = MapillaryClient(args.token)

        # Process each username
        for username in args.usernames:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing user: {username}")
            logger.info(f"{'='*60}\n")

            downloader = MapillaryDownloader(
                client,
                args.output,
                username,
                args.quality,
                workers=args.workers,
                tar_sequences=not args.no_tar,
                convert_webp=convert_webp,
            )
            downloader.download_user_data(bbox=bbox, convert_webp=convert_webp)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
