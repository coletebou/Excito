#!/bin/bash
# Convert a PEER NGA .AT2 file to RSPMatch .acc format
#
# Usage: ./convert_at2.sh input.AT2 output.acc
#
# PEER AT2 format:
#   Line 1: header
#   Line 2: event description
#   Line 3: "ACCELERATION TIME SERIES IN UNITS OF G"
#   Line 4: "NPTS= 7814, DT= .0050 SEC,"
#   Line 5+: acceleration values (multiple per line, free format)
#
# RSPMatch acc format:
#   Line 1: title
#   Line 2: nPts dt nAdded
#   Line 3+: acceleration values

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 input.AT2 [output.acc]"
    echo "  Converts PEER NGA AT2 format to RSPMatch acc format."
    echo "  If output is omitted, replaces .AT2 extension with .acc"
    exit 1
fi

INPUT="$1"
if [ $# -ge 2 ]; then
    OUTPUT="$2"
else
    OUTPUT="${INPUT%.AT2}.acc"
    OUTPUT="${OUTPUT%.at2}.acc"
fi

if [ ! -f "$INPUT" ]; then
    echo "Error: $INPUT not found"
    exit 1
fi

# Extract title from line 2
TITLE=$(sed -n '2p' "$INPUT")

# Parse NPTS and DT from line 4
LINE4=$(sed -n '4p' "$INPUT")
NPTS=$(echo "$LINE4" | grep -oP 'NPTS=\s*\K[0-9]+')
DT=$(echo "$LINE4" | grep -oP 'DT=\s*\K[.0-9]+')

if [ -z "$NPTS" ] || [ -z "$DT" ]; then
    echo "Error: Could not parse NPTS and DT from line 4:"
    echo "  $LINE4"
    exit 1
fi

# Write output
echo "$TITLE" > "$OUTPUT"
echo "$NPTS $DT 0" >> "$OUTPUT"
tail -n +5 "$INPUT" >> "$OUTPUT"

echo "Converted: $INPUT -> $OUTPUT"
echo "  NPTS=$NPTS  DT=$DT  Title: $TITLE"
