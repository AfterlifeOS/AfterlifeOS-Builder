#!/bin/bash

# Arguments:
# 1: LOCAL_MANIFEST_URL (optional)
# AOSP_MANIFEST_URL and AOSP_MANIFEST_BRANCH are now read from environment variables

LOCAL_MANIFEST_URL="$1"

echo "Starting Syncing Source stage..."

# --- Cleanup previous build's output directory ---
LAST_BUILD_DEVICE_FILE=".last_build_device.tmp"
if [ -f "$LAST_BUILD_DEVICE_FILE" ]; then
    OLDER_DEVICE=$(cat "$LAST_BUILD_DEVICE_FILE")
    if [ -n "$OLDER_DEVICE" ]; then
        OLD_OUTPUT_DIR="out/target/product/$OLDER_DEVICE"
        if [ -d "$OLD_OUTPUT_DIR" ]; then
            echo "Found output directory from previous build for device '$OLDER_DEVICE'. Cleaning it up..."
            rm -rf "$OLD_OUTPUT_DIR"
            echo "Successfully removed $OLD_OUTPUT_DIR"
        fi
    fi
fi


# Navigate to AOSP source directory
AOSP_SOURCE_DIR="$HOME/android/source"
echo "Navigating to AOSP source directory: $AOSP_SOURCE_DIR"
cd "$AOSP_SOURCE_DIR" || { echo "Failed to navigate to $AOSP_SOURCE_DIR"; exit 1; }

# --- Cleanup previous local_manifest.xml and its associated physical directories if tracked ---
if [ -f ".local_manifest_path.tmp" ]; then
    PREVIOUS_LOCAL_MANIFEST_FILE=$(cat .local_manifest_path.tmp)
    if [ -n "$PREVIOUS_LOCAL_MANIFEST_FILE" ] && [ -f "$PREVIOUS_LOCAL_MANIFEST_FILE" ]; then
        echo "Found previous local manifest file: $PREVIOUS_LOCAL_MANIFEST_FILE"
        echo "Parsing previous local manifest to identify directories to clean..."

        # Extract project paths from the previous local manifest
        # Assuming project paths are relative to AOSP_SOURCE_DIR
        OLD_PROJECT_PATHS=$(grep -oP '(?<=<project)[^>]*path="[^"]*"' "$PREVIOUS_LOCAL_MANIFEST_FILE" | sed -n 's/.*path="\([^"]*\)".*/\1/p')

        if [ -n "$OLD_PROJECT_PATHS" ]; then
            echo "Identified old project paths for cleanup:"
            echo "$OLD_PROJECT_PATHS"

            for project_path in $OLD_PROJECT_PATHS; do
                FULL_PATH_TO_CLEAN="$AOSP_SOURCE_DIR/$project_path"
                if [ -d "$FULL_PATH_TO_CLEAN" ]; then
                    echo "Removing old project directory: $FULL_PATH_TO_CLEAN"
                    rm -rf "$FULL_PATH_TO_CLEAN"
                else
                    echo "Directory not found for cleanup (might have been removed already): $FULL_PATH_TO_CLEAN"
                fi
            done
        else
            echo "No project paths found in previous local manifest for cleanup."
        fi

        echo "Removing previous local manifest file: $PREVIOUS_LOCAL_MANIFEST_FILE"
        rm -f "$PREVIOUS_LOCAL_MANIFEST_FILE"
    fi
    # Clear the tracking file regardless, as the old manifest is processed
    > .local_manifest_path.tmp
fi

# --- Repo Init for main AOSP manifest ---
echo "Initializing repo with AOSP main manifest from $AOSP_MANIFEST_URL on branch $AOSP_MANIFEST_BRANCH"
# Use --no-repo-verify to avoid issues with older repo versions or non-standard manifests
repo init -u "$AOSP_MANIFEST_URL" -b "$AOSP_MANIFEST_BRANCH" --depth=1 --git-lfs || { echo "Repo init failed for AOSP main manifest"; exit 1; }

# --- Handle LOCAL_MANIFEST_URL ---
if [ -n "$LOCAL_MANIFEST_URL" ]; then
    echo "Fetching local manifest from: $LOCAL_MANIFEST_URL"
    # Generate a unique filename for the local manifest to avoid conflicts
    # Use a fixed name for simplicity for now, assuming only one custom manifest is active
    MANIFEST_FILENAME="jenkins_custom_manifest.xml"
    LOCAL_MANIFEST_PATH=".repo/local_manifests/$MANIFEST_FILENAME"

    # Fetch the local manifest content
    if curl -o "$LOCAL_MANIFEST_PATH" "$LOCAL_MANIFEST_URL"; then
        echo "Local manifest successfully downloaded to $LOCAL_MANIFEST_PATH"
        # Track the path of the newly downloaded local manifest for cleanup
        echo "$LOCAL_MANIFEST_PATH" > .local_manifest_path.tmp
    else
        echo "Failed to download local manifest from $LOCAL_MANIFEST_URL"
        exit 1
    fi
else
    echo "No LOCAL_MANIFEST_URL provided. Skipping custom local manifest."
fi

# --- Repo Sync ---
echo "Starting repo sync..."
repo sync -c --no-clone-bundle --no-tags --optimized-fetch --prune --force-sync -j8 || { echo "Repo sync failed"; exit 1; }

echo "Syncing Source stage complete."
