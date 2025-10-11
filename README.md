# Mapillary Downloader

Download your Mapillary data before it's gone.

## Installation

```bash
make install
```

## Usage

First, get your Mapillary API access token from https://www.mapillary.com/dashboard/developers

```bash
source .venv/bin/activate
python -m mapillary_downloader --token YOUR_TOKEN --username YOUR_USERNAME --output ./downloads
```

## Development

```bash
make dev      # Setup dev environment
make test     # Run tests
make coverage # Run tests with coverage
```

## License

WTFPL + Warranty (Don't blame me)
