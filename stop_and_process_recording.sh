#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="${S2T_TMP_DIR:-"$SCRIPT_DIR/tmp"}"
UV_BIN="${UV_BIN:-}"
AUDIO_FILE="$TMP_DIR/recording.wav"
PID_FILE="$TMP_DIR/recording_pid"
LOCK_FILE="$TMP_DIR/recording.lock"
TRANSCRIPTION_FILE="$TMP_DIR/recording.txt"

# Load local configuration for desktop shortcuts, which do not inherit shell variables.
if [ -f "$SCRIPT_DIR/.env" ]; then
  while IFS='=' read -r key value; do
    key="${key#export }"
    case "$key" in
      FOUNDRY_API_KEY|S2T_ASR_BACKEND|S2T_AZURE_ENDPOINT|S2T_AZURE_LOCALES)
        value="${value%\"}"; value="${value#\"}"
        value="${value%\'}"; value="${value#\'}"
        export "$key=$value"
        ;;
    esac
  done < "$SCRIPT_DIR/.env"
fi

mkdir -p "$TMP_DIR"
exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

if [ ! -f "$PID_FILE" ]; then
  echo "s2t: no recording pid found." >&2
  exit 1
fi

mapfile -t pids < <(pgrep -f "ffmpeg .* -y $AUDIO_FILE" || true)
pid="$(cat "$PID_FILE")"
if [ "${#pids[@]}" -eq 0 ] && kill -0 "$pid" 2>/dev/null; then
  pids=("$pid")
fi

if [ "${#pids[@]}" -gt 0 ]; then
  kill -INT "${pids[@]}" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    [ -s "$AUDIO_FILE" ] && break
    sleep 0.1
  done
  if [ ! -s "$AUDIO_FILE" ]; then
    kill "${pids[@]}" 2>/dev/null || true
  fi
fi
rm -f "$PID_FILE"

if [ ! -s "$AUDIO_FILE" ]; then
  echo "s2t: recording file was not created or is empty: $AUDIO_FILE" >&2
  exit 1
fi

ASR_BACKEND="${S2T_ASR_BACKEND:-}"
if [ -z "$ASR_BACKEND" ]; then
  if [ -n "${FOUNDRY_API_KEY:-}" ]; then ASR_BACKEND=azure; else ASR_BACKEND=whisper; fi
fi

if [ "$ASR_BACKEND" = "whisper" ] && [ -z "$UV_BIN" ]; then
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
  elif [ -x "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
  else
    echo "s2t: uv is not installed. Install it from https://docs.astral.sh/uv/." >&2
    exit 1
  fi
fi

if [ "$ASR_BACKEND" = "whisper" ] && [ ! -x "$UV_BIN" ]; then
  echo "s2t: uv is not executable: $UV_BIN" >&2
  exit 1
fi

if [ "$ASR_BACKEND" = "azure" ]; then
  if [ -z "${FOUNDRY_API_KEY:-}" ]; then
    echo "s2t: FOUNDRY_API_KEY is not set." >&2
    exit 1
  fi
  endpoint="${S2T_AZURE_ENDPOINT:-https://swedencentral.stt.speech.microsoft.com}"
  endpoint="${endpoint/.stt.speech.microsoft.com/.api.cognitive.microsoft.com}"
  locales="${S2T_AZURE_LOCALES:-}"
  if [ -n "$locales" ]; then
    definition="$(python3 -c 'import json,sys; print(json.dumps({"locales": sys.argv[1].split(",")}))' "$locales")"
  else
    definition='{}'
  fi
  response_file="$TMP_DIR/azure_response.json"
  http_code="$(curl --silent --show-error --output "$response_file" --write-out '%{http_code}' \
    --request POST "${endpoint%/}/speechtotext/transcriptions:transcribe?api-version=2025-10-15" \
    --header "Ocp-Apim-Subscription-Key: $FOUNDRY_API_KEY" \
    --form "audio=@$AUDIO_FILE;type=audio/wav" \
    --form "definition=$definition;type=application/json")"
  if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
    echo "s2t: Azure transcription failed (HTTP $http_code). See $response_file" >&2
    exit 1
  fi
  python3 - "$response_file" "$TRANSCRIPTION_FILE" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
text = "\n".join(
    phrase.get("text", "").strip()
    for phrase in payload.get("combinedPhrases", [])
    if phrase.get("text", "").strip()
)
if not text:
    raise SystemExit("s2t: Azure returned no transcript")
pathlib.Path(sys.argv[2]).write_text(text + "\n")
PY
  rm -f "$response_file"
elif [ "$ASR_BACKEND" = "whisper" ]; then
  "$UV_BIN" run --project "$SCRIPT_DIR" whisper "$AUDIO_FILE" \
    --model "${S2T_WHISPER_MODEL:-tiny}" \
    --output_dir="$TMP_DIR" \
    --output_format="txt"
else
  echo "s2t: unsupported S2T_ASR_BACKEND: $ASR_BACKEND" >&2
  exit 1
fi

if [ ! -f "$TRANSCRIPTION_FILE" ]; then
  echo "s2t: transcription file was not created: $TRANSCRIPTION_FILE" >&2
  exit 1
fi

# Copy transcription to clipboard
if command -v wl-copy >/dev/null 2>&1 && [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
  wl-copy < "$TRANSCRIPTION_FILE"
elif command -v xclip >/dev/null 2>&1; then
  xclip -selection clipboard < "$TRANSCRIPTION_FILE"
else
  echo "s2t: install wl-clipboard or xclip to copy the transcription." >&2
  exit 1
fi

notify-send "Transcription Complete" "Your speech has been transcribed and is now in the clipboard."

if [ "${S2T_AUTO_PASTE:-0}" = "1" ]; then
  sleep 0.1
  if [ "${XDG_SESSION_TYPE:-}" = "x11" ] && command -v xdotool >/dev/null 2>&1; then
    xdotool key ctrl+v
  else
    notify-send "Speech-to-text" "Clipboard is ready. Press Ctrl+V to paste."
  fi
fi

# Clean up
rm -f "$AUDIO_FILE" "$TRANSCRIPTION_FILE" "$LOCK_FILE"
