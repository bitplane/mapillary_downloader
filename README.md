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
# Set token via environment variable
export MAPILLARY_TOKEN=YOUR_TOKEN
mapillary-downloader --username SOME_USERNAME --output ./downloads

# Or pass token directly, and have it in your shell history 💩👀
mapillary-downloader --token YOUR_TOKEN --username SOME_USERNAME --output ./downloads
```

| option        | because                               | default            |
| ------------- | ------------------------------------- | ------------------ |
| `--username`  | Mapillary username                    | None (required)    |
| `--token`     | Mapillary API token (or env var)      | `$MAPILLARY_TOKEN` |
| `--output`    | Output directory                      | `./mapillary_data` |
| `--quality`   | 256, 1024, 2048 or original           | `original`         |
| `--bbox`      | `west,south,east,north`               | `None`             |
| `--webp`      | Convert to WebP (saves ~70% space)    | `False`            |
| `--workers`   | Number of parallel download workers   | Half of CPU count  |
| `--no-tar`    | Don't tar sequence directories        | `False`            |

The downloader will:

* 📷 Download a user's images organized by sequence
* 📜 Inject EXIF metadata (GPS coordinates, camera info, timestamps,
  compass direction)
* 🛟 Save progress so you can safely resume if interrupted
* 🗜️ Optionally convert to WebP to save space
* 📦 Tar sequence directories for faster uploads

## WebP Conversion

You'll need `cwebp` to use the `--webp` flag. So install it:

```bash
# Debian/Ubuntu
sudo apt install webp

# macOS
brew install webp
```

## Sequence Tarball Creation

By default, sequence directories are automatically tarred after download because
if they weren't, you'd spend more time setting up upload metadata than actually
uploading files to IA.

To keep individual files instead of creating tars, use the `--no-tar` flag:

```bash
mapillary-downloader --username WHOEVER --no-tar
```

## Internet Archive upload

I've written a bash tool to rip media then tag, queue, and upload to The
Internet Archive. The metadata is in the same format. If you copy completed
download dirs into the `4.ship` dir, they'll find their way into an
appropriately named item.

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
* [📀 rip](https://bitplane.net/dev/sh/rip

## License

WTFPL with one additional clause

1. Don't blame me

Do wtf you want, but don't blame me if it makes jokes about the size of your
disk drive.
