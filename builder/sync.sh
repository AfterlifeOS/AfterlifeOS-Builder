#!/bin/bash

# Arguments:
# 1: LOCAL_MANIFEST_URL (optional)
# AOSP_MANIFEST_URL and AOSP_MANIFEST_BRANCH are read from environment variables

set -o pipefail

LOCAL_MANIFEST_URL="$1"
MANIFEST_FILENAME="jenkins_custom_manifest.xml"
LOCAL_MANIFEST_PATH=".repo/local_manifests/$MANIFEST_FILENAME"

echo "Starting Syncing Source stage..."

# --- 1. CLEANUP PREVIOUS CUSTOM MANIFEST (Before Repo Init) ---
# We must do this BEFORE repo init because if the old manifest has a bad remote,
# repo init might fail even if we intend to replace it later.
if [ -f "$LOCAL_MANIFEST_PATH" ]; then
    echo "Found previous custom manifest ($MANIFEST_FILENAME). Starting cleanup..."
    
    # Extract paths using python
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
        # Check for previous device to optimize sync
        LAST_DEVICE_FILE=".last_build_device.tmp"
        LAST_DEVICE=""
        if [ -f "$LAST_DEVICE_FILE" ]; then
            LAST_DEVICE=$(cat "$LAST_DEVICE_FILE")
        fi

        if [ "$INSTALLCLEAN" == "No" ] && [ -n "$LAST_DEVICE" ] && [ "$DEVICE" == "$LAST_DEVICE" ]; then
            echo "Skipping cleanup of old trees: INSTALLCLEAN is 'No' and Device ($DEVICE) matches previous build."
        else
            echo "Cleaning up trees from previous manifest..."
            for path in $OLD_PATHS; do
                if [ -d "$path" ]; then
                    echo "Removing directory: $path"
                    rm -rf "$path"
                fi
            done
        fi
    fi

    echo "Removing old manifest file: $LOCAL_MANIFEST_PATH"
    rm -f "$LOCAL_MANIFEST_PATH"
fi

# --- 2. REPO INIT ---
echo "Ensuring local manifests directory exists..."
mkdir -p ".repo/local_manifests" || { echo "Failed to create .repo/local_manifests"; exit 1; }

# Handle Auth for Private Manifest
#if [ -n "$GITHUB_TOKEN" ]; then
#    echo "Configuring git credential helper for GitHub..."
    # Use git config instead of embedding token in URL to prevent leaks in .git/config
#    git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
#fi

echo "Initializing repo with AOSP main manifest from $AOSP_MANIFEST_URL on branch $AOSP_MANIFEST_BRANCH"
repo init -u "$AOSP_MANIFEST_URL" -b "$AOSP_MANIFEST_BRANCH" --depth=1 --git-lfs || { echo "Repo init failed for AOSP main manifest"; exit 1; }

# --- 3. APPLY NEW CUSTOM MANIFEST ---
if [ -n "$LOCAL_MANIFEST_URL" ]; then
    echo "Fetching new local manifest from: $LOCAL_MANIFEST_URL"
    if curl -L -o "$LOCAL_MANIFEST_PATH" "$LOCAL_MANIFEST_URL"; then
        echo "Local manifest successfully downloaded."
    else
        echo "Failed to download local manifest."
        exit 1
    fi
else
    echo "No LOCAL_MANIFEST_URL provided. Skipping custom local manifest."
fi

# --- 4. REPO SYNC ---
echo "Starting repo sync..."
repo sync -c --no-clone-bundle --no-tags --optimized-fetch --prune --force-sync -j8 || { echo "Repo sync failed"; exit 1; }

echo "Syncing Source stage complete."
