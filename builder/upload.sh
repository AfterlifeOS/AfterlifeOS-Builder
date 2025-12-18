#!/bin/bash

# Arguments:
# 1: DEVICE

DEVICE="$1"

TG_API="https://api.telegram.org/bot${TELEGRAM_TOKEN}"

echo "Starting Uploading Build stage..."

# Locate the built ROM file
BUILD_OUTPUT_DIR="out/target/product/$DEVICE"
echo "Searching for the latest ROM in: $BUILD_OUTPUT_DIR"
if [ "$RELEASE_BUILD" == "true" ]; then
    echo "Release build detected. Will upload json file"
    JSON_OUTPUT_FILE="$BUILD_OUTPUT_DIR/${DEVICE}.json"
fi

# Find the newest file matching the pattern. This is more reliable than `head -n 1`.
ROM_FILE=$(find "$BUILD_OUTPUT_DIR" -maxdepth 1 -name "AfterlifeOS_*.zip" -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)

if [ -z "$ROM_FILE" ]; then
    echo "Error: ROM file not found in $BUILD_OUTPUT_DIR"
    exit 1
fi

echo "Found latest ROM file: $ROM_FILE"
if [ -n "$JSON_OUTPUT_FILE" ] && [ -f "$JSON_OUTPUT_FILE" ]; then
    echo "Found JSON release file: $JSON_OUTPUT_FILE"
    echo "Uploading ${JSON_OUTPUT_FILE} to telegram"
    CAPT="Release JSON - $DEVICE"
    response=$(curl -s --max-time 60 --ipv4 \
        -F document=@"${JSON_OUTPUT_FILE}" \
        "${TG_API}/sendDocument" \
        -F chat_id="-1002570127976" \
        -F caption="${CAPT}" \
        -F parse_mode="Markdown")

    ok=$(echo "$response" | jq -r '.ok')

    if [ "$ok" == "true" ]; then
        echo "Telegram sent successfully."
    else
        echo "Error: Failed to send Telegram file"
        echo "Telegram response: $response"
    fi
fi

# Check for jq dependency
if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' is not installed. Please install it to use the Gofile upload feature."
    exit 1
fi

# Upload the file to Gofile and print the download link
echo "Uploading ${ROM_FILE} to Gofile..."
DOWNLOAD_URL=$(curl -# -X POST https://upload.gofile.io/uploadFile -F "file=@$ROM_FILE" | jq -r '.data.downloadPage')

if [ -z "$DOWNLOAD_URL" ] || [ "$DOWNLOAD_URL" == "null" ]; then
    echo "Error: Failed to upload file or parse download URL."
    exit 1
fi

echo "=========================================="
echo "Build successfully uploaded!"
echo "Download Link: $DOWNLOAD_URL"
echo "=========================================="

echo "Uploading Build stage complete."
