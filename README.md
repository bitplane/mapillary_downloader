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
| `--no-tar`    | Don't tar sequence directories        | `False`            |

The downloader will:

* 💾 Fetch all your uploaded images from Mapillary
* 📷 Download full-resolution images organized by sequence
* 📜 Inject EXIF metadata (GPS coordinates, camera info, timestamps,
  compass direction)
* 🛟 Save progress so you can safely resume if interrupted
* 🗜️ Optionally convert to WebP format for massive space savings
* 📦 Tar sequence directories for efficient Internet Archive uploads

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

## Sequence Tarball Creation

By default, sequence directories are automatically tarred after download to
optimize Internet Archive uploads. This reduces upload time and IA processing
overhead by bundling thousands of small files into single tar files per
sequence.

The tar files are uncompressed (since WebP/JPEG are already compressed) and use
relative paths for proper extraction. If a tar file already exists, collision
handling creates `.2.tar`, `.3.tar` suffixes automatically.

To keep individual files instead of creating tars, use the `--no-tar` flag:

```bash
mapillary-downloader --username YOUR_USERNAME --no-tar
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
