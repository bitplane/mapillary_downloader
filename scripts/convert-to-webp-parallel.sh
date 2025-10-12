#!/bin/bash
# Convert all JPEG images in subdirectories to WebP format in parallel
# Processes one subdirectory per CPU core
#
# Usage: ./convert-to-webp-parallel.sh <directory>

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory>"
    echo "Converts all .jpg/.jpeg files in subdirectories to WebP format in parallel"
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

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONVERT_SCRIPT="$SCRIPT_DIR/convert-to-webp.sh"

if [ ! -x "$CONVERT_SCRIPT" ]; then
    echo "Error: $CONVERT_SCRIPT not found or not executable"
    exit 1
fi

# Get number of CPUs
NCPUS=$(nproc)

echo "Converting images in parallel using $NCPUS CPU cores"
echo "Processing subdirectories in: $DIR"
echo

# Find all subdirectories that contain JPEG files
mapfile -t SUBDIRS < <(find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) -printf '%h\n' | sort -u)

if [ ${#SUBDIRS[@]} -eq 0 ]; then
    echo "No subdirectories with JPEG files found"
    exit 0
fi

echo "Found ${#SUBDIRS[@]} subdirectories with JPEG files"
echo

# Process subdirectories in parallel
export CONVERT_SCRIPT
# shellcheck disable=SC2016
printf '%s\n' "${SUBDIRS[@]}" | xargs -P "$NCPUS" -I {} bash -c 'DIR="{}"; echo "Processing: $DIR" && "$CONVERT_SCRIPT" "$DIR" 2>&1 | sed "s/^/[$(basename "$DIR")] /"'

echo
echo "All conversions complete!"
