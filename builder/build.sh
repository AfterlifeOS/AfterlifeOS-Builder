#!/bin/bash

# Arguments:
# 1: DEVICE
# 2: RELEASETYPE
# 3: INSTALLCLEAN
# 4: FULLCLEAN

DEVICE="$1"
RELEASETYPE="$2"
INSTALLCLEAN="$3"
FULLCLEAN="$4"

echo "Starting Building stage..."

# --- SMART CLEANUP LOGIC ---
LAST_DEVICE_FILE=".last_build_device.tmp"
if [ -f "$LAST_DEVICE_FILE" ]; then
    LAST_DEVICE=$(cat "$LAST_DEVICE_FILE")
    if [ -n "$LAST_DEVICE" ] && [ "$LAST_DEVICE" != "$DEVICE" ]; then
        echo "⚠️ Device changed from '$LAST_DEVICE' to '$DEVICE'."
        
        # 1. Clean up OLD device output to save space
        if [ -d "out/target/product/$LAST_DEVICE" ]; then
            echo "Removing output directory of previous device ($LAST_DEVICE)..."
            rm -rf "out/target/product/$LAST_DEVICE"
        fi
        
        # 2. Force INSTALLCLEAN for the NEW device to avoid artifact mixing
        if [ "$INSTALLCLEAN" != "Yes" ]; then
            echo "Forcing INSTALLCLEAN='Yes' due to device switch."
            INSTALLCLEAN="Yes"
        fi
    fi
else
    echo "No previous build record found. Treating as fresh start."
fi

# Saving current device
echo "Saving current device name for next build's cleanup..."
echo "$DEVICE" > "$LAST_DEVICE_FILE"

# Source build environment
echo "Sourcing build/envsetup.sh..."
. build/envsetup.sh || { echo "Failed to source build/envsetup.sh"; exit 1; }

# Handle Full Clean step (cleans the entire 'out' directory)
if [ "$FULLCLEAN" == "Yes" ]; then
    echo "FULLCLEAN is Yes, running 'make clean'..."
    make clean || { echo "Make clean failed"; exit 1; }
fi

# Run lunch command
LUNCH_COMMAND="lunch afterlife_${DEVICE}-bp2a-${RELEASETYPE}"
echo "Running lunch command: $LUNCH_COMMAND"
$LUNCH_COMMAND || { echo "Lunch command failed"; exit 1; }

# Handle Install Clean step (cleans only the product's out directory)
if [ "$INSTALLCLEAN" == "Yes" ]; then
    echo "INSTALLCLEAN is Yes, running 'make installclean'..."
    make installclean || { echo "Install Clean failed"; exit 1; }
fi

# Start building
echo "Starting make process with all available cores..."
# Use pipefail to ensure the exit code of 'm' is preserved even when piping to tee
set -o pipefail
m afterlife -j$(nproc --all) 2>&1 | tee "${WORKSPACE}/build.log" || { echo "Build failed"; exit 1; }

echo "Building stage complete."
