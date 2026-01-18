"""EXIF metadata writer for Mapillary images."""

import logging
import piexif
from datetime import datetime

logger = logging.getLogger("mapillary_downloader")


def decimal_to_dms(decimal):
    """Convert decimal degrees to degrees, minutes, seconds format for EXIF.

    Args:
        decimal: Decimal degrees (can be negative)

    Returns:
        Tuple of ((degrees, 1), (minutes, 1), (seconds, 100)) as rational numbers
    """
    decimal = abs(decimal)
    degrees = int(decimal)
    minutes_float = (decimal - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    seconds_rational = (int(seconds * 100), 100)

    return ((degrees, 1), (minutes, 1), seconds_rational)


def timestamp_to_exif_datetime(timestamp):
    """Convert Unix timestamp to EXIF datetime string.

    Args:
        timestamp: Unix timestamp in milliseconds

    Returns:
        String in format "YYYY:MM:DD HH:MM:SS"
    """
    dt = datetime.fromtimestamp(timestamp / 1000.0)
    return dt.strftime("%Y:%m:%d %H:%M:%S")


def write_exif_to_image(image_path, metadata):
    """Write EXIF metadata from Mapillary API to downloaded image.

    Args:
        image_path: Path to the downloaded image file
        metadata: Dictionary of metadata from Mapillary API

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.debug(f"Writing EXIF to {image_path}")
        logger.debug(f"Metadata: {metadata}")

        # Load existing EXIF data if any
        try:
            exif_dict = piexif.load(str(image_path))
        except Exception:
            # No existing EXIF data, start fresh
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        # Ensure all IFDs exist
        for ifd in ["0th", "Exif", "GPS", "1st"]:
            if ifd not in exif_dict:
                exif_dict[ifd] = {}

        # Basic image info (0th IFD)
        if "make" in metadata and metadata["make"]:
            exif_dict["0th"][piexif.ImageIFD.Make] = metadata["make"].encode("utf-8")

        if "model" in metadata and metadata["model"]:
            exif_dict["0th"][piexif.ImageIFD.Model] = metadata["model"].encode("utf-8")

        if "width" in metadata and metadata["width"]:
            exif_dict["0th"][piexif.ImageIFD.ImageWidth] = metadata["width"]

        if "height" in metadata and metadata["height"]:
            exif_dict["0th"][piexif.ImageIFD.ImageLength] = metadata["height"]

        # Datetime tags
        if "captured_at" in metadata and metadata["captured_at"]:
            datetime_str = timestamp_to_exif_datetime(metadata["captured_at"])
            datetime_bytes = datetime_str.encode("utf-8")
            exif_dict["0th"][piexif.ImageIFD.DateTime] = datetime_bytes
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = datetime_bytes
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = datetime_bytes
            exif_dict["Exif"][piexif.ExifIFD.SubSecTimeOriginal] = ('000'+str(metadata["captured_at"] % 1000))[-3:]
            exif_dict["Exif"][piexif.ExifIFD.SubSecTimeDigitized] = ('000'+str(metadata["captured_at"] % 1000))[-3:]

        # GPS data - prefer computed_geometry over geometry
        geometry = metadata.get("computed_geometry") or metadata.get("geometry")
        if geometry and "coordinates" in geometry:
            lon, lat = geometry["coordinates"]

            # GPS Latitude
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = decimal_to_dms(lat)
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = b"N" if lat >= 0 else b"S"

            # GPS Longitude
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = decimal_to_dms(lon)
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = b"E" if lon >= 0 else b"W"

        # GPS Altitude - prefer computed_altitude over altitude
        altitude = metadata.get("computed_altitude") or metadata.get("altitude")
        if altitude is not None:
            altitude_val = int(abs(altitude) * 100)
            logger.debug(f"Raw altitude value: {altitude}, calculated: {altitude_val}")
            exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = (altitude_val, 100)
            exif_dict["GPS"][piexif.GPSIFD.GPSAltitudeRef] = 1 if altitude < 0 else 0

        # GPS Compass direction
        compass = metadata.get("computed_compass_angle") or metadata.get("compass_angle")
        if compass is not None:
            # Normalize compass to 0-360 range
            compass_val = int((compass % 360) * 100)
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirection] = (compass_val, 100)
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirectionRef] = b"T"  # True north

        # GPS Version
        exif_dict["GPS"][piexif.GPSIFD.GPSVersionID] = (2, 0, 0, 0)

        # Dump and write EXIF data
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(image_path))

        logger.debug(f"Successfully wrote EXIF to {image_path}")
        return True

    except Exception as e:
        logger.warning(f"Failed to write EXIF data to {image_path}: {e}")
        logger.debug(f"Full metadata: {metadata}")
        return False
