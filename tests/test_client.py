"""Tests for the Mapillary API client."""

from unittest.mock import Mock
from mapillary_downloader.client import MapillaryClient


def test_client_init():
    """Test client initialization."""
    token = "test_token"
    client = MapillaryClient(token)

    assert client.access_token == token
    assert client.base_url == "https://graph.mapillary.com"
    assert client.session.headers["Authorization"] == f"OAuth {token}"


def test_get_user_images_fields():
    """Test that get_user_images requests the correct fields."""
    client = MapillaryClient("test_token")

    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"id": "123", "captured_at": 1234567890}], "paging": {}}
    mock_response.raise_for_status = Mock()

    client.session.get = Mock(return_value=mock_response)

    images = list(client.get_user_images("testuser"))

    assert len(images) == 1
    assert images[0]["id"] == "123"

    call_args = client.session.get.call_args
    assert "creator_username" in call_args[1]["params"]
    assert call_args[1]["params"]["creator_username"] == "testuser"

    fields = call_args[1]["params"]["fields"].split(",")
    assert "id" in fields
    assert "thumb_original_url" in fields


def test_get_user_images_pagination():
    """Test that pagination works correctly."""
    client = MapillaryClient("test_token")

    page1_response = Mock()
    page1_response.json.return_value = {
        "data": [{"id": "1"}],
        "paging": {"next": "https://graph.mapillary.com/images?page=2"},
    }
    page1_response.raise_for_status = Mock()

    page2_response = Mock()
    page2_response.json.return_value = {"data": [{"id": "2"}], "paging": {}}
    page2_response.raise_for_status = Mock()

    client.session.get = Mock(side_effect=[page1_response, page2_response])

    images = list(client.get_user_images("testuser"))

    assert len(images) == 2
    assert images[0]["id"] == "1"
    assert images[1]["id"] == "2"
    assert client.session.get.call_count == 2


def test_get_user_images_with_bbox():
    """Test that bbox parameter is passed correctly."""
    client = MapillaryClient("test_token")

    mock_response = Mock()
    mock_response.json.return_value = {"data": [], "paging": {}}
    mock_response.raise_for_status = Mock()

    client.session.get = Mock(return_value=mock_response)

    bbox = [-180, -90, 180, 90]
    list(client.get_user_images("testuser", bbox=bbox))

    call_args = client.session.get.call_args
    assert "bbox" in call_args[1]["params"]
    assert call_args[1]["params"]["bbox"] == "-180,-90,180,90"


def test_download_image_success(tmp_path):
    """Test successful image download."""
    client = MapillaryClient("test_token")

    image_data = b"fake image data"
    mock_response = Mock()
    mock_response.iter_content = Mock(return_value=[image_data])
    mock_response.raise_for_status = Mock()

    client.session.get = Mock(return_value=mock_response)

    output_path = tmp_path / "test.jpg"
    result = client.download_image("http://example.com/image.jpg", output_path)

    assert result is True
    assert output_path.exists()
    assert output_path.read_bytes() == image_data


def test_download_image_failure(tmp_path, capsys):
    """Test failed image download."""
    client = MapillaryClient("test_token")

    client.session.get = Mock(side_effect=Exception("Network error"))

    output_path = tmp_path / "test.jpg"
    result = client.download_image("http://example.com/image.jpg", output_path)

    assert result is False
    assert not output_path.exists()

    captured = capsys.readouterr()
    assert "Error downloading" in captured.out
