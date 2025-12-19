#!/bin/bash

# Arguments:
# 1: MODE (apply/restore)
# 2: DEVICE (Required for find logic)
# 3: GMS_VARIANT (Required for apply)

set -e

MODE="$1"
DEVICE="$2"
GMS_VARIANT="$3"
LOCAL_MANIFEST_PATH=".repo/local_manifests/jenkins_custom_manifest.xml"
TRACKER_FILE=".gms_mod_tracker"

# --- Function to find Makefile ---
find_makefile() {
    if [ ! -f "$LOCAL_MANIFEST_PATH" ]; then
        echo "Error: Local manifest '$LOCAL_MANIFEST_PATH' not found."
        exit 1
    fi
    PROJECT_PATHS=$(grep -oP '(?<=<project)[^>]*path="[^"]*"' "$LOCAL_MANIFEST_PATH" | sed -n 's/.*path="\([^"]*\)".*/\1/p')
    if [ -z "$PROJECT_PATHS" ]; then
        echo "Error: No project paths found in manifest."
        exit 1
    fi
    for path in $PROJECT_PATHS; do
        result=$(find "$path" -name "afterlife_${DEVICE}.mk" -print -quit)
        if [ -n "$result" ]; then
            echo "$result"
            return
        fi
    done
    echo ""
}

if [ "$MODE" == "restore" ]; then
    echo "--- GMS Variant Restore ---"
    
    # Try to read from tracker first
    if [ -f "$TRACKER_FILE" ]; then
        MAKEFILE_PATH=$(cat "$TRACKER_FILE")
        echo "Read target from tracker: $MAKEFILE_PATH"
    else
        # Fallback search if tracker missing
        if [ -z "$DEVICE" ]; then
            echo "Tracker missing and DEVICE not provided for restore fallback. Skipping."
            exit 0
        fi
        echo "Tracker missing. Searching for makefile..."
        MAKEFILE_PATH=$(find_makefile)
    fi

    if [ -n "$MAKEFILE_PATH" ] && [ -f "${MAKEFILE_PATH}.bak" ]; then
        echo "Restoring backup: ${MAKEFILE_PATH}.bak -> ${MAKEFILE_PATH}"
        mv "${MAKEFILE_PATH}.bak" "${MAKEFILE_PATH}"
    else
        echo "No backup file found or makefile path invalid. Nothing to restore."
    fi
    
    rm -f "$TRACKER_FILE"
    echo "--- Restore Complete ---"
    exit 0
fi

# --- APPLY MODE ---
if [ "$MODE" != "apply" ]; then
    echo "Usage: $0 [apply|restore] [DEVICE] [VARIANT]"
    exit 1
fi

if [ -z "$DEVICE" ] || [ -z "$GMS_VARIANT" ]; then
    echo "Error: DEVICE and GMS_VARIANT arguments are required for apply."
    exit 1
fi

echo "--- GMS Variant Apply ---"
echo "Device: $DEVICE"
echo "Variant: $GMS_VARIANT"

MAKEFILE_PATH=$(find_makefile)
if [ -z "$MAKEFILE_PATH" ]; then
    echo "Error: Could not find 'afterlife_${DEVICE}.mk'"
    exit 1
fi

echo "Target: $MAKEFILE_PATH"

# Save path for restore
echo "$MAKEFILE_PATH" > "$TRACKER_FILE"

# Backup (Only if not already backed up to prevent overwriting original with modified)
if [ ! -f "${MAKEFILE_PATH}.bak" ]; then
    echo "Creating backup: ${MAKEFILE_PATH}.bak"
    cp "$MAKEFILE_PATH" "${MAKEFILE_PATH}.bak"
fi

# Map Variant
GMS_VALUE=""
case "$GMS_VARIANT" in
    "Full") GMS_VALUE="true" ;;
    "Core") GMS_VALUE="core" ;;
    "Basic") GMS_VALUE="basic" ;;
    "Vanilla") GMS_VALUE="false" ;;
    *) echo "Error: Invalid Variant '$GMS_VARIANT'"; exit 1 ;;
esac

FLAG="AFTERLIFE_GAPPS"
if grep -q "${FLAG}" "$MAKEFILE_PATH"; then
    echo "Modifying existing flag..."
    sed -i "s/^${FLAG} := .*/${FLAG} := ${GMS_VALUE}/" "$MAKEFILE_PATH"
else
    echo "Appending new flag..."
    echo "" >> "$MAKEFILE_PATH"
    echo "${FLAG} := ${GMS_VALUE}" >> "$MAKEFILE_PATH"
fi

echo "Applied GMS Variant: $GMS_VALUE"
echo "--- Apply Complete ---"
