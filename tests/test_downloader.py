"""Tests for the downloader."""

import json
import shutil
from unittest.mock import Mock, patch

import pytest

from mapillary_downloader.downloader import MapillaryDownloader
from mapillary_downloader.limits import DownloadLimits


def fake_finalize_collection(staging_dir, final_dir, *, convert_webp, tar_sequences, before_move=None, **kwargs):
    """Fast finalizer test double that preserves the staging-to-final contract."""
    if before_move:
        before_move()
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staging_dir), str(final_dir))


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


class InterruptAfterResultWorkerPool(FakeWorkerPool):
    """Worker pool that interrupts after one successful result is observed."""

    def __init__(self, worker_func, max_workers=16, monitoring_interval=10):
        super().__init__(worker_func, max_workers, monitoring_interval)
        self.returned_result = False

    def get_result(self, timeout=None):
        if self.results:
            self.returned_result = True
            return self.results.pop(0)
        if self.returned_result:
            raise KeyboardInterrupt
        return None


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
        patch("mapillary_downloader.downloader.finalize_collection", side_effect=fake_finalize_collection),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=None, min_free_space_bytes=None),
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


def test_download_user_data_saves_progress_on_interrupt(tmp_path):
    """A Ctrl-C after successful downloads should not lose in-memory progress."""
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

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", InterruptAfterResultWorkerPool),
        patch("mapillary_downloader.downloader.finalize_collection", side_effect=fake_finalize_collection),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=None, min_free_space_bytes=None),
        )

        with pytest.raises(KeyboardInterrupt):
            downloader.download_user_data()

    progress = json.loads((downloader.staging_dir / "progress.json").read_text())
    assert progress["original"] == ["img1"]
    assert InterruptAfterResultWorkerPool.instances[0].shutdown_called


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
        patch("mapillary_downloader.downloader.finalize_collection", side_effect=fake_finalize_collection),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=None, min_free_space_bytes=None),
        )

        downloader.download_user_data()

    pool = FakeWorkerPool.instances[0]
    assert pool.submitted == []
    assert downloader.downloaded == {"img1"}


def test_download_user_data_finalizes_when_no_images_downloadable(tmp_path):
    """A clean metadata run with missing image URLs should still create an output collection."""
    FakeWorkerPool.instances = []
    mock_client = Mock()
    mock_client.access_token = "test-token"
    mock_client.get_user_images.return_value = iter(
        [
            {
                "id": "img1",
                "captured_at": 1700000000000,
            }
        ]
    )

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
        patch("mapillary_downloader.downloader.finalize_collection", side_effect=fake_finalize_collection),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=None, min_free_space_bytes=None),
        )

        downloader.download_user_data()

    pool = FakeWorkerPool.instances[0]
    assert pool.submitted == []
    assert downloader.final_dir.exists()
    assert (downloader.final_dir / "metadata.jsonl").exists()


def test_download_user_data_closes_file_handler_when_final_dir_exists(tmp_path):
    """Skip paths should not leave per-user file log handlers attached."""
    mock_client = Mock()
    final_dir = tmp_path / "output" / "mapillary-testuser-original"
    final_dir.mkdir(parents=True)

    with patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            limits=DownloadLimits(max_size_bytes=None, min_free_space_bytes=None),
        )
        downloader.download_user_data()

    assert downloader.file_handler is None


def test_download_user_data_closes_file_handler_when_ia_exists(tmp_path):
    """IA skip paths should not leave per-user file log handlers attached."""
    mock_client = Mock()

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.check_ia_exists", return_value=True),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            limits=DownloadLimits(max_size_bytes=None, min_free_space_bytes=None),
        )
        downloader.download_user_data()

    assert downloader.file_handler is None


def test_chunked_download_uses_payload_dir_and_manifest(tmp_path):
    """Chunked mode keeps state in cache and moves only payload to output chunk."""
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
            },
            {
                "id": "img2",
                "captured_at": 1700000001000,
                "sequence": "seq2",
                "thumb_original_url": "http://example.com/img2.jpg",
            },
        ]
    )

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
        patch("mapillary_downloader.downloader.finalize_collection", side_effect=fake_finalize_collection),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=None, min_free_space_bytes=None, max_images=1),
        )

        downloader.download_user_data()

    pool = FakeWorkerPool.instances[0]
    assert pool.submitted[0][1] == str(downloader.staging_dir / "payload")
    assert (tmp_path / "output" / "mapillary-testuser-original").exists()
    assert (downloader.staging_dir / "chunks.json").exists()
    assert downloader.output_dir.exists()


