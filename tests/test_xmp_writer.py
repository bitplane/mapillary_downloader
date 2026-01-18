"""Tests for XMP writer."""

import subprocess

import piexif
from PIL import Image

from mapillary_downloader.xmp_writer import build_xmp_packet, write_xmp_to_image


def test_build_xmp_packet_basic():
    """Test XMP packet generation with basic metadata."""
    metadata = {
        "width": 5760,
        "height": 2880,
    }

    xmp = build_xmp_packet(metadata)

    assert 'GPano:ProjectionType="equirectangular"' in xmp
    assert 'GPano:UsePanoramaViewer="True"' in xmp
    assert 'GPano:FullPanoWidthPixels="5760"' in xmp
    assert 'GPano:FullPanoHeightPixels="2880"' in xmp
    assert 'GPano:CroppedAreaImageWidthPixels="5760"' in xmp
    assert 'GPano:CroppedAreaImageHeightPixels="2880"' in xmp
    assert 'GPano:CroppedAreaLeftPixels="0"' in xmp
    assert 'GPano:CroppedAreaTopPixels="0"' in xmp


def test_build_xmp_packet_with_compass():
    """Test XMP packet includes pose heading when compass is available."""
    metadata = {
        "width": 6720,
        "height": 3360,
        "computed_compass_angle": 68.8,
    }

    xmp = build_xmp_packet(metadata)

    assert 'GPano:PoseHeadingDegrees="68.8"' in xmp


def test_build_xmp_packet_prefers_computed_compass():
    """Test that computed_compass_angle is preferred over compass_angle."""
    metadata = {
        "width": 100,
        "height": 50,
        "compass_angle": 90.0,
        "computed_compass_angle": 180.0,
    }

    xmp = build_xmp_packet(metadata)

    assert 'GPano:PoseHeadingDegrees="180.0"' in xmp
    assert "90.0" not in xmp


def test_build_xmp_packet_no_compass():
    """Test XMP packet without compass data."""
    metadata = {
        "width": 100,
        "height": 50,
    }

    xmp = build_xmp_packet(metadata)

    assert "PoseHeadingDegrees" not in xmp


def test_write_xmp_pano_basic(tmp_path):
    """Test writing XMP to a panoramic image."""
    img = Image.new("RGB", (5760, 2880), color="blue")
    image_path = tmp_path / "pano.jpg"
    img.save(image_path)

    metadata = {
        "id": "pano123",
        "is_pano": True,
        "width": 5760,
        "height": 2880,
    }

    result = write_xmp_to_image(image_path, metadata)
    assert result is True

    # Verify with exiftool
    output = subprocess.run(
        ["exiftool", "-XMP:all", str(image_path)],
        capture_output=True,
        text=True,
    )

    assert "equirectangular" in output.stdout
    assert "5760" in output.stdout
    assert "2880" in output.stdout


def test_write_xmp_skips_non_pano(tmp_path):
    """Test that XMP is not written for non-panoramic images."""
    img = Image.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "regular.jpg"
    img.save(image_path)

    metadata = {
        "id": "regular123",
        "is_pano": False,
        "width": 100,
        "height": 100,
    }

    result = write_xmp_to_image(image_path, metadata)
    assert result is False

    # Verify no XMP was written
    output = subprocess.run(
        ["exiftool", "-XMP:all", str(image_path)],
        capture_output=True,
        text=True,
    )

    assert "equirectangular" not in output.stdout


def test_write_xmp_skips_missing_is_pano(tmp_path):
    """Test that XMP is not written when is_pano is missing."""
    img = Image.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "unknown.jpg"
    img.save(image_path)

    metadata = {
        "id": "unknown123",
        "width": 100,
        "height": 100,
    }

    result = write_xmp_to_image(image_path, metadata)
    assert result is False


