#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_DIR="$REPO_DIR/input"
BINARY="$REPO_DIR/RSPMatch99_Sub Files/rspmatch"
SEED="${1:-elcentro_prescaled.acc}"

TIMESTAMP=$(date +"%m_%d_%y_%H%M")
RUN_DIR="$REPO_DIR/output/multipass-${TIMESTAMP}"
mkdir -p "$RUN_DIR"

cp "$INPUT_DIR/target.tgt" "$RUN_DIR/"
cp "$INPUT_DIR/$SEED" "$RUN_DIR/seed.acc"

echo "=== RSPMatch Multi-Pass (Pre-scaled Seed) ==="
echo "Output: $RUN_DIR"
echo "Seed: $SEED"
echo ""

# 5 passes with no PGA scaling (pre-scaled record is already sized right)
PASS_ITERS=(  60    80   100   100   100 )
PASS_GAMMA=( 0.6   0.5   0.4   0.3   0.3 )
PASS_FMIN=(  0.2   0.2   0.2   0.2   0.2 )
PASS_FMAX=(  1.5   3.0   7.0  15.0  15.0 )
PASS_MAXFQ=( 1.5   3.0   7.0  15.0  15.0 )
PASS_GROUP=(  5     8    10    10     5  )
NUM_PASSES=5

CURRENT_ACC="seed.acc"

for i in $(seq 0 $((NUM_PASSES - 1))); do
    PASS=$((i + 1))

    PASS_DIR="$RUN_DIR/pass${PASS}"
    mkdir -p "$PASS_DIR"

    cp "$RUN_DIR/$CURRENT_ACC" "$PASS_DIR/input.acc"
    cp "$RUN_DIR/target.tgt" "$PASS_DIR/"

    cat > "$PASS_DIR/run.inp" << RUNINP
${PASS_ITERS[$i]}
0.005
${PASS_GAMMA[$i]}
7
1.0 1.0 0.1 ${PASS_MAXFQ[$i]}
0 1.0
1
1.0e-5
${PASS_GROUP[$i]}
${PASS_MAXFQ[$i]}
0.1 ${PASS_MAXFQ[$i]} 4
0
0 0.0
${PASS_FMIN[$i]} ${PASS_FMAX[$i]}
1
1.0
target.tgt
input.acc
matched.acc
matched.rsp
unmatched.rsp
RUNINP

    cat > "$PASS_DIR/master.inp" << MASTERINP
1
run.inp
MASTERINP

    echo "===== Pass $PASS/$NUM_PASSES: ${PASS_FMIN[$i]}-${PASS_FMAX[$i]} Hz, ${PASS_ITERS[$i]} iter, gamma=${PASS_GAMMA[$i]} ====="

    cd "$PASS_DIR"
    echo "master.inp" | "$BINARY" 2>&1 | tee log.txt | grep -E "full set" | tail -3

    if [ ! -f "$PASS_DIR/matched.acc" ]; then
        echo "ERROR: Pass $PASS failed"
        exit 1
    fi

    cp "$PASS_DIR/matched.acc" "$RUN_DIR/pass${PASS}_matched.acc"
    CURRENT_ACC="pass${PASS}_matched.acc"
    echo ""
done

cp "$RUN_DIR/pass${NUM_PASSES}/matched.acc" "$RUN_DIR/matched.acc"
cp "$RUN_DIR/pass${NUM_PASSES}/matched.rsp" "$RUN_DIR/matched.rsp"
cp "$RUN_DIR/pass${NUM_PASSES}/unmatched.rsp" "$RUN_DIR/unmatched.rsp"
cp "$INPUT_DIR/elcentro.acc" "$RUN_DIR/elcentro.acc"

echo "=== Final Spectrum Match ==="
grep -E "^\s+[0-9]+\.[0-9]+" "$RUN_DIR/matched.rsp" | awk '$3 > 0 {printf "  %8s Hz:  Target=%s  Matched=%s  Misfit=%+.1f%%\n", $1, $3, $4, ($4-$3)/$3*100}'
echo ""

if python3 -c "import matplotlib" 2>/dev/null; then
    python3 "$REPO_DIR/plot_results.py" "$RUN_DIR"
fi
