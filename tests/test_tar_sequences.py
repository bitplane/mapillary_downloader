"""Tests for tar sequence functionality."""

import hashlib
import tarfile

from mapillary_downloader.tar_sequences import tar_sequence_directories


def test_tar_sequences_basic(tmp_path):
    """Test basic tar creation."""
    # Create a collection directory with a sequence
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    seq_dir = collection / "seq_123"
    seq_dir.mkdir()

    # Create some test files
    (seq_dir / "image1.webp").write_bytes(b"fake image 1")
    (seq_dir / "image2.webp").write_bytes(b"fake image 2")

    # Tar the sequences
    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1
    assert total_files == 2

    # Check tar file exists and original directory is gone
    tar_path = collection / "seq_123.tar"
    assert tar_path.exists()
    assert not seq_dir.exists()

    # Verify tar contents
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        assert len(members) == 2
        names = sorted([m.name for m in members])
        assert names == ["seq_123/image1.webp", "seq_123/image2.webp"]


def test_tar_sequences_empty_directory(tmp_path):
    """Test that empty directories are skipped."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create empty sequence directory
    seq_dir = collection / "seq_empty"
    seq_dir.mkdir()

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 0
    assert total_files == 0

    # Directory should still exist, no tar created
    assert seq_dir.exists()
    assert not (collection / "seq_empty.tar").exists()


def test_tar_sequences_skip_meta_dirs(tmp_path):
    """Test that .meta and other special directories are skipped."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create .meta directory
    meta_dir = collection / ".meta"
    meta_dir.mkdir()
    (meta_dir / "metadata.txt").write_text("test")

    # Create normal sequence
    seq_dir = collection / "seq_456"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1
    assert total_files == 1

    # .meta should not be tarred
    assert not (collection / ".meta.tar").exists()
    assert meta_dir.exists()


def test_tar_sequences_hyphen_prefix(tmp_path):
    """Test that sequence IDs starting with hyphens are handled correctly."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    # Create sequence with hyphen prefix (real-world case)
    seq_dir = collection / "-Ojz1iTmlAFeHfns_tWhww"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test image")

    tarred_count, total_files = tar_sequence_directories(collection)

    assert tarred_count == 1
    assert total_files == 1

    tar_path = collection / "-Ojz1iTmlAFeHfns_tWhww.tar"
    assert tar_path.exists()
    assert not seq_dir.exists()


def test_tar_reproducibility(tmp_path):
    """Test that tar files are reproducible with same content."""
    # Create first collection
    collection1 = tmp_path / "collection1"
    collection1.mkdir()
    seq1 = collection1 / "seq_789"
    seq1.mkdir()
    (seq1 / "image1.webp").write_bytes(b"test content 1")
    (seq1 / "image2.webp").write_bytes(b"test content 2")

    # Set consistent mtimes
    import os
    import time

    mtime = time.time() - 86400  # 1 day ago
    for f in seq1.glob("*"):
        os.utime(f, (mtime, mtime))

    tar_sequence_directories(collection1)
    tar1_path = collection1 / "seq_789.tar"
    tar1_hash = hashlib.sha256(tar1_path.read_bytes()).hexdigest()

    # Create second identical collection
    collection2 = tmp_path / "collection2"
    collection2.mkdir()
    seq2 = collection2 / "seq_789"
    seq2.mkdir()
    (seq2 / "image1.webp").write_bytes(b"test content 1")
    (seq2 / "image2.webp").write_bytes(b"test content 2")

    # Set same mtimes
    for f in seq2.glob("*"):
        os.utime(f, (mtime, mtime))

    tar_sequence_directories(collection2)
    tar2_path = collection2 / "seq_789.tar"
    tar2_hash = hashlib.sha256(tar2_path.read_bytes()).hexdigest()

    # Hashes should be identical
    assert tar1_hash == tar2_hash


def test_tar_normalized_ownership(tmp_path):
    """Test that tar files have normalized uid/gid."""
    collection = tmp_path / "mapillary-test-original"
    collection.mkdir()

    seq_dir = collection / "seq_ownership"
    seq_dir.mkdir()
    (seq_dir / "image.webp").write_bytes(b"test")

    tar_sequence_directories(collection)
    tar_path = collection / "seq_ownership.tar"

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

    seq_dir = collection / "seq_order"
    seq_dir.mkdir()

    # Create files in non-alphabetical order
    (seq_dir / "zzz.webp").write_bytes(b"z")
    (seq_dir / "aaa.webp").write_bytes(b"a")
    (seq_dir / "mmm.webp").write_bytes(b"m")

    tar_sequence_directories(collection)
    tar_path = collection / "seq_order.tar"

    # Verify files are in sorted order in tar
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        # Files should be sorted by name
        assert names == sorted(names)
