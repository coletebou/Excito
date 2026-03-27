#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_DIR="$REPO_DIR/input"
RUN_FILE="${1:-run.inp}"
BINARY="$REPO_DIR/RSPMatch99_Sub Files/rspmatch"

if [ ! -f "$INPUT_DIR/$RUN_FILE" ]; then
    echo "Error: $INPUT_DIR/$RUN_FILE not found"
    exit 1
fi

if [ ! -f "$BINARY" ]; then
    echo "Error: rspmatch binary not found. Compile first (see README.md)"
    exit 1
fi

# Create timestamped output directory
TIMESTAMP=$(date +"%m_%d_%y_%H%M")
RUN_DIR="$REPO_DIR/output/run-${TIMESTAMP}"
mkdir -p "$RUN_DIR"

# Read the data file paths from the run file (lines 17 and 18)
TARGET_FILE=$(sed -n '17p' "$INPUT_DIR/$RUN_FILE" | tr -d '[:space:]')
ACCEL_FILE=$(sed -n '18p' "$INPUT_DIR/$RUN_FILE" | tr -d '[:space:]')

# Copy input data files into the run directory so Fortran sees short paths
cp "$INPUT_DIR/$RUN_FILE" "$RUN_DIR/run.inp"
[ -f "$INPUT_DIR/$TARGET_FILE" ] && cp "$INPUT_DIR/$TARGET_FILE" "$RUN_DIR/"
[ -f "$INPUT_DIR/$ACCEL_FILE" ] && cp "$INPUT_DIR/$ACCEL_FILE" "$RUN_DIR/"

# Build a run file with short output names (all in current directory)
TEMP_RUN="$RUN_DIR/_run.inp"
head -n 18 "$RUN_DIR/run.inp" > "$TEMP_RUN"
echo "matched.acc" >> "$TEMP_RUN"
echo "matched.rsp" >> "$TEMP_RUN"
echo "unmatched.rsp" >> "$TEMP_RUN"

# Build master file
TEMP_MASTER="$RUN_DIR/_master.inp"
echo "1" > "$TEMP_MASTER"
echo "_run.inp" >> "$TEMP_MASTER"

echo "=== RSPMatch Run ==="
echo "Output: $RUN_DIR"
echo "Run file: $RUN_FILE"
echo "Target: $TARGET_FILE"
echo "Accelerogram: $ACCEL_FILE"
echo ""

# Run from the output directory so all paths are short
cd "$RUN_DIR"
echo "_master.inp" | "$BINARY" 2>&1 | tee log.txt

# Clean up temp files
rm -f "$RUN_DIR/_run.inp" "$RUN_DIR/_master.inp"

echo ""
echo "=== Complete ==="
echo "Output directory: $RUN_DIR"
echo ""
ls -lh "$RUN_DIR"
