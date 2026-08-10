#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="${S2T_TMP_DIR:-"$SCRIPT_DIR/tmp"}"
AUDIO_FILE="$TMP_DIR/recording.wav"
PID_FILE="$TMP_DIR/recording_pid"
LOCK_FILE="$TMP_DIR/recording.lock"
LOG_FILE="$TMP_DIR/ffmpeg.log"
BACKEND="${S2T_AUDIO_BACKEND:-pulse}"
INPUT="${S2T_AUDIO_INPUT:-default}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "s2t: ffmpeg is not installed." >&2
  exit 1
fi

mkdir -p "$TMP_DIR"
exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "s2t: recording is already running." >&2
  exit 0
fi
rm -f "$PID_FILE"

rm -f "$AUDIO_FILE" "$LOG_FILE"

nohup ffmpeg -hide_banner -nostdin -loglevel warning \
  -f "$BACKEND" -i "$INPUT" \
  -ar 16000 -ac 1 -y "$AUDIO_FILE" >"$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"

sleep 0.3
if ! kill -0 "$pid" 2>/dev/null; then
  echo "s2t: ffmpeg failed to start recording. Log follows:" >&2
  sed -n '1,120p' "$LOG_FILE" >&2 || true
  rm -f "$PID_FILE"
  exit 1
fi

notify-send "Recording" "Speech-to-text recording started." 2>/dev/null || true
