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

# Checking latest build device
echo "Checking Build Context..."
if [ -f .last_build_device.tmp ]; then
    LAST_DEVICE=$(cat .last_build_device.tmp)
    echo "-> Current device is ${DEVICE}"
    echo "-> Previous device is ${LAST_DEVICE}"
    if [ "$DEVICE" != "$LAST_DEVICE" ]; then
        echo "[*] Current build device is not same with latest build device"
        echo "[*] Cleaning up latest device trash files"
        TRASH_DIR="out/target/product/${LAST_DEVICE}"
        if [ -d "${TRASH_DIR}" ]; then
            echo "[*] found ${TRASH_DIR}. Removing now..."
            rm -rf "${TRASH_DIR}"
        else
            echo "[*] ${TRASH_DIR} not found. skipping cleanup..."
        fi
    else
        echo "[*] Current build device same with latest build device"
        echo "[*] No need to clean up"
    fi
fi

# Saving current device
echo "Saving current device name for next build's cleanup..."
echo "$DEVICE" > .last_build_device.tmp

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
m afterlife -j$(nproc --all) || { echo "Build failed"; exit 1; }

echo "Building stage complete."
