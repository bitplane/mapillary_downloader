"""Tests for tar sequence functionality."""

import hashlib
import tarfile

from mapillary_downloader.tar_sequences import tar_sequence_directories


def test_tar_sequences_basic(tmp_path):
    """Test basic tar creation with date-based structure."""
    # Create a collection directory with date-organized sequences
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create date directory '2024-01-15' with sequences inside
    date_dir = collection / "2024-01-15"
    date_dir.mkdir()

    seq_dir1 = date_dir / "seq_123"
    seq_dir1.mkdir()
    (seq_dir1 / "image1.webp").write_bytes(b"fake image 1")
    (seq_dir1 / "image2.webp").write_bytes(b"fake image 2")

    seq_dir2 = date_dir / "seq_456"
    seq_dir2.mkdir()
    (seq_dir2 / "image3.webp").write_bytes(b"fake image 3")

    # Tar the date directories
    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1  # One date tarred
    assert total_files == 3  # Three images total

    # Check tar file exists and original date directory is gone
    tar_path = collection / "2024-01-15.tar"
    assert tar_path.exists()
    assert not date_dir.exists()

    # Verify tar contents
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        assert len(members) == 3
        names = sorted([m.name for m in members])
        assert names == [
            "2024-01-15/seq_123/image1.webp",
            "2024-01-15/seq_123/image2.webp",
            "2024-01-15/seq_456/image3.webp",
        ]


def test_tar_sequences_empty_directory(tmp_path):
    """Test that empty date directories are skipped."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create empty date directory
    date_dir = collection / "2024-01-20"
    date_dir.mkdir()

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 0
    assert total_files == 0

    # Directory should still exist, no tar created
    assert date_dir.exists()
    assert not (collection / "2024-01-20.tar").exists()


def test_tar_sequences_skip_meta_dirs(tmp_path):
    """Test that .meta and other special directories are skipped."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create .meta directory
    meta_dir = collection / ".meta"
    meta_dir.mkdir()
    (meta_dir / "metadata.txt").write_text("test")

    # Create normal date directory with sequence
    date_dir = collection / "2024-01-15"
    date_dir.mkdir()
    seq_dir = date_dir / "seq_456"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1
    assert total_files == 1

    # .meta should not be tarred
    assert not (collection / ".meta.tar").exists()
    assert meta_dir.exists()


def test_tar_sequences_unknown_date(tmp_path):
    """Test that unknown-date bucket is handled correctly."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create unknown-date directory
    unknown_dir = collection / "unknown-date"
    unknown_dir.mkdir()

    # Create sequence inside
    seq_dir = unknown_dir / "seq_no_timestamp"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test image")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1
    assert total_files == 1

    tar_path = collection / "unknown-date.tar"
    assert tar_path.exists()
    assert not unknown_dir.exists()


def test_tar_reproducibility(tmp_path):
    """Test that tar files are reproducible with same content."""
    import os
    import time

    # Create first collection
    collection1 = tmp_path / "collection1"
    collection1.mkdir()
    date1 = collection1 / "2024-01-15"
    date1.mkdir()
    seq1 = date1 / "seq_789"
    seq1.mkdir()
    (seq1 / "image1.webp").write_bytes(b"test content 1")
    (seq1 / "image2.webp").write_bytes(b"test content 2")

    # Set consistent mtimes
    mtime = time.time() - 86400  # 1 day ago
    for f in seq1.glob("*"):
        os.utime(f, (mtime, mtime))

    tar_sequence_directories(collection1)
    tar1_path = collection1 / "2024-01-15.tar"
    tar1_hash = hashlib.sha256(tar1_path.read_bytes()).hexdigest()

    # Create second identical collection
    collection2 = tmp_path / "collection2"
    collection2.mkdir()
    date2 = collection2 / "2024-01-15"
    date2.mkdir()
    seq2 = date2 / "seq_789"
    seq2.mkdir()
    (seq2 / "image1.webp").write_bytes(b"test content 1")
    (seq2 / "image2.webp").write_bytes(b"test content 2")

    # Set same mtimes
    for f in seq2.glob("*"):
        os.utime(f, (mtime, mtime))

    tar_sequence_directories(collection2)
    tar2_path = collection2 / "2024-01-15.tar"
    tar2_hash = hashlib.sha256(tar2_path.read_bytes()).hexdigest()

    # Hashes should be identical
    assert tar1_hash == tar2_hash


def test_tar_normalized_ownership(tmp_path):
    """Test that tar files have normalized uid/gid."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    date_dir = collection / "2024-01-15"
    date_dir.mkdir()
    seq_dir = date_dir / "seq_ownership"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test")

    tar_sequence_directories(collection)
    tar_path = collection / "2024-01-15.tar"

    # Verify ownership is normalized
    with tarfile.open(tar_path) as tar:
        for member in tar.getmembers():
            assert member.uid == 0
            assert member.gid == 0
            assert member.uname == ""
            assert member.gname == ""


def test_tar_file_ordering(tmp_path):
    """Test that files are added in consistent sorted order."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    date_dir = collection / "2024-01-15"
    date_dir.mkdir()
    seq_dir = date_dir / "seq_order"
    seq_dir.mkdir()

    # Create files in non-alphabetical order
    (seq_dir / "zzz.webp").write_bytes(b"z")
    (seq_dir / "aaa.webp").write_bytes(b"a")
    (seq_dir / "mmm.webp").write_bytes(b"m")

    tar_sequence_directories(collection)
    tar_path = collection / "2024-01-15.tar"

    # Verify files are in sorted order in tar
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        # Files should be sorted by name
        assert names == sorted(names)


def test_tar_multiple_dates(tmp_path):
    """Test tarring multiple date directories in chronological order."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create multiple date directories
    for date_name in ["2024-01-15", "2024-03-20", "2024-02-10"]:
        date_dir = collection / date_name
        date_dir.mkdir()
        seq_dir = date_dir / f"seq_{date_name}"
        seq_dir.mkdir()
        (seq_dir / "image.webp").write_bytes(b"test")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 3
    assert total_files == 3

    # All three dates should be tarred
    assert (collection / "2024-01-15.tar").exists()
    assert (collection / "2024-02-10.tar").exists()
    assert (collection / "2024-03-20.tar").exists()

    # Date directories should be gone
    assert not (collection / "2024-01-15").exists()
    assert not (collection / "2024-02-10").exists()
    assert not (collection / "2024-03-20").exists()
