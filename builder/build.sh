#!/bin/bash

# Arguments:
# 1: DEVICE
# 2: RELEASETYPE

DEVICE="$1"
RELEASETYPE="$2"

echo "Starting Building stage..."

# Navigate to AOSP source directory
AOSP_SOURCE_DIR="$HOME/android/source"
echo "Navigating to AOSP source directory: $AOSP_SOURCE_DIR"
cd "$AOSP_SOURCE_DIR" || { echo "Failed to navigate to $AOSP_SOURCE_DIR"; exit 1; }

# Saving current device
echo "Saving current device name for next build's cleanup..."
echo "$DEVICE" > .last_build_device.tmp

# Source build environment
echo "Sourcing build/envsetup.sh..."
. build/envsetup.sh || { echo "Failed to source build/envsetup.sh"; exit 1; }

# Run lunch command
LUNCH_COMMAND="lunch afterlife_${DEVICE}-bp2a-${RELEASETYPE}"
echo "Running lunch command: $LUNCH_COMMAND"
$LUNCH_COMMAND || { echo "Lunch command failed"; exit 1; }

# Start building
echo "Starting make process with all available cores..."
m afterlife -j$(nproc --all) || { echo "Build failed"; exit 1; }

echo "Building stage complete."
