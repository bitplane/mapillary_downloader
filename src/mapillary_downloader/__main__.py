"""CLI entry point."""

import argparse
import sys
from mapillary_downloader.client import MapillaryClient
from mapillary_downloader.downloader import MapillaryDownloader


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download your Mapillary data before it's gone"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Mapillary API access token"
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Your Mapillary username"
    )
    parser.add_argument(
        "--output",
        default="./mapillary_data",
        help="Output directory (default: ./mapillary_data)"
    )
    parser.add_argument(
        "--quality",
        choices=["256", "1024", "2048", "original"],
        default="original",
        help="Image quality to download (default: original)"
    )
    parser.add_argument(
        "--bbox",
        help="Bounding box: west,south,east,north"
    )

    args = parser.parse_args()

    bbox = None
    if args.bbox:
        try:
            bbox = [float(x) for x in args.bbox.split(",")]
            if len(bbox) != 4:
                raise ValueError
        except ValueError:
            print("Error: bbox must be four comma-separated numbers")
            sys.exit(1)

    try:
        client = MapillaryClient(args.token)
        downloader = MapillaryDownloader(client, args.output)
        downloader.download_user_data(args.username, args.quality, bbox)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
