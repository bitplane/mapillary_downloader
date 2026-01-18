"""XMP metadata writer for panoramic Mapillary images."""

import logging

logger = logging.getLogger("mapillary_downloader")

# XMP namespace identifier for APP1 segment
XMP_NAMESPACE = b"http://ns.adobe.com/xap/1.0/\x00"

# XMP packet template for GPano metadata
XMP_TEMPLATE = """<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:GPano="http://ns.google.com/photos/1.0/panorama/"
      GPano:ProjectionType="equirectangular"
      GPano:UsePanoramaViewer="True"
      GPano:FullPanoWidthPixels="{width}"
      GPano:FullPanoHeightPixels="{height}"
      GPano:CroppedAreaImageWidthPixels="{width}"
      GPano:CroppedAreaImageHeightPixels="{height}"
      GPano:CroppedAreaLeftPixels="0"
      GPano:CroppedAreaTopPixels="0"{pose_heading}/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def build_xmp_packet(metadata):
    """Build XMP packet with GPano metadata.

    Args:
        metadata: Dictionary with width, height, and optionally compass_angle

    Returns:
        XMP XML string
    """
    width = metadata.get("width", 0)
    height = metadata.get("height", 0)

    # Get compass angle (prefer computed)
    compass = metadata.get("computed_compass_angle") or metadata.get("compass_angle")

    # Build pose heading attribute if available
    if compass is not None:
        pose_heading = f'\n      GPano:PoseHeadingDegrees="{compass:.1f}"'
    else:
        pose_heading = ""

    return XMP_TEMPLATE.format(
        width=width,
        height=height,
        pose_heading=pose_heading,
    )


def write_xmp_to_image(image_path, metadata):
    """Write XMP GPano metadata to a JPEG image for panoramas.

    Only writes metadata if is_pano is True in the metadata dict.

    Args:
        image_path: Path to the JPEG image file
        metadata: Dictionary of metadata from Mapillary API

    Returns:
        True if XMP was written, False if skipped or failed
    """
    # Only write XMP for panoramas
    if not metadata.get("is_pano"):
        return False

    # Need dimensions to write meaningful GPano data
    if not metadata.get("width") or not metadata.get("height"):
        logger.warning(f"Skipping XMP for {image_path}: missing dimensions")
        return False

    try:
        # Read the JPEG file
        with open(image_path, "rb") as f:
            data = f.read()

        # Verify JPEG signature
        if data[:2] != b"\xff\xd8":
            logger.warning(f"Skipping XMP for {image_path}: not a valid JPEG")
            return False

        # Build XMP packet
        xmp_xml = build_xmp_packet(metadata)
        xmp_bytes = xmp_xml.encode("utf-8")

        # Build APP1 segment with XMP namespace
        xmp_segment = XMP_NAMESPACE + xmp_bytes
        segment_length = len(xmp_segment) + 2  # +2 for length bytes

        if segment_length > 65535:
            logger.warning(f"Skipping XMP for {image_path}: XMP too large")
            return False

        # APP1 marker (0xFFE1) + length + data
        app1_marker = b"\xff\xe1"
        length_bytes = segment_length.to_bytes(2, byteorder="big")
        full_segment = app1_marker + length_bytes + xmp_segment

        # Find insertion point - after SOI (0xFFD8) and any existing APP0/APP1 segments
        # We want to insert after EXIF APP1 but before other segments
        pos = 2  # Skip SOI

        while pos < len(data) - 1:
            if data[pos] != 0xFF:
                break

            marker = data[pos + 1]

            # Stop at SOS (start of scan) or non-marker data
            if marker == 0xDA or marker == 0x00:
                break

            # Check if this is an APP1 with XMP namespace (skip if exists)
            if marker == 0xE1:  # APP1
                seg_len = int.from_bytes(data[pos + 2 : pos + 4], byteorder="big")
                seg_data = data[pos + 4 : pos + 2 + seg_len]
                if seg_data.startswith(XMP_NAMESPACE):
                    # XMP already exists, replace it
                    new_data = data[:pos] + full_segment + data[pos + 2 + seg_len :]
                    with open(image_path, "wb") as f:
                        f.write(new_data)
                    logger.debug(f"Replaced XMP in {image_path}")
                    return True
                # Skip this APP1 (probably EXIF)
                pos += 2 + seg_len
                continue

            # Skip APP0 (JFIF) segments
            if marker == 0xE0:  # APP0
                seg_len = int.from_bytes(data[pos + 2 : pos + 4], byteorder="big")
                pos += 2 + seg_len
                continue

            # Found a different marker, insert XMP here
            break

        # Insert XMP segment at current position
        new_data = data[:pos] + full_segment + data[pos:]

        with open(image_path, "wb") as f:
            f.write(new_data)

        logger.debug(f"Wrote XMP GPano metadata to {image_path}")
        return True

    except Exception as e:
        logger.warning(f"Failed to write XMP to {image_path}: {e}")
        return False
