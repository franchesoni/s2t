#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="${S2T_TMP_DIR:-"$SCRIPT_DIR/tmp"}"
PID_FILE="$TMP_DIR/recording_pid"
DEBOUNCE_FILE="$TMP_DIR/last_toggle"
MIN_SECONDS_BETWEEN_TOGGLES="${S2T_TOGGLE_DEBOUNCE_SECONDS:-2}"

mkdir -p "$TMP_DIR"

now="$(date +%s)"
last_toggle=0
if [ -f "$DEBOUNCE_FILE" ]; then
  last_toggle="$(cat "$DEBOUNCE_FILE" 2>/dev/null || printf '0')"
fi

if [ "$((now - last_toggle))" -lt "$MIN_SECONDS_BETWEEN_TOGGLES" ]; then
  printf '%s\n' "$now" > "$DEBOUNCE_FILE"
  exit 0
fi
printf '%s\n' "$now" > "$DEBOUNCE_FILE"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  exec "$SCRIPT_DIR/stop_and_process_recording.sh"
fi
rm -f "$PID_FILE"

exec "$SCRIPT_DIR/start_recording.sh"
