"""Tests for utility functions."""

from mapillary_downloader.utils import format_size, format_time


def test_format_size_bytes():
    """Test formatting bytes."""
    assert format_size(0) == "0 B"
    assert format_size(500) == "500 B"
    assert format_size(999) == "999 B"


def test_format_size_kilobytes():
    """Test formatting kilobytes."""
    assert format_size(1_000) == "1.00 KB"
    assert format_size(1_500) == "1.50 KB"
    assert format_size(999_999) == "1000.00 KB"


def test_format_size_megabytes():
    """Test formatting megabytes."""
    assert format_size(1_000_000) == "1.00 MB"
    assert format_size(1_500_000) == "1.50 MB"
    assert format_size(999_999_999) == "1000.00 MB"


def test_format_size_gigabytes():
    """Test formatting gigabytes."""
    assert format_size(1_000_000_000) == "1.00 GB"
    assert format_size(1_500_000_000) == "1.50 GB"
    assert format_size(10_000_000_000) == "10.00 GB"


def test_format_time_seconds():
    """Test formatting seconds."""
    assert format_time(0) == "0s"
    assert format_time(30) == "30s"
    assert format_time(59) == "59s"


def test_format_time_minutes():
    """Test formatting minutes."""
    assert format_time(60) == "1m"
    assert format_time(90) == "1m 30s"
    assert format_time(120) == "2m"
    assert format_time(3599) == "59m 59s"


def test_format_time_hours():
    """Test formatting hours."""
    assert format_time(3600) == "1h"
    assert format_time(3660) == "1h 1m"
    assert format_time(7200) == "2h"
    assert format_time(9000) == "2h 30m"
