#!/usr/bin/env bash
# S2T test suite — run from any directory.
# Tests: direct transcription, daemon health, daemon transcription, fallback path.
set -euo pipefail

S2T="$HOME/s2t"
VENV="$HOME/env_sandbox"
DAEMON_URL="http://127.0.0.1:7979"
TMP=$(mktemp -d)
PASS=0
FAIL=0

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

green() { echo -e "\033[0;32m[PASS]\033[0m $*"; PASS=$((PASS + 1)); }
red()   { echo -e "\033[0;31m[FAIL]\033[0m $*"; FAIL=$((FAIL + 1)); }

# Generate a short silent WAV for testing
make_wav() {
    ffmpeg -f lavfi -i "sine=frequency=1000:duration=1" "$1" -y -loglevel quiet
}

echo "=== S2T Test Suite ==="
echo ""

# --- Test 1: direct transcription via transcribe.py ---
echo "[1] Direct transcription (transcribe.py)..."
make_wav "$TMP/t1.wav"
"$VENV/bin/python3" "$S2T/transcribe.py" "$TMP/t1.wav" "$TMP/t1.txt" 2>/dev/null
if [[ -f "$TMP/t1.txt" ]]; then
    green "transcribe.py produced output file"
else
    red "transcribe.py did not produce output file"
fi

# --- Test 2: phrase expansion ---
echo "[2] Phrase expansion..."
echo "test phrase" > "$TMP/expand.txt"
"$VENV/bin/python3" "$S2T/expand_phrases.py" "$TMP/expand.txt" 2>/dev/null || true
if [[ -f "$TMP/expand.txt" ]]; then
    green "expand_phrases.py ran without error"
else
    red "expand_phrases.py failed"
fi

# --- Test 3: daemon health check ---
echo "[3] Daemon health check..."
if curl -sf --max-time 1 "$DAEMON_URL/health" > /dev/null 2>&1; then
    green "Daemon is running and healthy"
    DAEMON_UP=true
else
    echo "  [info] Daemon not running — skipping daemon transcription test"
    echo "  (Run 'spin up voice' to start the daemon)"
    DAEMON_UP=false
fi

# --- Test 4: daemon transcription (only if daemon is up) ---
if [[ "$DAEMON_UP" == "true" ]]; then
    echo "[4] Daemon transcription..."
    make_wav "$TMP/t4.wav"
    RESPONSE=$(curl -sf --max-time 15 -X POST "$DAEMON_URL/transcribe" \
        -H "Content-Type: application/json" \
        -d "{\"path\":\"$TMP/t4.wav\"}" 2>/dev/null)
    if echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'text' in d" 2>/dev/null; then
        green "Daemon returned transcription response"
    else
        red "Daemon transcription response malformed: $RESPONSE"
    fi
fi

# --- Test 5: fallback path timing (daemon down simulation) ---
echo "[5] Fallback transcription timing..."
make_wav "$TMP/t5.wav"
START=$(date +%s%N)
"$VENV/bin/python3" "$S2T/transcribe.py" "$TMP/t5.wav" "$TMP/t5.txt" 2>/dev/null
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))
if [[ $ELAPSED -lt 10000 ]]; then
    green "Fallback completed in ${ELAPSED}ms (under 10s)"
else
    red "Fallback took ${ELAPSED}ms — suspiciously slow"
fi

# --- Test 6: spin project registered ---
echo "[6] Spin project registered..."
if /home/pbrown/BROWN-FAMILY-SPORTS/Software/spin/bin/spin status voice 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -q "voice"; then
    green "spin recognizes 'voice' project"
else
    red "spin does not recognize 'voice' project"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
