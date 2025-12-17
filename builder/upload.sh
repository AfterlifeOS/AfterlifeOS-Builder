#!/bin/bash

# Arguments:
# 1: DEVICE
# 2: RELEASETYPE (though not strictly needed for locating the file, good to pass)

DEVICE="$1"
RELEASETYPE="$2"

echo "Starting Uploading Build stage..."

# Navigate to AOSP source directory
AOSP_SOURCE_DIR="$HOME/android/source"
echo "Navigating to AOSP source directory: $AOSP_SOURCE_DIR"
cd "$AOSP_SOURCE_DIR" || { echo "Failed to navigate to $AOSP_SOURCE_DIR"; exit 1; }

# Locate the built ROM file
# Assuming the ROM file is a .zip in the standard AOSP output directory
BUILD_OUTPUT_DIR="out/target/product/$DEVICE"
ROM_FILE=$(find "$BUILD_OUTPUT_DIR" -maxdepth 1 -name "Afterlife_*.zip" | head -n 1)

if [ -z "$ROM_FILE" ]; then
    echo "Error: ROM file not found in $BUILD_OUTPUT_DIR"
    exit 1
fi

echo "Found ROM file: $ROM_FILE"

# Check for jq dependency
if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' is not installed. Please install it to use the Gofile upload feature."
    exit 1
fi

# Upload the file to Gofile and print the download link
echo "Uploading to Gofile..."
DOWNLOAD_URL=$(curl -# -X POST https://upload.gofile.io/uploadFile -F "file=@$ROM_FILE" | jq -r '.data.downloadPage')

if [ -z "$DOWNLOAD_URL" ] || [ "$DOWNLOAD_URL" == "null" ]; then
    echo "Error: Failed to upload file or parse download URL."
    exit 1
fi

echo "=========================================="
echo "Build successfully uploaded!"
echo "Download Link: $DOWNLOAD_URL"
echo "=========================================="

echo "Saving current device name for next build's cleanup..."
echo "$DEVICE" > .last_build_device.tmp

echo "Uploading Build stage complete."
