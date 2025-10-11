"""Tests for the downloader."""

import json
from unittest.mock import Mock
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


def test_download_user_data(tmp_path, capsys):
    """Test downloading user data."""
    mock_client = Mock()

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
    mock_client.download_image = Mock(return_value=True)

    downloader = MapillaryDownloader(mock_client, tmp_path)
    downloader.download_user_data("testuser")

    assert len(downloader.downloaded) == 2
    assert "img1" in downloader.downloaded
    assert "img2" in downloader.downloaded

    assert mock_client.download_image.call_count == 2

    assert (tmp_path / "metadata.jsonl").exists()
    metadata_lines = (tmp_path / "metadata.jsonl").read_text().strip().split("\n")
    assert len(metadata_lines) == 2


def test_download_user_data_with_sequence_organization(tmp_path):
    """Test that images are organized by sequence."""
    mock_client = Mock()

    images = [{"id": "img1", "sequence": "seq1", "thumb_original_url": "http://example.com/img1.jpg"}]

    mock_client.get_user_images = Mock(return_value=iter(images))
    mock_client.download_image = Mock(return_value=True)

    downloader = MapillaryDownloader(mock_client, tmp_path)
    downloader.download_user_data("testuser")

    seq_dir = tmp_path / "seq1"
    assert seq_dir.exists()

    call_args = mock_client.download_image.call_args[0]
    assert str(call_args[1]).endswith("seq1/img1.jpg")


def test_download_user_data_skip_existing(tmp_path):
    """Test that existing downloads are skipped."""
    mock_client = Mock()

    images = [
        {"id": "img1", "thumb_original_url": "http://example.com/img1.jpg"},
        {"id": "img2", "thumb_original_url": "http://example.com/img2.jpg"},
    ]

    mock_client.get_user_images = Mock(return_value=iter(images))
    mock_client.download_image = Mock(return_value=True)

    downloader = MapillaryDownloader(mock_client, tmp_path)
    downloader.downloaded.add("img1")

    downloader.download_user_data("testuser")

    assert mock_client.download_image.call_count == 1
    call_args = mock_client.download_image.call_args[0]
    assert "img2.jpg" in str(call_args[1])


def test_download_user_data_quality_selection(tmp_path):
    """Test that quality parameter selects correct URL field."""
    mock_client = Mock()

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
    mock_client.download_image = Mock(return_value=True)

    downloader = MapillaryDownloader(mock_client, tmp_path)
    downloader.download_user_data("testuser", quality="1024")

    call_args = mock_client.download_image.call_args[0]
    assert call_args[0] == "http://example.com/1024.jpg"
