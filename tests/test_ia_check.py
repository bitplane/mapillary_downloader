"""Tests for Internet Archive check."""

from requests.exceptions import RequestException
from mapillary_downloader.ia_check import check_ia_exists


class FakeResponse:
    """Fake response object for testing."""

    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class FakeSession:
    """Fake session for testing."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append({"url": url, "timeout": timeout})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_check_ia_exists_found():
    """Test when collection exists on IA."""
    session = FakeSession(FakeResponse(200, {"metadata": {"title": "test"}}))

    result = check_ia_exists(session, "mapillary-testuser-original")

    assert result is True
    assert len(session.calls) == 1
    assert "mapillary-testuser-original" in session.calls[0]["url"]


def test_check_ia_exists_not_found():
    """Test when collection doesn't exist (404)."""
    session = FakeSession(FakeResponse(404, {}))

    result = check_ia_exists(session, "mapillary-nonexistent-original")

    assert result is False


def test_check_ia_exists_no_metadata():
    """Test when response has no metadata field."""
    session = FakeSession(FakeResponse(200, {"error": "not found"}))

    result = check_ia_exists(session, "mapillary-testuser-original")

    assert result is False


def test_check_ia_exists_is_dark():
    """Test when item is dark (hidden)."""
    session = FakeSession(FakeResponse(200, {"metadata": {"title": "test"}, "is_dark": True}))

    result = check_ia_exists(session, "mapillary-testuser-original")

    assert result is False


def test_check_ia_exists_network_error():
    """Test that network errors return False."""
    session = FakeSession(RequestException("connection failed"))

    result = check_ia_exists(session, "mapillary-testuser-original")

    assert result is False
