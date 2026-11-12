"""Tests for collection finalization helpers."""

import gzip
import json

from mapillary_downloader import paths
from mapillary_downloader.finalizer import compress_metadata, finalize_collection


def test_compress_metadata_preserves_legacy_filename(tmp_path):
    metadata_file = tmp_path / paths.METADATA_JSONL
    metadata_file.write_text(json.dumps({"id": "img1"}) + "\n")

    compress_metadata(tmp_path)

    compressed = tmp_path / paths.METADATA_JSONL_GZ
    assert not metadata_file.exists()
    assert compressed.exists()
    with gzip.open(compressed, "rt") as f:
        assert json.loads(f.readline()) == {"id": "img1"}


def test_finalize_chunk_payload_uses_final_name_for_metadata(tmp_path):
    state_dir = tmp_path / "cache" / "mapillary-testuser-original"
    payload_dir = state_dir / paths.PAYLOAD_DIR
    payload_dir.mkdir(parents=True)
    (state_dir / paths.METADATA_JSONL).write_text(json.dumps({"id": "img1", "captured_at": 1700000000000}) + "\n")
    (state_dir / paths.PROGRESS_JSON).write_text(json.dumps({"original": ["img1"]}))
    final_dir = tmp_path / "output" / "mapillary-testuser-original-2"

    finalize_collection(
        payload_dir,
        final_dir,
        convert_webp=False,
        tar_sequences=False,
        state_dir=state_dir,
        include_master_state=True,
    )

    assert final_dir.exists()
    assert (final_dir / ".meta" / "title" / "0").read_text() == "Mapillary images by testuser"
    assert not payload_dir.exists()


def test_finalize_resumes_existing_work_dir(tmp_path):
    payload_dir = tmp_path / "cache" / "mapillary-testuser-original" / paths.PAYLOAD_DIR
    payload_dir.mkdir(parents=True)
    work_dir = payload_dir.parent / "mapillary-testuser-original-2"
    work_dir.mkdir()

    (work_dir / "saved-image").write_bytes(b"downloaded data")
    final_dir = tmp_path / "output" / "mapillary-testuser-original-2"
    finalize_collection(
        payload_dir,
        final_dir,
        convert_webp=False,
        tar_sequences=False,
        include_master_state=False,
    )
    assert (final_dir / "saved-image").read_bytes() == b"downloaded data"
    assert not work_dir.exists()


def test_intermediate_chunk_metadata_has_archive_tags_without_count(tmp_path):
    payload_dir = tmp_path / "cache" / "mapillary-testuser-original" / paths.PAYLOAD_DIR
    payload_dir.mkdir(parents=True)
    final_dir = tmp_path / "output" / "mapillary-testuser-original"

    finalize_collection(
        payload_dir,
        final_dir,
        convert_webp=False,
        tar_sequences=False,
        include_master_state=False,
        chunk_title="Mapillary images by testuser (chunk)",
        chunk_description="Intermediate chunk without aggregate count.",
        chunk_username="testuser",
    )

    assert (final_dir / ".meta" / "collection" / "0").read_text() == "mapillary-images"
    assert (final_dir / ".meta" / "creator" / "0").read_text() == "testuser"
    assert "Contains " not in (final_dir / ".meta" / "description" / "0").read_text()