def test_chunked_download_skips_existing_output_chunk(tmp_path):
    """Chunked mode should not overwrite manually-created existing chunks."""
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
    existing = tmp_path / "output" / "mapillary-testuser-original"
    existing.mkdir(parents=True)
    staging_dir = tmp_path / "cache" / "mapillary-testuser-original"
    staging_dir.mkdir(parents=True)
    (staging_dir / "chunks.json").write_text(
        json.dumps(
            {
                "mode": "chunked",
                "params": {"username": "testuser", "quality": "original", "is_webp": False, "bbox": None},
                "limits": {"max_size_bytes": 1, "max_images": None},
                "next_chunk": 1,
                "completed": [],
            }
        )
    )

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
        patch("mapillary_downloader.downloader.finalize_collection", side_effect=fake_finalize_collection),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=1, min_free_space_bytes=None),
        )
        downloader.download_user_data()

    assert existing.exists()
    assert (tmp_path / "output" / "mapillary-testuser-original-2").exists()


def test_fresh_chunked_download_skips_existing_legacy_collection(tmp_path):
    """Default chunking must not duplicate an already-complete legacy output as -2."""
    FakeWorkerPool.instances = []
    mock_client = Mock()
    mock_client.access_token = "test-token"
    existing = tmp_path / "output" / "mapillary-testuser-original"
    existing.mkdir(parents=True)

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=900_000_000_000, min_free_space_bytes=None),
        )
        downloader.download_user_data()

    assert existing.exists()
    assert not (tmp_path / "output" / "mapillary-testuser-original-2").exists()
    assert FakeWorkerPool.instances == []


def test_chunked_download_skips_when_manifest_final(tmp_path):
    """A manifest with a final chunk should stop future reruns."""
    FakeWorkerPool.instances = []
    mock_client = Mock()
    mock_client.access_token = "test-token"
    staging_dir = tmp_path / "cache" / "mapillary-testuser-original"
    staging_dir.mkdir(parents=True)
    for filename in ("metadata.jsonl", "metadata.jsonl.gz", ".api_cursor"):
        (staging_dir / filename).write_bytes(b"cached metadata")
    (staging_dir / "progress.json").write_text('{"original": ["img1"]}')
    (staging_dir / "chunks.json").write_text(
        json.dumps(
            {
                "mode": "chunked",
                "params": {"username": "testuser", "quality": "original", "is_webp": False, "bbox": None},
                "limits": {"max_size_bytes": 1, "max_images": None},
                "next_chunk": 2,
                "completed": [{"name": "mapillary-testuser-original", "images": 1, "bytes": 123, "final": True}],
            }
        )
    )

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=1, min_free_space_bytes=None),
        )
        downloader.download_user_data()

    assert FakeWorkerPool.instances == []

    for filename in ("metadata.jsonl", "metadata.jsonl.gz", "progress.json", ".api_cursor"):
        assert not (staging_dir / filename).exists()
    assert (staging_dir / "chunks.json").exists()
    mock_client.get_user_images.assert_not_called()


def test_chunked_manifest_reconciles_finalizing_output(tmp_path):
    """If a move completed before manifest update, startup should mark it completed."""
    FakeWorkerPool.instances = []
    mock_client = Mock()
    mock_client.access_token = "test-token"
    staging_dir = tmp_path / "cache" / "mapillary-testuser-original"
    staging_dir.mkdir(parents=True)
    for filename in ("metadata.jsonl", "metadata.jsonl.gz", ".api_cursor"):
        (staging_dir / filename).write_bytes(b"cached metadata")
    (staging_dir / "progress.json").write_text('{"original": ["img1"]}')
    output_dir = tmp_path / "output" / "mapillary-testuser-original"
    output_dir.mkdir(parents=True)
    (staging_dir / "chunks.json").write_text(
        json.dumps(
            {
                "mode": "chunked",
                "params": {"username": "testuser", "quality": "original", "is_webp": False, "bbox": None},
                "limits": {"max_size_bytes": 1, "max_images": None},
                "next_chunk": 1,
                "finalizing": {"name": "mapillary-testuser-original", "images": 7, "bytes": 456, "final": True},
                "completed": [],
            }
        )
    )

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=1, min_free_space_bytes=None),
        )
        downloader.download_user_data()

    manifest = json.loads((staging_dir / "chunks.json").read_text())
    assert manifest["completed"] == [{"name": "mapillary-testuser-original", "images": 7, "bytes": 456, "final": True}]
    assert "finalizing" not in manifest
    assert FakeWorkerPool.instances == []

    for filename in ("metadata.jsonl", "metadata.jsonl.gz", "progress.json", ".api_cursor"):
        assert not (staging_dir / filename).exists()
    assert (staging_dir / "chunks.json").exists()
    mock_client.get_user_images.assert_not_called()


