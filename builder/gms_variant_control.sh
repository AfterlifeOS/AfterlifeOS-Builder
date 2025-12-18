#!/bin/bash

# This script sets the GMS variant in the device-specific makefile
# based on the Jenkins parameter.

# Arguments:
# 1: DEVICE
# 2: GMS_VARIANT

set -e # Exit immediately if a command exits with a non-zero status.

DEVICE="$1"
GMS_VARIANT="$2"
LOCAL_MANIFEST_PATH=".repo/local_manifests/jenkins_custom_manifest.xml"

if [ -z "$DEVICE" ] || [ -z "$GMS_VARIANT" ]; then
    echo "Error: DEVICE and GMS_VARIANT arguments are required."
    exit 1
fi

echo "--- GMS Variant Control ---"
echo "Device: $DEVICE"
echo "Variant: $GMS_VARIANT"

# --- Map GMS_VARIANT to the Makefile value ---
GMS_VALUE=""
case "$GMS_VARIANT" in
    "Full")
        GMS_VALUE="true"
        ;;
    "Core")
        GMS_VALUE="core"
        ;;
    "Basic")
        GMS_VALUE="basic"
        ;;
    "Vanilla")
        GMS_VALUE="false"
        ;;
    *)
        echo "Error: Invalid GMS_VARIANT '$GMS_VARIANT' passed to script."
        exit 1
        ;;
esac

echo "Mapped GMS Value: $GMS_VALUE"

# --- Find the target Makefile ---
if [ ! -f "$LOCAL_MANIFEST_PATH" ]; then
    echo "Error: Local manifest '$LOCAL_MANIFEST_PATH' not found. Cannot determine project paths."
    exit 1
fi

echo "Parsing local manifest to find project trees..."
PROJECT_PATHS=$(grep -oP '(?<=<project)[^>]*path="[^"]*"' "$LOCAL_MANIFEST_PATH" | sed -n 's/.*path="\([^"]*\)".*/\1/p')

if [ -z "$PROJECT_PATHS" ]; then
    echo "Error: Could not find any project paths in '$LOCAL_MANIFEST_PATH'."
    exit 1
fi

echo "Searching for afterlife_${DEVICE}.mk in paths: $PROJECT_PATHS"
MAKEFILE_PATH=""
for path in $PROJECT_PATHS; do
    # Use find to search within each project path
    # We pipe to `head -n 1` to ensure we only get one result if there are duplicates
    result=$(find "$path" -name "afterlife_${DEVICE}.mk" -print -quit)
    if [ -n "$result" ]; then
        MAKEFILE_PATH=$result
        break # Exit loop once file is found
    fi
done

if [ -z "$MAKEFILE_PATH" ]; then
    echo "Error: Could not find 'afterlife_${DEVICE}.mk' in any of the local manifest project paths."
    exit 1
fi

echo "Found target makefile: $MAKEFILE_PATH"

# --- Modify the Makefile ---
FLAG="AFTERLIFE_GAPPS"

# Check if the flag already exists in the file
if grep -q "${FLAG}" "$MAKEFILE_PATH"; then
    echo "Flag '${FLAG}' found. Modifying existing line."
    # Use sed to find the line starting with the flag and replace it entirely
    sed -i "s/^${FLAG} := .*/${FLAG} := ${GMS_VALUE}/" "$MAKEFILE_PATH"
else
    echo "Flag '${FLAG}' not found. Appending new line."
    # Add the flag to the end of the file
    echo "" >> "$MAKEFILE_PATH"
    echo "${FLAG} := ${GMS_VALUE}" >> "$MAKEFILE_PATH"
fi

echo "Successfully updated '$MAKEFILE_PATH'."
echo "--- GMS Variant Control Complete ---"

exit 0
