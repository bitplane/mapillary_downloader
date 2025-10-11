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
mapillary-downloader --token YOUR_TOKEN --username YOUR_USERNAME --output ./downloads
```

| option        | because                               | default            |
| ------------- | ------------------------------------- | ------------------ |
| `--token`     | Your Mapillary API access token       | None (required)    |
| `--username`  | Your Mapillary username               | None (required)    |
| `--output`    | Output directory                      | `./mapillary_data` |
| `--quality`   | 256, 1024, 2048 or original           | `original`         |
| `--bbox`      | `west,south,east,north`               | `None`             |

The downloader will:

* 💾 Fetch all your uploaded images from Mapillary
* 📷 Download full-resolution images organized by sequence
* 📜 Inject EXIF metadata (GPS coordinates, camera info, timestamps,
  compass direction)
* 🛟 Save progress so you can safely resume if interrupted

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
