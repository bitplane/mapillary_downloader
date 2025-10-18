"""Tests for the downloader."""

import json
from unittest.mock import Mock, patch
from mapillary_downloader.downloader import MapillaryDownloader


def test_downloader_init(tmp_path):
    """Test downloader initialization."""
    mock_client = Mock()
    # Mock get_cache_dir to use tmp_path for testing
    with patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path):
        downloader = MapillaryDownloader(mock_client, tmp_path)

        assert downloader.client == mock_client
        assert downloader.staging_dir == tmp_path / "download"
        assert downloader.final_dir == tmp_path
        assert downloader.output_dir == downloader.staging_dir
        assert downloader.staging_dir.exists()
        assert downloader.metadata_file == downloader.staging_dir / "metadata.jsonl"
        assert downloader.progress_file == downloader.staging_dir / "progress.json"


def test_load_progress_empty(tmp_path):
    """Test loading progress when no progress file exists."""
    mock_client = Mock()
    with patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path):
        downloader = MapillaryDownloader(mock_client, tmp_path)

        assert len(downloader.downloaded) == 0


def test_load_progress_existing(tmp_path):
    """Test loading progress from existing file."""
    staging_dir = tmp_path / "download"
    staging_dir.mkdir()
    progress_file = staging_dir / "progress.json"
    progress_file.write_text(json.dumps({"downloaded": ["img1", "img2"]}))

    mock_client = Mock()
    with patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path):
        downloader = MapillaryDownloader(mock_client, tmp_path)

        assert len(downloader.downloaded) == 2
        assert "img1" in downloader.downloaded
        assert "img2" in downloader.downloaded


def test_save_progress(tmp_path):
    """Test saving progress."""
    mock_client = Mock()
    with patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path):
        downloader = MapillaryDownloader(mock_client, tmp_path, username="testuser", quality="original")

        downloader.downloaded.add("img1")
        downloader.downloaded.add("img2")
        downloader._save_progress()

        progress_file = downloader.staging_dir / "progress.json"
        assert progress_file.exists()

        data = json.loads(progress_file.read_text())
        # New format is per-quality: {"original": [...], "1024": [...]}
        assert len(data["original"]) == 2
        assert "img1" in data["original"]


# NOTE: Integration tests for download_user_data are disabled during the workers branch rewrite.
# These tests were testing the old _download_images_parallel implementation which has been
# replaced with the new queue-based worker pool architecture. They need to be rewritten to
# test the new architecture, which is more complex to mock since it involves multiprocessing.
#
# The new architecture uses:
# - AdaptiveWorkerPool with multiprocessing workers
# - Streaming metadata reader
# - Parallel API fetch + download
#
# These will be reimplemented as proper integration tests once the architecture is stable.
