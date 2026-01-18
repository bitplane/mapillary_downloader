# 🗺️ Mapillary Downloader

Download your Mapillary data before it's gone.

## ▶️ Installation

Installation is optional, you can prefix the command with `uvx` or `pipx` to
download and run it. Or if you're oldskool you can do:

```bash
pip install mapillary-downloader
```

## ❓ Usage

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
| `--max-workers` | Maximum number of parallel download workers  | CPU count          |
| `--no-tar`      | Don't tar bucket directories                 | `False`            |
| `--no-check-ia` | Don't check if exists on Internet Archive    | `False`            |

The downloader will:

* 🏛️ Check Internet Archive to avoid duplicate downloads
* 📷 Download multiple users' images organized by sequence
* 📜 Inject EXIF metadata (GPS coordinates, camera info, timestamps,
     compass direction) and XMP data for panoramas.
* 🗜️ Convert to WebP (by default) to save ~70% disk space
* 🛟 Save progress every 5 minutes so you can safely resume if interrupted
     ()
* 📦 Tar sequence directories (by default) for faster uploads to Internet
     Archive

## 🖼️ WebP Conversion

You'll need the `cwebp` binary installed:

```bash
# Debian/Ubuntu
sudo apt install webp

# macOS
brew install webp
```

To disable WebP conversion and keep original JPEGs, use `--no-webp`:

## 📦 Tarballs

Images are organized by capture date (YYYY-MM-DD) for incremental archiving:

```
mapillary-username-quality/
  2024-01-15/
    abc123/
      image1.webp
      image2.webp
    bcd456/
      image3.webp
  2024-01-16/
    def789/
      image4.webp
```

By default, these date directories are automatically tarred after download
(`2024-01-15.tar`, `2024-01-16.tar`, etc.). Reasons:

* ⤴️ Incremental uploads. Add more to a collection. Well, eventually anyway.
     This won't work yet unless you delete the jsonl file and start again.
* 📂 Fewer files - ~365 days/year × 10 years = 3,650 tars max. IA only want
     5k items per collection
* 🧨 Avoids blowing up IA's derive workers. We don't want Brewster's computers
     to create thumbs for 2 billion images.
* 💾 I like to have a few inodes available for things other than this. I'm sure
     you do too.

To keep individual files instead of creating tars, use the `--no-tar` flag.

## 🏛️ Internet Archive upload

I've written a bash tool to rip media then tag, queue, and upload to The
Internet Archive. The metadata is in the same format. If you symlink your
`./mapillary_data` dir to `rip`'s `4.ship` dir, they'll be queued for upload.

See inlay for details:

* [📀 rip](https://bitplane.net/dev/sh/rip)

## 📊 Stats

To see overall project progress, or an estimate, use `--stats`

## 🚧 Development

```bash
make dev      # Setup dev environment
make test     # Run tests. Note: requires `exiftool`
make dist     # Build the distribution
make help     # See other make options
```

## 🔗 Links

* [🏠 home](https://bitplane.net/dev/python/mapillary_downloader)
  * [📖 pydoc](https://bitplane.net/dev/python/mapillary_downloader/pydoc)
* [🐍 pypi](https://pypi.org/project/mapillary-downloader)
* [🐱 github](https://github.com/bitplane/mapillary_downloader)
* [📀 rip](https://bitplane.net/dev/sh/rip)

## ⚖️ License

WTFPL with one additional clause

1. Don't blame me

Do wtf you want, but don't blame me if it makes jokes about the size of your
disk.
