"""Tests for the downloader."""

import json
from unittest.mock import Mock, patch
from mapillary_downloader.downloader import MapillaryDownloader


def test_downloader_init(tmp_path):
    """Test downloader initialization."""
    mock_client = Mock()
    downloader = MapillaryDownloader(mock_client, tmp_path)

    assert downloader.client == mock_client
    assert downloader.output_dir == tmp_path
    assert tmp_path.exists()
    assert downloader.metadata_file == tmp_path / "metadata.jsonl"
    assert downloader.progress_file == tmp_path / "progress.json"


def test_load_progress_empty(tmp_path):
    """Test loading progress when no progress file exists."""
    mock_client = Mock()
    downloader = MapillaryDownloader(mock_client, tmp_path)

    assert len(downloader.downloaded) == 0


def test_load_progress_existing(tmp_path):
    """Test loading progress from existing file."""
    progress_file = tmp_path / "progress.json"
    progress_file.write_text(json.dumps({"downloaded": ["img1", "img2"]}))

    mock_client = Mock()
    downloader = MapillaryDownloader(mock_client, tmp_path)

    assert len(downloader.downloaded) == 2
    assert "img1" in downloader.downloaded
    assert "img2" in downloader.downloaded


def test_save_progress(tmp_path):
    """Test saving progress."""
    mock_client = Mock()
    downloader = MapillaryDownloader(mock_client, tmp_path)

    downloader.downloaded.add("img1")
    downloader.downloaded.add("img2")
    downloader._save_progress()

    progress_file = tmp_path / "progress.json"
    assert progress_file.exists()

    data = json.loads(progress_file.read_text())
    assert len(data["downloaded"]) == 2
    assert "img1" in data["downloaded"]


@patch("mapillary_downloader.downloader.generate_ia_metadata")
@patch("mapillary_downloader.downloader.tar_sequence_directories")
def test_download_user_data(mock_tar, mock_ia_meta, tmp_path, capsys):
    """Test downloading user data."""
    mock_client = Mock()
    mock_client.access_token = "test_token"

    images = [
        {
            "id": "img1",
            "sequence": "seq1",
            "thumb_original_url": "http://example.com/img1.jpg",
            "captured_at": 1234567890,
        },
        {
            "id": "img2",
            "sequence": "seq1",
            "thumb_original_url": "http://example.com/img2.jpg",
            "captured_at": 1234567891,
        },
    ]

    mock_client.get_user_images = Mock(return_value=iter(images))

    downloader = MapillaryDownloader(mock_client, tmp_path, username="testuser", quality="original", workers=1)

    # Mock _download_images_parallel to avoid actual worker execution
    downloader._download_images_parallel = Mock(return_value=(2, 200, 0))

    downloader.download_user_data()

    assert downloader._download_images_parallel.call_count == 1
    assert mock_tar.call_count == 1
    assert mock_ia_meta.call_count == 1

    assert (tmp_path / "mapillary-testuser-original" / "metadata.jsonl").exists()
    metadata_lines = (tmp_path / "mapillary-testuser-original" / "metadata.jsonl").read_text().strip().split("\n")
    assert len(metadata_lines) == 2


@patch("mapillary_downloader.downloader.generate_ia_metadata")
@patch("mapillary_downloader.downloader.tar_sequence_directories")
def test_download_user_data_with_sequence_organization(mock_tar, mock_ia_meta, tmp_path):
    """Test that images are organized by sequence."""
    mock_client = Mock()
    mock_client.access_token = "test_token"

    images = [{"id": "img1", "sequence": "seq1", "thumb_original_url": "http://example.com/img1.jpg"}]

    mock_client.get_user_images = Mock(return_value=iter(images))

    downloader = MapillaryDownloader(mock_client, tmp_path, username="testuser", quality="original", workers=1)
    downloader._download_images_parallel = Mock(return_value=(1, 100, 0))

    downloader.download_user_data()

    # Collection directory should be created
    assert (tmp_path / "mapillary-testuser-original").exists()
    assert downloader._download_images_parallel.call_count == 1


@patch("mapillary_downloader.downloader.generate_ia_metadata")
@patch("mapillary_downloader.downloader.tar_sequence_directories")
def test_download_user_data_skip_existing(mock_tar, mock_ia_meta, tmp_path):
    """Test that existing downloads are skipped."""
    mock_client = Mock()
    mock_client.access_token = "test_token"

    images = [
        {"id": "img1", "thumb_original_url": "http://example.com/img1.jpg"},
        {"id": "img2", "thumb_original_url": "http://example.com/img2.jpg"},
    ]

    mock_client.get_user_images = Mock(return_value=iter(images))

    downloader = MapillaryDownloader(mock_client, tmp_path, username="testuser", quality="original", workers=1)
    downloader.downloaded.add("img1")

    # Track which images are passed to download function
    downloaded_images = []

    def track_downloads(images, convert_webp):
        downloaded_images.extend(images)
        return (len(images), 100 * len(images), 0)

    downloader._download_images_parallel = track_downloads

    downloader.download_user_data()

    # Only img2 should be downloaded since img1 was already in downloaded set
    assert len(downloaded_images) == 1
    assert downloaded_images[0]["id"] == "img2"


@patch("mapillary_downloader.downloader.generate_ia_metadata")
@patch("mapillary_downloader.downloader.tar_sequence_directories")
def test_download_user_data_quality_selection(mock_tar, mock_ia_meta, tmp_path):
    """Test that quality parameter selects correct URL field."""
    mock_client = Mock()
    mock_client.access_token = "test_token"

    images = [
        {
            "id": "img1",
            "thumb_256_url": "http://example.com/256.jpg",
            "thumb_1024_url": "http://example.com/1024.jpg",
            "thumb_2048_url": "http://example.com/2048.jpg",
            "thumb_original_url": "http://example.com/orig.jpg",
        }
    ]

    mock_client.get_user_images = Mock(return_value=iter(images))

    downloader = MapillaryDownloader(mock_client, tmp_path, username="testuser", quality="1024", workers=1)
    downloader._download_images_parallel = Mock(return_value=(1, 100, 0))

    downloader.download_user_data()

    # Check that downloader was initialized with correct quality
    assert downloader.quality == "1024"
    assert downloader._download_images_parallel.call_count == 1
