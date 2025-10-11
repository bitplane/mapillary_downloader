"""Tests for EXIF writer."""

import piexif
from PIL import Image
from mapillary_downloader.exif_writer import decimal_to_dms, timestamp_to_exif_datetime, write_exif_to_image


def test_decimal_to_dms_positive():
    """Test conversion of positive decimal degrees to DMS."""
    result = decimal_to_dms(51.5074)
    degrees, minutes, seconds = result

    assert degrees == (51, 1)
    assert minutes == (30, 1)
    assert seconds[1] == 100  # Denominator
    # 0.5074 * 60 = 30.444, (30.444 - 30) * 60 = 26.64
    assert 2600 <= seconds[0] <= 2700


def test_decimal_to_dms_negative():
    """Test conversion of negative decimal degrees to DMS (absolute value)."""
    result = decimal_to_dms(-0.1278)
    degrees, minutes, seconds = result

    assert degrees == (0, 1)
    assert minutes == (7, 1)
    # 0.1278 * 60 = 7.668, (7.668 - 7) * 60 = 40.08
    assert 4000 <= seconds[0] <= 4100


def test_timestamp_to_exif_datetime():
    """Test conversion of Unix timestamp to EXIF datetime format."""
    # 2024-01-15 (time will vary by timezone)
    timestamp = 1705320645000  # in milliseconds
    result = timestamp_to_exif_datetime(timestamp)

    # Check format and date
    assert result.startswith("2024:01:15")
    assert len(result) == 19  # "YYYY:MM:DD HH:MM:SS"


def test_write_exif_to_image_gps(tmp_path):
    """Test writing GPS EXIF data to image."""
    # Create a test image
    img = Image.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.jpg"
    img.save(image_path)

    metadata = {
        "id": "test123",
        "geometry": {"coordinates": [-0.1278, 51.5074]},  # [lon, lat]
        "altitude": 45.5,
        "captured_at": 1705320645000,
    }

    result = write_exif_to_image(image_path, metadata)
    assert result is True

    # Read back the EXIF data
    exif_dict = piexif.load(str(image_path))

    # Check GPS latitude
    assert piexif.GPSIFD.GPSLatitude in exif_dict["GPS"]
    assert exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] == b"N"

    # Check GPS longitude
    assert piexif.GPSIFD.GPSLongitude in exif_dict["GPS"]
    assert exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] == b"W"

    # Check altitude
    assert piexif.GPSIFD.GPSAltitude in exif_dict["GPS"]
    assert exif_dict["GPS"][piexif.GPSIFD.GPSAltitudeRef] == 0  # Above sea level


def test_write_exif_to_image_camera(tmp_path):
    """Test writing camera EXIF data to image."""
    img = Image.new("RGB", (4032, 3024), color="blue")
    image_path = tmp_path / "test.jpg"
    img.save(image_path)

    metadata = {
        "id": "test456",
        "make": "Canon",
        "model": "EOS 5D",
        "width": 4032,
        "height": 3024,
        "exif_orientation": 1,
        "captured_at": 1705320645000,
    }

    result = write_exif_to_image(image_path, metadata)
    assert result is True

    # Read back the EXIF data
    exif_dict = piexif.load(str(image_path))

    # Check camera data
    assert exif_dict["0th"][piexif.ImageIFD.Make] == b"Canon"
    assert exif_dict["0th"][piexif.ImageIFD.Model] == b"EOS 5D"
    assert exif_dict["0th"][piexif.ImageIFD.ImageWidth] == 4032
    assert exif_dict["0th"][piexif.ImageIFD.ImageLength] == 3024
    assert exif_dict["0th"][piexif.ImageIFD.Orientation] == 1

    # Check datetime
    assert piexif.ImageIFD.DateTime in exif_dict["0th"]
    assert b"2024:01:15" in exif_dict["0th"][piexif.ImageIFD.DateTime]


def test_write_exif_to_image_compass(tmp_path):
    """Test writing compass direction to EXIF."""
    img = Image.new("RGB", (100, 100), color="green")
    image_path = tmp_path / "test.jpg"
    img.save(image_path)

    metadata = {
        "id": "test789",
        "geometry": {"coordinates": [0, 0]},
        "computed_compass_angle": 315.5,  # NW direction
    }

    result = write_exif_to_image(image_path, metadata)
    assert result is True

    # Read back the EXIF data
    exif_dict = piexif.load(str(image_path))

    # Check compass direction
    assert piexif.GPSIFD.GPSImgDirection in exif_dict["GPS"]
    direction = exif_dict["GPS"][piexif.GPSIFD.GPSImgDirection]
    assert direction[0] == 31550  # 315.5 * 100
    assert direction[1] == 100
    assert exif_dict["GPS"][piexif.GPSIFD.GPSImgDirectionRef] == b"T"  # True north


def test_write_exif_uses_computed_values(tmp_path):
    """Test that computed values are preferred over originals."""
    img = Image.new("RGB", (100, 100), color="yellow")
    image_path = tmp_path / "test.jpg"
    img.save(image_path)

    metadata = {
        "id": "test_computed",
        "geometry": {"coordinates": [1, 1]},
        "computed_geometry": {"coordinates": [2, 2]},
        "altitude": 100,
        "computed_altitude": 200,
        "compass_angle": 90,
        "computed_compass_angle": 180,
    }

    result = write_exif_to_image(image_path, metadata)
    assert result is True

    # Read back the EXIF data
    exif_dict = piexif.load(str(image_path))

    # Should use computed_geometry (2, 2) not geometry (1, 1)
    lat_dms = exif_dict["GPS"][piexif.GPSIFD.GPSLatitude]
    assert lat_dms[0][0] == 2  # 2 degrees

    # Should use computed_altitude (200) not altitude (100)
    altitude = exif_dict["GPS"][piexif.GPSIFD.GPSAltitude]
    assert altitude[0] == 20000  # 200 * 100

    # Should use computed_compass_angle (180) not compass_angle (90)
    direction = exif_dict["GPS"][piexif.GPSIFD.GPSImgDirection]
    assert direction[0] == 18000  # 180 * 100


def test_write_exif_to_image_missing_fields(tmp_path):
    """Test writing EXIF with missing/None fields."""
    img = Image.new("RGB", (100, 100), color="white")
    image_path = tmp_path / "test.jpg"
    img.save(image_path)

    metadata = {
        "id": "test_partial",
        "geometry": {"coordinates": [0, 0]},
        # Missing: make, model, altitude, compass
    }

    result = write_exif_to_image(image_path, metadata)
    assert result is True

    # Should not crash, just skip missing fields
    exif_dict = piexif.load(str(image_path))
    assert piexif.GPSIFD.GPSLatitude in exif_dict["GPS"]
    # Altitude should not be present
    assert piexif.GPSIFD.GPSAltitude not in exif_dict["GPS"]