@pytest.mark.parametrize("is_final", [False, True])
def test_chunked_manifest_resumes_interrupted_finalization(tmp_path, is_final):
    """Resume the renamed payload without starting download workers."""
    FakeWorkerPool.instances = []
    mock_client = Mock()
    mock_client.access_token = "test-token"
    staging_dir = tmp_path / "cache" / "mapillary-testuser-original"
    staging_dir.mkdir(parents=True)
    metadata = json.dumps({"id": "img1", "captured_at": 1700000000000}) + "\n"
    (staging_dir / "metadata.jsonl").write_text(metadata)
    (staging_dir / "progress.json").write_text('{"original": ["img1"]}')
    output_dir = tmp_path / "output" / "mapillary-testuser-original"
    work_dir = staging_dir / output_dir.name
    work_dir.mkdir()
    (work_dir / "saved-image").write_bytes(b"downloaded data")
    (staging_dir / "chunks.json").write_text(
        json.dumps(
            {
                "mode": "chunked",
                "params": {"username": "testuser", "quality": "original", "is_webp": False, "bbox": None},
                "limits": {"max_size_bytes": 1, "max_images": None},
                "next_chunk": 1,
                "finalizing": {"name": "mapillary-testuser-original", "images": 7, "bytes": 456, "final": is_final},
                "completed": [],
            }
        )
    )

    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            check_ia=False,
            tar_sequences=False,
            limits=DownloadLimits(max_size_bytes=1, min_free_space_bytes=None),
        )
        if is_final:
            downloader.download_user_data()
        else:
            downloader._init_chunk_manifest(None)
            assert downloader.chunk_manifest.next_chunk == 2
            downloader._close_file_handler()

    manifest = json.loads((staging_dir / "chunks.json").read_text())
    assert manifest["completed"] == [
        {"name": "mapillary-testuser-original", "images": 7, "bytes": 456, "final": is_final}
    ]
    assert "finalizing" not in manifest
    assert FakeWorkerPool.instances == []

    assert (output_dir / "saved-image").read_bytes() == b"downloaded data"
    assert not work_dir.exists()

    assert (staging_dir / "metadata.jsonl").exists() is not is_final
    assert (staging_dir / "progress.json").exists() is not is_final
    if is_final:
        import gzip

        with gzip.open(output_dir / "metadata.jsonl.gz", "rt") as archive:
            assert archive.read() == metadata


def test_baseline_bytes_counts_existing_payload_files(tmp_path):
    mock_client = Mock()
    with patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            limits=DownloadLimits(max_size_bytes=1, min_free_space_bytes=None),
        )
        (downloader.output_dir / "2024-01-01.tar").write_bytes(b"12345")
        (downloader.output_dir / "download.log.1").write_bytes(b"log")
        downloader.baseline_bytes = downloader._baseline_bytes()

    assert downloader.baseline_bytes == 5


@pytest.mark.parametrize("completion_save_fails", [False, True])
def test_completed_download_cleans_cache_only_after_manifest_saved(tmp_path, completion_save_fails):
    from contextlib import nullcontext

    from mapillary_downloader.chunks import ChunkManifest

    mock_client = Mock()
    mock_client.access_token = "test-token"
    mock_client.get_user_images.return_value = iter(
        [{"id": "img1", "captured_at": 1700000000000, "thumb_original_url": "http://example.com/img1.jpg"}]
    )
    with (
        patch("mapillary_downloader.downloader.get_cache_dir", return_value=tmp_path / "cache"),
        patch("mapillary_downloader.downloader.AdaptiveWorkerPool", FakeWorkerPool),
    ):
        downloader = MapillaryDownloader(
            mock_client,
            tmp_path / "output",
            username="testuser",
            quality="original",
            tar_sequences=False,
            check_ia=False,
            limits=DownloadLimits(max_size_bytes=900_000_000_000, min_free_space_bytes=None),
        )
        with (
            patch.object(ChunkManifest, "mark_completed", side_effect=OSError("save failed"))
            if completion_save_fails
            else nullcontext()
        ):
            if completion_save_fails:
                with pytest.raises(OSError, match="save failed"):
                    downloader.download_user_data()
            else:
                downloader.download_user_data()

        assert downloader.metadata_file.exists() == completion_save_fails
        assert downloader.progress_file.exists() == completion_save_fails
        assert (downloader.final_dir / "metadata.jsonl.gz").exists()
        manifest = json.loads(downloader.paths.chunks_file.read_text())
        assert bool(manifest["completed"]) is not completion_save_fails

        if not completion_save_fails:
            # Uploading/moving output away must not trigger another download.
            shutil.rmtree(downloader.final_dir)
            downloader.download_user_data()
            assert mock_client.get_user_images.call_count == 1
