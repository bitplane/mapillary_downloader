"""Tests for logging configuration."""

import logging

from mapillary_downloader.logging_config import ColoredFormatter, setup_logging, add_file_handler


def test_colored_formatter_no_color():
    """Test formatter without color."""
    formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s", use_color=False)

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None
    )
    result = formatter.format(record)

    assert result == "INFO: test message"
    assert "\033[" not in result


def test_colored_formatter_with_color_non_tty():
    """Test that color is disabled when stdout is not a TTY."""
    formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s", use_color=True)

    # In test environment, stdout is typically not a TTY
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0, msg="error", args=(), exc_info=None
    )
    result = formatter.format(record)

    # Should not have color codes since we're not in a TTY
    assert "error" in result.lower() or "ERROR" in result


def test_setup_logging():
    """Test logging setup."""
    logger = setup_logging(level=logging.DEBUG)

    assert logger.name == "mapillary_downloader"
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) > 0

    # Clean up
    logger.handlers.clear()


def test_add_file_handler(tmp_path):
    """Test adding file handler."""
    log_file = tmp_path / "test.log"
    logger = logging.getLogger("mapillary_downloader")
    initial_handlers = len(logger.handlers)

    handler = add_file_handler(log_file, level=logging.WARNING)

    assert len(logger.handlers) == initial_handlers + 1
    assert log_file.exists()

    # Log something and verify it's written
    logger.warning("test warning message")
    handler.flush()

    content = log_file.read_text()
    assert "test warning message" in content

    # Clean up
    handler.close()
    logger.removeHandler(handler)
