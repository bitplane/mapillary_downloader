# 🗺️ Mapillary Downloader

Download your Mapillary data before it's gone.

## Installation

Installation is optional, you can prefix the command with `uvx` or `pipx` to
download and run it. Or if you're oldskool you can do:

```bash
pip install mapillary-downloader
```

## Usage

First, get your Mapillary API access token from
[the developer dashboard](https://www.mapillary.com/dashboard/developers)

```bash
# Set token via environment variable (recommended)
export MAPILLARY_TOKEN=YOUR_TOKEN
mapillary-downloader USERNAME1 USERNAME2 USERNAME3

# Or pass token directly, and have it in your shell history 💩👀
mapillary-downloader --token YOUR_TOKEN USERNAME1 USERNAME2

# Download to specific directory
mapillary-downloader --output ./downloads USERNAME1
```

| option          | because                                      | default            |
| --------------- | -------------------------------------------- | ------------------ |
| `usernames`     | One or more Mapillary usernames              | (required)         |
| `--token`       | Mapillary API token (or env var)             | `$MAPILLARY_TOKEN` |
| `--output`      | Output directory                             | `./mapillary_data` |
| `--quality`     | 256, 1024, 2048 or original                  | `original`         |
| `--bbox`        | `west,south,east,north`                      | `None`             |
| `--no-webp`     | Don't convert to WebP                        | `False`            |
| `--workers`     | Number of parallel download workers          | Half of CPU count  |
| `--no-tar`      | Don't tar sequence directories               | `False`            |
| `--no-check-ia` | Don't check if exists on Internet Archive    | `False`            |

The downloader will:

* 🏛️ Check Internet Archive to avoid duplicate downloads
* 📷 Download multiple users' images organized by sequence
* 📜 Inject EXIF metadata (GPS coordinates, camera info, timestamps,
  compass direction)
* 🗜️ Convert to WebP (by default) to save ~70% disk space
* 🛟 Save progress so you can safely resume if interrupted
* 📦 Tar sequence directories (by default) for faster uploads to Internet Archive

## WebP Conversion

You'll need the `cwebp` binary installed:

```bash
# Debian/Ubuntu
sudo apt install webp

# macOS
brew install webp
```

To disable WebP conversion and keep original JPEGs, use `--no-webp`:

```bash
mapillary-downloader --no-webp USERNAME
```

## Sequence Tarball Creation

By default, sequence directories are automatically tarred after download because
if they weren't, you'd spend more time setting up upload metadata than actually
uploading files to IA.

To keep individual files instead of creating tars, use the `--no-tar` flag.

## Internet Archive upload

I've written a bash tool to rip media then tag, queue, and upload to The
Internet Archive. The metadata is in the same format. If you symlink your
`./mapillary_data` dir to `rip`'s `4.ship` dir, they'll be queued for upload.

See inlay for details:

* [📀 rip](https://bitplane.net/dev/sh/rip)


## Development

```bash
make dev      # Setup dev environment
make test     # Run tests
make dist     # Build the distribution
make help     # See other make options
```

## Links

* [🏠 home](https://bitplane.net/dev/python/mapillary_downloader)
  * [📖 pydoc](https://bitplane.net/dev/python/mapillary_downloader/pydoc)
* [🐍 pypi](https://pypi.org/project/mapillary-downloader)
* [🐱 github](https://github.com/bitplane/mapillary_downloader)
* [📀 rip](https://bitplane.net/dev/sh/rip)

## License

WTFPL with one additional clause

1. Don't blame me

Do wtf you want, but don't blame me if it makes jokes about the size of your
disk drive.
