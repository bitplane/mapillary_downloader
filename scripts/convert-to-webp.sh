#!/bin/bash
# Convert all JPEG images in a directory to WebP format, preserving EXIF metadata
# and deleting the originals after successful conversion.
#
# Usage: ./convert-to-webp.sh <directory>

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory>"
    echo "Converts all .jpg/.jpeg files in directory (recursively) to WebP format"
    exit 1
fi

DIR="$1"

if [ ! -d "$DIR" ]; then
    echo "Error: Directory '$DIR' does not exist"
    exit 1
fi

if ! command -v cwebp &> /dev/null; then
    echo "Error: cwebp not found. Install with: sudo apt install webp"
    exit 1
fi

# Count total files
TOTAL=$(find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) | wc -l)

if [ "$TOTAL" -eq 0 ]; then
    echo "No JPEG files found in $DIR"
    exit 0
fi

echo "Found $TOTAL JPEG files to convert"
echo "Starting conversion..."
echo

CONVERTED=0
FAILED=0
SAVED_BYTES=0
TOTAL_ORIGINAL_BYTES=0

# Find all JPEGs and convert them
while read -r jpg; do
    webp="${jpg%.*}.webp"

    # Get original size
    ORIGINAL_SIZE=$(stat -c%s "$jpg")
    TOTAL_ORIGINAL_BYTES=$((TOTAL_ORIGINAL_BYTES + ORIGINAL_SIZE))

    # Convert with metadata preservation
    if cwebp -metadata all "$jpg" -o "$webp" >/dev/null 2>&1; then
        # Get WebP size
        WEBP_SIZE=$(stat -c%s "$webp")
        SAVED=$((ORIGINAL_SIZE - WEBP_SIZE))

        # Delete original
        rm "$jpg"

        CONVERTED=$((CONVERTED + 1))
        SAVED_BYTES=$((SAVED_BYTES + SAVED))

        # Print progress every 10 files
        if [ $((CONVERTED % 10)) -eq 0 ]; then
            SAVED_MB=$((SAVED_BYTES / 1048576))
            PERCENTAGE=$((SAVED_BYTES * 100 / TOTAL_ORIGINAL_BYTES))
            PROGRESS_PCT=$((CONVERTED * 100 / TOTAL))
            echo "Progress: ${PROGRESS_PCT}% ($CONVERTED/$TOTAL) | Space reduction: ${PERCENTAGE}% (saved ${SAVED_MB}MB so far)"
        fi
    else
        FAILED=$((FAILED + 1))
        echo "Failed to convert: $jpg"
        # Remove failed WebP if it exists
        [ -f "$webp" ] && rm "$webp"
    fi
done < <(find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \))

# Final summary
SAVED_MB=$((SAVED_BYTES / 1048576))
SAVED_GB=$((SAVED_BYTES / 1073741824))

if [ "$TOTAL_ORIGINAL_BYTES" -gt 0 ]; then
    PERCENTAGE=$((SAVED_BYTES * 100 / TOTAL_ORIGINAL_BYTES))
else
    PERCENTAGE=0
fi

echo
echo "Conversion complete!"
echo "Converted: $CONVERTED files"
echo "Failed: $FAILED files"
echo "Space saved: ${SAVED_MB}MB (${SAVED_GB}GB)"
echo "Compression: ${PERCENTAGE}% space reduction"
