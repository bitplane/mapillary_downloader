"""Tests for WebP conversion."""

import subprocess
from unittest.mock import Mock, patch
from mapillary_downloader.webp_converter import check_cwebp_available, convert_to_webp


def test_check_cwebp_available_when_installed():
    """Test cwebp detection when binary is available."""
    with patch("shutil.which", return_value="/usr/bin/cwebp"):
        assert check_cwebp_available() is True


def test_check_cwebp_available_when_not_installed():
    """Test cwebp detection when binary is not available."""
    with patch("shutil.which", return_value=None):
        assert check_cwebp_available() is False


def test_convert_to_webp_success(tmp_path):
    """Test successful WebP conversion."""
    jpg_path = tmp_path / "test.jpg"
    jpg_path.write_bytes(b"fake jpg data")

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        webp_path = convert_to_webp(jpg_path)

        assert webp_path is not None
        assert webp_path.suffix == ".webp"
        assert not jpg_path.exists()  # Original should be deleted


def test_convert_to_webp_failure(tmp_path):
    """Test failed WebP conversion."""
    jpg_path = tmp_path / "test.jpg"
    jpg_path.write_bytes(b"fake jpg data")

    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "conversion failed"

    with patch("subprocess.run", return_value=mock_result):
        webp_path = convert_to_webp(jpg_path)

        assert webp_path is None
        assert jpg_path.exists()  # Original should still exist on failure


def test_convert_to_webp_timeout(tmp_path):
    """Test WebP conversion timeout."""
    jpg_path = tmp_path / "test.jpg"
    jpg_path.write_bytes(b"fake jpg data")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cwebp", 60)):
        webp_path = convert_to_webp(jpg_path)

        assert webp_path is None
        assert jpg_path.exists()


def test_convert_to_webp_exception(tmp_path):
    """Test WebP conversion with unexpected exception."""
    jpg_path = tmp_path / "test.jpg"
    jpg_path.write_bytes(b"fake jpg data")

    with patch("subprocess.run", side_effect=Exception("unexpected error")):
        webp_path = convert_to_webp(jpg_path)

        assert webp_path is None
        assert jpg_path.exists()


def test_convert_to_webp_preserves_metadata(tmp_path):
    """Test that cwebp is called with metadata preservation flag."""
    jpg_path = tmp_path / "test.jpg"
    jpg_path.write_bytes(b"fake jpg data")

    mock_result = Mock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        convert_to_webp(jpg_path)

        # Verify cwebp is called with -metadata all flag
        call_args = mock_run.call_args[0][0]
        assert "cwebp" in call_args
        assert "-metadata" in call_args
        assert "all" in call_args
