#!/usr/bin/env bash
# Bootstrap: ensure faster-whisper is installed and the tiny model is pre-cached.
set -euo pipefail

VENV="$HOME/env_sandbox"

echo "[s2t] Checking faster-whisper..."
if ! "$VENV/bin/pip" show faster-whisper > /dev/null 2>&1; then
    echo "[s2t] Installing faster-whisper..."
    "$VENV/bin/pip" install faster-whisper
else
    echo "[s2t] faster-whisper already installed."
fi

echo "[s2t] Pre-warming Whisper tiny model cache..."
"$VENV/bin/python3" - <<'PY'
from faster_whisper import WhisperModel
WhisperModel("tiny", device="cpu", compute_type="int8")
print("[s2t] Model cached and ready.")
PY
