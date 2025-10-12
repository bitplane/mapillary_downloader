# 🗺️ Mapillary Downloader

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
# Set token via environment variable (recommended)
export MAPILLARY_TOKEN=YOUR_TOKEN
mapillary-downloader --username YOUR_USERNAME --output ./downloads

# Or pass token directly
mapillary-downloader --token YOUR_TOKEN --username YOUR_USERNAME --output ./downloads
```

| option        | because                               | default            |
| ------------- | ------------------------------------- | ------------------ |
| `--token`     | Mapillary API token (or env var)      | `$MAPILLARY_TOKEN` |
| `--username`  | Mapillary username                    | None (required)    |
| `--output`    | Output directory                      | `./mapillary_data` |
| `--quality`   | 256, 1024, 2048 or original           | `original`         |
| `--bbox`      | `west,south,east,north`               | `None`             |
| `--webp`      | Convert to WebP (saves ~70% space)    | `False`            |
| `--workers`   | Number of parallel download workers   | CPU count          |

The downloader will:

* 💾 Fetch all your uploaded images from Mapillary
* 📷 Download full-resolution images organized by sequence
* 📜 Inject EXIF metadata (GPS coordinates, camera info, timestamps,
  compass direction)
* 🛟 Save progress so you can safely resume if interrupted
* 🗜️ Optionally convert to WebP format for massive space savings

## WebP Conversion

Use the `--webp` flag to convert images to WebP format after download:

```bash
mapillary-downloader --token YOUR_TOKEN --username YOUR_USERNAME --webp
```

This reduces storage by approximately 70% while preserving all EXIF metadata
including GPS coordinates. Requires the `cwebp` binary to be installed:

```bash
# Debian/Ubuntu
sudo apt install webp

# macOS
brew install webp
```

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

Do wtf you want, but don't blame me if it makes jokes about the size of your
disk drive.
