"""Tests for the downloader."""

import json
from unittest.mock import Mock, patch
from mapillary_downloader.downloader import MapillaryDownloader


class FakeWorkerPool:
    """Synchronous worker-pool test double for downloader orchestration tests."""

    instances = []

    def __init__(self, worker_func, max_workers=16, monitoring_interval=10):
        self.worker_func = worker_func
        self.max_workers = max_workers
        self.monitoring_interval = monitoring_interval
        self.current_workers = 1
        self.started = False
        self.shutdown_called = False
        self.submitted = []
        self.results = []
        self.throughput_checks = []
        FakeWorkerPool.instances.append(self)

    def start(self):
        self.started = True

    def submit(self, work_item):
        if work_item is None:
            return
        self.submitted.append(work_item)
        image = work_item[0]
        self.results.append((image["id"], 123, True, None))

    def get_result(self, timeout=None):
        if self.results:
            return self.results.pop(0)
        return None

    def check_throughput(self, total_processed):
        self.throughput_checks.append(total_processed)

    def shutdown(self, timeout=2):
        self.shutdown_called = True


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
    staging_dir = tmp_path / "mapillary-testuser-original"
    staging_dir.mkdir()
    progress_file = staging_dir / "progress.json"
    progress_file.write_text(json.dumps({"original": ["img1", "img2"], "1024": ["other"]}))

    mock_client = Mock()
    with patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path):
        downloader = MapillaryDownloader(mock_client, tmp_path, username="testuser", quality="original")

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


def test_download_user_data_submits_metadata_to_worker_pool(tmp_path):
    """Test download orchestration without spawning multiprocessing workers."""
    FakeWorkerPool.instances = []
    mock_client = Mock()
    mock_client.access_token = "test-token"
    mock_client.get_user_images.return_value = iter(
        [
            {
                "id": "img1",
                "captured_at": 1700000000000,
                "sequence": "seq1",
                "thumb_original_url": "http://example.com/img1.jpg",
            }
        ]
    )

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
        patch.object(MapillaryDownloader, "_create_thumbnail"),
        patch("mapillary_downloader.downloader.generate_ia_metadata", return_value=True),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
        )

        downloader.download_user_data()

    pool = FakeWorkerPool.instances[0]
    assert pool.started
    assert pool.shutdown_called
    assert len(pool.submitted) == 1

    image, output_dir, quality, convert_webp, access_token = pool.submitted[0]
    assert image["id"] == "img1"
    assert output_dir == str(downloader.staging_dir)
    assert quality == "original"
    assert not convert_webp
    assert access_token == "test-token"

    assert "img1" in downloader.downloaded
    assert downloader.final_dir.exists()


def test_download_user_data_skips_completed_progress_entries(tmp_path):
    """Test that existing progress prevents duplicate worker submissions."""
    FakeWorkerPool.instances = []
    mock_client = Mock()
    mock_client.access_token = "test-token"
    mock_client.get_user_images.return_value = iter(
        [
            {
                "id": "img1",
                "captured_at": 1700000000000,
                "thumb_original_url": "http://example.com/img1.jpg",
            }
        ]
    )

    staging_dir = tmp_path / "cache" / "mapillary-testuser-original"
    staging_dir.mkdir(parents=True)
    (staging_dir / "progress.json").write_text(json.dumps({"original": ["img1"]}))

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
        patch.object(MapillaryDownloader, "_create_thumbnail"),
        patch("mapillary_downloader.downloader.generate_ia_metadata", return_value=True),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
        )

        downloader.download_user_data()

    pool = FakeWorkerPool.instances[0]
    assert pool.submitted == []
    assert downloader.downloaded == {"img1"}
