"""CLI entry point."""

import argparse
import sys
from mapillary_downloader.client import MapillaryClient
from mapillary_downloader.downloader import MapillaryDownloader
from mapillary_downloader.logging_config import setup_logging
from mapillary_downloader.webp_converter import check_cwebp_available


def main():
    """Main CLI entry point."""
    # Set up logging
    logger = setup_logging()

    parser = argparse.ArgumentParser(description="Download your Mapillary data before it's gone")
    parser.add_argument("--token", required=True, help="Mapillary API access token")
    parser.add_argument("--username", required=True, help="Your Mapillary username")
    parser.add_argument("--output", default="./mapillary_data", help="Output directory (default: ./mapillary_data)")
    parser.add_argument(
        "--quality",
        choices=["256", "1024", "2048", "original"],
        default="original",
        help="Image quality to download (default: original)",
    )
    parser.add_argument("--bbox", help="Bounding box: west,south,east,north")
    parser.add_argument(
        "--webp",
        action="store_true",
        help="Convert images to WebP format (saves ~70%% disk space, requires cwebp binary)",
    )

    args = parser.parse_args()

    bbox = None
    if args.bbox:
        try:
            bbox = [float(x) for x in args.bbox.split(",")]
            if len(bbox) != 4:
                raise ValueError
        except ValueError:
            logger.error("Error: bbox must be four comma-separated numbers")
            sys.exit(1)

    # Check for cwebp binary if WebP conversion is requested
    if args.webp:
        if not check_cwebp_available():
            logger.error("Error: cwebp binary not found. Install webp package (e.g., apt install webp)")
            sys.exit(1)
        logger.info("WebP conversion enabled - images will be converted after download")

    try:
        client = MapillaryClient(args.token)
        downloader = MapillaryDownloader(client, args.output, args.username, args.quality)
        downloader.download_user_data(bbox=bbox, convert_webp=args.webp)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