def test_write_xmp_with_compass(tmp_path):
    """Test writing XMP with compass heading."""
    img = Image.new("RGB", (6720, 3360), color="green")
    image_path = tmp_path / "pano_compass.jpg"
    img.save(image_path)

    metadata = {
        "id": "pano_compass",
        "is_pano": True,
        "width": 6720,
        "height": 3360,
        "computed_compass_angle": 315.5,
    }

    result = write_xmp_to_image(image_path, metadata)
    assert result is True

    output = subprocess.run(
        ["exiftool", "-XMP:all", str(image_path)],
        capture_output=True,
        text=True,
    )

    assert "315.5" in output.stdout


def test_write_xmp_preserves_exif(tmp_path):
    """Test that writing XMP doesn't corrupt existing EXIF data."""
    img = Image.new("RGB", (5760, 2880), color="purple")
    image_path = tmp_path / "pano_exif.jpg"
    img.save(image_path)

    # Write EXIF first
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"TestCamera",
            piexif.ImageIFD.Model: b"Pano360",
        },
        "Exif": {},
        "GPS": {
            piexif.GPSIFD.GPSLatitude: ((51, 1), (30, 1), (0, 100)),
            piexif.GPSIFD.GPSLatitudeRef: b"N",
        },
        "1st": {},
        "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(image_path))

    # Now write XMP
    metadata = {
        "id": "pano_exif",
        "is_pano": True,
        "width": 5760,
        "height": 2880,
    }

    result = write_xmp_to_image(image_path, metadata)
    assert result is True

    # Verify EXIF is still intact
    exif_check = piexif.load(str(image_path))
    assert exif_check["0th"][piexif.ImageIFD.Make] == b"TestCamera"
    assert exif_check["0th"][piexif.ImageIFD.Model] == b"Pano360"
    assert exif_check["GPS"][piexif.GPSIFD.GPSLatitudeRef] == b"N"

    # Verify XMP is present
    output = subprocess.run(
        ["exiftool", "-XMP:all", str(image_path)],
        capture_output=True,
        text=True,
    )
    assert "equirectangular" in output.stdout


def test_write_xmp_survives_webp_conversion(tmp_path):
    """Test that XMP survives JPEG to WebP conversion."""
    img = Image.new("RGB", (5760, 2880), color="cyan")
    jpg_path = tmp_path / "pano.jpg"
    webp_path = tmp_path / "pano.webp"
    img.save(jpg_path)

    metadata = {
        "id": "pano_webp",
        "is_pano": True,
        "width": 5760,
        "height": 2880,
        "computed_compass_angle": 45.0,
    }

    result = write_xmp_to_image(jpg_path, metadata)
    assert result is True

    # Convert to WebP with metadata preservation
    convert_result = subprocess.run(
        ["cwebp", "-metadata", "all", str(jpg_path), "-o", str(webp_path)],
        capture_output=True,
    )
    assert convert_result.returncode == 0
    assert webp_path.exists()

    # Verify XMP in WebP
    output = subprocess.run(
        ["exiftool", "-XMP:all", str(webp_path)],
        capture_output=True,
        text=True,
    )

    assert "equirectangular" in output.stdout
    assert "5760" in output.stdout
    assert "2880" in output.stdout
    assert "45.0" in output.stdout


def test_write_xmp_replaces_existing(tmp_path):
    """Test that writing XMP twice replaces the first XMP."""
    img = Image.new("RGB", (1000, 500), color="yellow")
    image_path = tmp_path / "pano_replace.jpg"
    img.save(image_path)

    # Write first XMP
    metadata1 = {
        "id": "pano1",
        "is_pano": True,
        "width": 1000,
        "height": 500,
        "computed_compass_angle": 90.0,
    }
    write_xmp_to_image(image_path, metadata1)

    # Write second XMP with different compass
    metadata2 = {
        "id": "pano2",
        "is_pano": True,
        "width": 1000,
        "height": 500,
        "computed_compass_angle": 270.0,
    }
    result = write_xmp_to_image(image_path, metadata2)
    assert result is True

    # Verify only new compass is present
    output = subprocess.run(
        ["exiftool", "-XMP:all", str(image_path)],
        capture_output=True,
        text=True,
    )

    assert "270.0" in output.stdout
    # Old value should be replaced
    assert output.stdout.count("Pose Heading") == 1
