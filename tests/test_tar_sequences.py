"""Tests for tar sequence functionality."""

import hashlib
import tarfile

from mapillary_downloader.tar_sequences import tar_sequence_directories


def test_tar_sequences_basic(tmp_path):
    """Test basic tar creation with bucketed structure."""
    # Create a collection directory with bucketed sequences
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create bucket directory 's' with sequences inside
    bucket_dir = collection / "s"
    bucket_dir.mkdir()

    seq_dir1 = bucket_dir / "seq_123"
    seq_dir1.mkdir()
    (seq_dir1 / "image1.webp").write_bytes(b"fake image 1")
    (seq_dir1 / "image2.webp").write_bytes(b"fake image 2")

    seq_dir2 = bucket_dir / "seq_456"
    seq_dir2.mkdir()
    (seq_dir2 / "image3.webp").write_bytes(b"fake image 3")

    # Tar the buckets
    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1  # One bucket tarred
    assert total_files == 3  # Three images total

    # Check tar file exists and original bucket directory is gone
    tar_path = collection / "s.tar"
    assert tar_path.exists()
    assert not bucket_dir.exists()

    # Verify tar contents
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        assert len(members) == 3
        names = sorted([m.name for m in members])
        assert names == ["s/seq_123/image1.webp", "s/seq_123/image2.webp", "s/seq_456/image3.webp"]


def test_tar_sequences_empty_directory(tmp_path):
    """Test that empty bucket directories are skipped."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create empty bucket directory
    bucket_dir = collection / "e"
    bucket_dir.mkdir()

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 0
    assert total_files == 0

    # Directory should still exist, no tar created
    assert bucket_dir.exists()
    assert not (collection / "e.tar").exists()


def test_tar_sequences_skip_meta_dirs(tmp_path):
    """Test that .meta and other special directories are skipped."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create .meta directory
    meta_dir = collection / ".meta"
    meta_dir.mkdir()
    (meta_dir / "metadata.txt").write_text("test")

    # Create normal bucket with sequence
    bucket_dir = collection / "s"
    bucket_dir.mkdir()
    seq_dir = bucket_dir / "seq_456"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1
    assert total_files == 1

    # .meta should not be tarred
    assert not (collection / ".meta.tar").exists()
    assert meta_dir.exists()


def test_tar_sequences_hyphen_bucket(tmp_path):
    """Test that bucket with hyphen prefix is handled correctly."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create bucket with hyphen (underscore bucket in reality)
    bucket_dir = collection / "_"
    bucket_dir.mkdir()

    # Create sequence inside
    seq_dir = bucket_dir / "-Ojz1iTmlAFeHfns_tWhww"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test image")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1
    assert total_files == 1

    tar_path = collection / "_.tar"
    assert tar_path.exists()
    assert not bucket_dir.exists()


def test_tar_reproducibility(tmp_path):
    """Test that tar files are reproducible with same content."""
    import os
    import time

    # Create first collection
    collection1 = tmp_path / "collection1"
    collection1.mkdir()
    bucket1 = collection1 / "s"
    bucket1.mkdir()
    seq1 = bucket1 / "seq_789"
    seq1.mkdir()
    (seq1 / "image1.webp").write_bytes(b"test content 1")
    (seq1 / "image2.webp").write_bytes(b"test content 2")

    # Set consistent mtimes
    mtime = time.time() - 86400  # 1 day ago
    for f in seq1.glob("*"):
        os.utime(f, (mtime, mtime))

    tar_sequence_directories(collection1)
    tar1_path = collection1 / "s.tar"
    tar1_hash = hashlib.sha256(tar1_path.read_bytes()).hexdigest()

    # Create second identical collection
    collection2 = tmp_path / "collection2"
    collection2.mkdir()
    bucket2 = collection2 / "s"
    bucket2.mkdir()
    seq2 = bucket2 / "seq_789"
    seq2.mkdir()
    (seq2 / "image1.webp").write_bytes(b"test content 1")
    (seq2 / "image2.webp").write_bytes(b"test content 2")

    # Set same mtimes
    for f in seq2.glob("*"):
        os.utime(f, (mtime, mtime))

    tar_sequence_directories(collection2)
    tar2_path = collection2 / "s.tar"
    tar2_hash = hashlib.sha256(tar2_path.read_bytes()).hexdigest()

    # Hashes should be identical
    assert tar1_hash == tar2_hash


def test_tar_normalized_ownership(tmp_path):
    """Test that tar files have normalized uid/gid."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    bucket_dir = collection / "s"
    bucket_dir.mkdir()
    seq_dir = bucket_dir / "seq_ownership"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test")

    tar_sequence_directories(collection)
    tar_path = collection / "s.tar"

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

    bucket_dir = collection / "s"
    bucket_dir.mkdir()
    seq_dir = bucket_dir / "seq_order"
    seq_dir.mkdir()

    # Create files in non-alphabetical order
    (seq_dir / "zzz.webp").write_bytes(b"z")
    (seq_dir / "aaa.webp").write_bytes(b"a")
    (seq_dir / "mmm.webp").write_bytes(b"m")

    tar_sequence_directories(collection)
    tar_path = collection / "s.tar"

    # Verify files are in sorted order in tar
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        # Files should be sorted by name
        assert names == sorted(names)


def test_tar_multiple_buckets(tmp_path):
    """Test tarring multiple buckets."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create multiple buckets
    for bucket_name in ["a", "m", "z"]:
        bucket_dir = collection / bucket_name
        bucket_dir.mkdir()
        seq_dir = bucket_dir / f"seq_{bucket_name}"
        seq_dir.mkdir()
        (seq_dir / "image.webp").write_bytes(b"test")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 3
    assert total_files == 3

    # All three buckets should be tarred
    assert (collection / "a.tar").exists()
    assert (collection / "m.tar").exists()
    assert (collection / "z.tar").exists()

    # Bucket directories should be gone
    assert not (collection / "a").exists()
    assert not (collection / "m").exists()
    assert not (collection / "z").exists()
