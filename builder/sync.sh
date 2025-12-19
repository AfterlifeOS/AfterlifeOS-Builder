#!/bin/bash

# Arguments:
# 1: LOCAL_MANIFEST_URL (optional)
# AOSP_MANIFEST_URL and AOSP_MANIFEST_BRANCH are read from environment variables

set -o pipefail

LOCAL_MANIFEST_URL="$1"
LOG_FILE="${WORKSPACE}/sync.log"

echo "Logging sync output to: $LOG_FILE"

{
    echo "Starting Syncing Source stage..."

    # --- Clean up old error logs ---
    echo "Cleaning up old error logs..."
    rm -f out/error.log
    rm -f out/target/product/*/error.log

    # --- Initialize directories and tracking files ---
    echo "Ensuring local manifests directory exists..."
    mkdir -p ".repo/local_manifests" || { echo "Failed to create .repo/local_manifests"; exit 1; }

    # --- Repo Init for main AOSP manifest ---
    echo "Initializing repo with AOSP main manifest from $AOSP_MANIFEST_URL on branch $AOSP_MANIFEST_BRANCH"
    repo init -u "$AOSP_MANIFEST_URL" -b "$AOSP_MANIFEST_BRANCH" --depth=1 --git-lfs || { echo "Repo init failed for AOSP main manifest"; exit 1; }

    # --- Handle LOCAL_MANIFEST_URL ---
    if [ -n "$LOCAL_MANIFEST_URL" ]; then
        MANIFEST_FILENAME="jenkins_custom_manifest.xml"
        LOCAL_MANIFEST_PATH=".repo/local_manifests/$MANIFEST_FILENAME"

        # --- CLEANUP BASED ON OLD MANIFEST ---
        if [ -f "$LOCAL_MANIFEST_PATH" ]; then
            echo "Found existing local manifest. Cleaning up old trees..."
            # Extract paths using python to avoid regex fragility
            OLD_PATHS=$(python3 -c "
import xml.etree.ElementTree as ET
import os
try:
    tree = ET.parse('$LOCAL_MANIFEST_PATH')
    root = tree.getroot()
    for project in root.findall('project'):
        path = project.get('path')
        if path:
            print(path)
except Exception as e:
    print('')
")
            
            if [ -n "$OLD_PATHS" ]; then
                echo "Removing the following paths from old manifest:"
                echo "$OLD_PATHS"
                for path in $OLD_PATHS; do
                    if [ -d "$path" ]; then
                        echo "Removing $path..."
                        rm -rf "$path"
                    fi
                done
            fi
        fi
        # -------------------------------------

        echo "Fetching local manifest from: $LOCAL_MANIFEST_URL"
        
        # Fetch the local manifest content
        if curl -o "$LOCAL_MANIFEST_PATH" "$LOCAL_MANIFEST_URL"; then
            echo "Local manifest successfully downloaded to $LOCAL_MANIFEST_PATH"
        else
            echo "Failed to download local manifest from $LOCAL_MANIFEST_URL"
            exit 1
        fi
    else
        echo "No LOCAL_MANIFEST_URL provided. Skipping custom local manifest."
    fi

    # --- Repo Sync ---
    # The --prune flag will remove projects that are no longer in the manifest.
    # This is a safer alternative to the previous manual `rm -rf` logic.
    echo "Starting repo sync..."
    repo sync -c --no-clone-bundle --no-tags --optimized-fetch --prune --force-sync -j8 || { echo "Repo sync failed"; exit 1; }

    echo "Syncing Source stage complete."

} 2>&1 | tee "$LOG_FILE"
