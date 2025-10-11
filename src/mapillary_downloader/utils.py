"""Utility functions for formatting and display."""


def format_size(bytes_count):
    """Format bytes as human-readable size.

    Args:
        bytes_count: Number of bytes

    Returns:
        Formatted string (e.g. "1.23 GB", "456.78 MB")
    """
    if bytes_count >= 1_000_000_000:
        return f"{bytes_count / 1_000_000_000:.2f} GB"
    if bytes_count >= 1_000_000:
        return f"{bytes_count / 1_000_000:.2f} MB"
    if bytes_count >= 1_000:
        return f"{bytes_count / 1000:.2f} KB"
    return f"{bytes_count} B"


def format_time(seconds):
    """Format seconds as human-readable time.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted string (e.g. "2h 15m", "45m 30s", "30s")
    """
    if seconds < 60:
        return f"{int(seconds)}s"

    minutes = int(seconds / 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = int(minutes / 60)
    remaining_minutes = minutes % 60

    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"
