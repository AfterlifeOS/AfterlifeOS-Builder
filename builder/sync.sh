#!/bin/bash

# Arguments:
# 1: LOCAL_MANIFEST_URL (optional)
# AOSP_MANIFEST_URL and AOSP_MANIFEST_BRANCH are read from environment variables

LOCAL_MANIFEST_URL="$1"

echo "Starting Syncing Source stage..."

# --- Initialize directories and tracking files ---
echo "Ensuring local manifests directory exists..."
mkdir -p ".repo/local_manifests" || { echo "Failed to create .repo/local_manifests"; exit 1; }

# --- Repo Init for main AOSP manifest ---
echo "Initializing repo with AOSP main manifest from $AOSP_MANIFEST_URL on branch $AOSP_MANIFEST_BRANCH"
repo init -u "$AOSP_MANIFEST_URL" -b "$AOSP_MANIFEST_BRANCH" --depth=1 --git-lfs || { echo "Repo init failed for AOSP main manifest"; exit 1; }

# --- Handle LOCAL_MANIFEST_URL ---
if [ -n "$LOCAL_MANIFEST_URL" ]; then
    echo "Fetching local manifest from: $LOCAL_MANIFEST_URL"
    MANIFEST_FILENAME="jenkins_custom_manifest.xml"
    LOCAL_MANIFEST_PATH=".repo/local_manifests/$MANIFEST_FILENAME"

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
