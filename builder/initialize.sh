#!/bin/bash

echo "Starting Initialization stage..."

# Ensure we are in the AOSP source directory
AOSP_SOURCE_DIR="$HOME/android/source"
echo "Navigating to AOSP source directory: $AOSP_SOURCE_DIR"
cd "$AOSP_SOURCE_DIR" || { echo "Failed to navigate to $AOSP_SOURCE_DIR"; exit 1; }

# Create a directory for local manifests within the .repo folder
# This is where custom manifests will be placed by the sync script
LOCAL_MANIFESTS_DIR=".repo/local_manifests"
echo "Ensuring local manifests directory exists: $LOCAL_MANIFESTS_DIR"
mkdir -p "$LOCAL_MANIFESTS_DIR" || { echo "Failed to create $LOCAL_MANIFESTS_DIR"; exit 1; }

# Enable RBE
export USE_RBE=1

# Create a temporary file to store the path of the current local_manifest.xml
# This file will be used by subsequent builds to clean up old manifests
echo "Creating .local_manifest_path.tmp to track local manifest for cleanup."
touch .local_manifest_path.tmp

echo "Initialization complete."
