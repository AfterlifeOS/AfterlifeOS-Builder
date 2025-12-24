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

# Define Log File
LOG_FILE="${WORKSPACE}/build.log"
PROGRESS_FILE="${WORKSPACE}/progress.txt"

# Redirect all stdout and stderr to the log file (and console)
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Starting Building stage..."

# --- PROGRESS PARSER (Background) ---
# Parses Ninja/Kati/Soong output: [ 10% 100/1000] Description...
rm -f "$PROGRESS_FILE"
(
    tail -n0 -F "$LOG_FILE" 2>/dev/null | \
    grep --line-buffered -P '^\[\s*[0-9]+% [0-9]+/[0-9]+' | \
    awk -v logfile="$PROGRESS_FILE" '{
        # Remove ANSI colors
        gsub(/\x1b\[[0-9;]*m/, "");
        
        # Regex to capture: [ PCT% COUNTS ] DESC
        # Match: [ 1% 10/1000] Compiling...
        # Group 1: PCT, Group 2: COUNTS, Group 3: ETA/EXTRA, Group 4: DESC
        match($0, /^\[\s*([0-9]+)% ([0-9]+\/[0-9]+)([^]]*)\] (.*)/, arr);
        
        if (arr[1] != "" && arr[2] != "") {
             # Format: PERCENT,COUNTS,DESC
             print arr[1] "," arr[2] "," arr[4] > logfile;
             fflush(logfile);
        }
    }'
) &
PARSER_PID=$!

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
m afterlife -j48 || { 
    kill $PARSER_PID 2>/dev/null
    echo "Build failed"; exit 1; 
}

# Kill parser
kill $PARSER_PID 2>/dev/null

echo "Building stage complete."
