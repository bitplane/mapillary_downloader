"""Tests for metadata reader."""

import gzip
import json

from mapillary_downloader.metadata_reader import MetadataReader


def test_metadata_reader_empty(tmp_path):
    """Test reading from non-existent file."""
    reader = MetadataReader(tmp_path / "nonexistent.jsonl")

    ids = reader.get_all_ids()
    assert len(ids) == 0
    assert not reader.is_complete

    images = list(reader.iter_images())
    assert len(images) == 0


def test_metadata_reader_basic(tmp_path):
    """Test reading basic metadata."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write some test data
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1", "thumb_original_url": "http://example.com/1.jpg"}) + "\n")
        f.write(json.dumps({"id": "img2", "thumb_original_url": "http://example.com/2.jpg"}) + "\n")
        f.write(json.dumps({"id": "img3", "thumb_1024_url": "http://example.com/3.jpg"}) + "\n")

    reader = MetadataReader(metadata_file)

    # Test get_all_ids
    ids = reader.get_all_ids()
    assert len(ids) == 3
    assert "img1" in ids
    assert "img2" in ids
    assert "img3" in ids

    # Test iter_images
    images = list(reader.iter_images())
    assert len(images) == 3


def test_metadata_reader_quality_filter(tmp_path):
    """Test filtering by quality field."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write some test data with different qualities
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1", "thumb_original_url": "http://example.com/1.jpg"}) + "\n")
        f.write(json.dumps({"id": "img2", "thumb_1024_url": "http://example.com/2.jpg"}) + "\n")
        f.write(json.dumps({"id": "img3", "thumb_original_url": "http://example.com/3.jpg"}) + "\n")

    reader = MetadataReader(metadata_file)

    # Filter by thumb_original_url
    images = list(reader.iter_images(quality_field="thumb_original_url"))
    assert len(images) == 2
    assert images[0]["id"] == "img1"
    assert images[1]["id"] == "img3"


def test_metadata_reader_downloaded_filter(tmp_path):
    """Test filtering by downloaded IDs."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write some test data
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1", "thumb_original_url": "http://example.com/1.jpg"}) + "\n")
        f.write(json.dumps({"id": "img2", "thumb_original_url": "http://example.com/2.jpg"}) + "\n")
        f.write(json.dumps({"id": "img3", "thumb_original_url": "http://example.com/3.jpg"}) + "\n")

    reader = MetadataReader(metadata_file)

    # Filter out already downloaded
    downloaded_ids = {"img1", "img3"}
    images = list(reader.iter_images(downloaded_ids=downloaded_ids))
    assert len(images) == 1
    assert images[0]["id"] == "img2"


def test_metadata_reader_completion_marker(tmp_path):
    """Test completion marker detection."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write some test data with completion marker
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1", "thumb_original_url": "http://example.com/1.jpg"}) + "\n")
        f.write(json.dumps({"__complete__": True}) + "\n")
        f.write(json.dumps({"id": "img2", "thumb_original_url": "http://example.com/2.jpg"}) + "\n")

    reader = MetadataReader(metadata_file)

    # Check completion detected
    ids = reader.get_all_ids()
    assert reader.is_complete

    # Completion marker should not be in IDs
    assert len(ids) == 2
    assert "__complete__" not in str(ids)


def test_metadata_reader_mark_complete(tmp_path):
    """Test marking metadata as complete."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write some test data
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1"}) + "\n")

    # Mark as complete
    MetadataReader.mark_complete(metadata_file)

    # Verify marker was added
    reader = MetadataReader(metadata_file)
    ids = reader.get_all_ids()
    assert reader.is_complete
    assert len(ids) == 1


def test_metadata_reader_gzip(tmp_path):
    """Test reading gzipped metadata file."""
    metadata_file = tmp_path / "metadata.jsonl.gz"

    # Write gzipped test data
    with gzip.open(metadata_file, "wt") as f:
        f.write(json.dumps({"id": "img1", "thumb_original_url": "http://example.com/1.jpg"}) + "\n")
        f.write(json.dumps({"id": "img2", "thumb_original_url": "http://example.com/2.jpg"}) + "\n")
        f.write(json.dumps({"__complete__": True}) + "\n")

    reader = MetadataReader(metadata_file)

    assert reader.is_complete
    ids = reader.get_all_ids()
    assert len(ids) == 2

    images = list(reader.iter_images())
    assert len(images) == 2


def test_metadata_reader_empty_lines(tmp_path):
    """Test handling of empty lines in metadata file."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write data with empty lines
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1"}) + "\n")
        f.write("\n")  # empty line
        f.write("   \n")  # whitespace-only line
        f.write(json.dumps({"id": "img2"}) + "\n")

    reader = MetadataReader(metadata_file)
    ids = reader.get_all_ids()
    assert len(ids) == 2


def test_metadata_reader_missing_id(tmp_path):
    """Test handling of entries without id."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write data including entry without id
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1"}) + "\n")
        f.write(json.dumps({"no_id": "here"}) + "\n")
        f.write(json.dumps({"id": "img2"}) + "\n")

    reader = MetadataReader(metadata_file)
    ids = reader.get_all_ids()
    assert len(ids) == 2
    assert "img1" in ids
    assert "img2" in ids

    images = list(reader.iter_images())
    assert len(images) == 2


def test_metadata_reader_completion_in_iter(tmp_path):
    """Test completion marker detection during iter_images."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write data with completion marker
    with open(metadata_file, "w") as f:
        f.write(json.dumps({"id": "img1"}) + "\n")
        f.write(json.dumps({"__complete__": True}) + "\n")

    reader = MetadataReader(metadata_file)
    # Don't call get_all_ids first - test detection via iter_images
    reader.is_complete = False

    images = list(reader.iter_images())
    assert len(images) == 1
    assert reader.is_complete


def test_metadata_reader_many_lines(tmp_path):
    """Test completion check with more than 10 lines."""
    metadata_file = tmp_path / "metadata.jsonl"

    # Write more than 10 lines
    with open(metadata_file, "w") as f:
        for i in range(15):
            f.write(json.dumps({"id": f"img{i}"}) + "\n")
        f.write(json.dumps({"__complete__": True}) + "\n")

    reader = MetadataReader(metadata_file)
    assert reader.is_complete
    ids = reader.get_all_ids()
    assert len(ids) == 15
