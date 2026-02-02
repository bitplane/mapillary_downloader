"""Logging configuration with colored output for TTY."""

import logging
import sys


class ColoredFormatter(logging.Formatter):
    """Formatter that adds color to log levels when output is a TTY."""

    # ANSI color codes
    COLORS = {
        "ERROR": "\033[91m",  # Red
        "WARNING": "\033[93m",  # Yellow
        "INFO": "\033[92m",  # Green
        "DEBUG": "\033[94m",  # Blue
        "RESET": "\033[0m",
    }
    CYAN = "\033[96m"

    def __init__(self, fmt=None, datefmt=None, use_color=True):
        """Initialize the formatter.

        Args:
            fmt: Log format string
            datefmt: Date format string
            use_color: Whether to use colored output
        """
        super().__init__(fmt, datefmt)
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record):
        """Format the log record with colors if appropriate.

        Args:
            record: LogRecord to format

        Returns:
            Formatted log string
        """
        if self.use_color:
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

            # Color API messages differently so they stand out
            if record.msg.startswith("API"):
                record.msg = f"{self.CYAN}{record.msg}{self.COLORS['RESET']}"

        return super().format(record)


def setup_logging(level=logging.INFO):
    """Set up logging with timestamps and colored output.

    Args:
        level: Logging level to use
    """
    formatter = ColoredFormatter(fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger("mapillary_downloader")
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


def add_file_handler(log_file, level=logging.INFO):
    """Add a file handler to the logger for archival.

    Args:
        log_file: Path to log file
        level: Logging level for file handler
    """
    # Use plain formatter for file (no colors)
    formatter = logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    handler.setFormatter(formatter)
    handler.setLevel(level)

    logger = logging.getLogger("mapillary_downloader")
    logger.addHandler(handler)

    return handler
