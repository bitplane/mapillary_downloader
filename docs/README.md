# Mapillary Downloader

Download your Mapillary data before it's gone.

## Installation

```bash
pip install mapillary-downloader
```

Or from source:

```bash
make install
```

## Usage

First, get your Mapillary API access token from https://www.mapillary.com/dashboard/developers

```bash
mapillary-download --token YOUR_TOKEN --username YOUR_USERNAME --output ./downloads
```

Options:
- `--token`: Your Mapillary API access token (required)
- `--username`: Your Mapillary username (required)
- `--output`: Output directory (default: ./mapillary_data)
- `--quality`: Image quality - 256, 1024, 2048, or original (default: original)
- `--bbox`: Bounding box filter: west,south,east,north

The downloader will:
- Fetch all your uploaded images from Mapillary
- Download full-resolution images organized by sequence
- Inject EXIF metadata (GPS coordinates, camera info, timestamps, compass direction)
- Save progress so you can safely resume if interrupted

## Features

- **Resume capability**: Interrupt and restart anytime - it tracks what's downloaded
- **EXIF restoration**: Restores GPS, camera, and timestamp metadata that Mapillary stripped
- **Atomic writes**: Progress tracking uses atomic file operations to prevent corruption
- **Organized output**: Images organized by sequence ID with metadata in JSONL format

## Development

```bash
make dev      # Setup dev environment
make test     # Run tests
make coverage # Run tests with coverage
```

## Links

* [🏠 home](https://bitplane.net/dev/python/mapillary_downloader)
* [📖 pydoc](https://bitplane.net/dev/python/mapillary_downloader/pydoc)
* [🐍 pypi](https://pypi.org/project/mapillary-downloader)
* [🐱 github](https://github.com/bitplane/mapillary_downloader)

## License

WTFPL with one additional clause

1. Don't blame me

Do wtf you want, but don't blame me when it breaks.
