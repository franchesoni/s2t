#!/bin/bash

paste_transcription() {
    local paste_mode="${S2T_PASTE_MODE:-auto}"
    local window_id=""
    local window_class=""
    local window_name=""
    local window_pid=""
    local window_command=""
    local window_signature=""
    local log_file="${S2T_PASTE_LOG:-/tmp/s2t-paste.log}"

    if [[ "$paste_mode" == "auto" ]]; then
        window_id=$(xdotool getactivewindow 2>/dev/null || true)
        if [[ -n "$window_id" ]]; then
            window_class=$(xdotool getwindowclassname "$window_id" 2>/dev/null || true)
            window_name=$(xdotool getwindowname "$window_id" 2>/dev/null || true)
            window_pid=$(xdotool getwindowpid "$window_id" 2>/dev/null || true)
            if [[ -n "$window_pid" ]]; then
                window_command=$(ps -p "$window_pid" -o comm= -o args= 2>/dev/null | head -n 1 || true)
            fi
        fi

        window_signature=$(printf '%s\n%s\n%s\n' "$window_class" "$window_name" "$window_command")

        if printf '%s\n' "$window_signature" \
            | grep -Eiq 'terminal|console|xterm|rxvt|urxvt|konsole|kitty|alacritty|wezterm|ghostty|foot|tilix|terminator|qterminal|lxterminal|mate-terminal|xfce4-terminal|gnome-terminal|ptyxis|st-256color|blackbox|warp|tabby|rio|contour|codex|claude|opencode|aider|agent|gpt-'; then
            paste_mode="terminal"
        elif [[ -z "${window_signature//[[:space:]]/}" ]]; then
            paste_mode="terminal"
        else
            paste_mode="default"
        fi

        printf '%s paste_mode=%s window_id=%s class=%q name=%q pid=%s command=%q\n' \
            "$(date -Is)" "$paste_mode" "$window_id" "$window_class" "$window_name" "$window_pid" "$window_command" \
            >> "$log_file" 2>/dev/null || true
    fi

    case "$paste_mode" in
        terminal)
            xdotool key --clearmodifiers ctrl+shift+v
            ;;
        default)
            xdotool key --clearmodifiers ctrl+v
            ;;
        *)
            notify-send "S2T paste mode error" "Unknown S2T_PASTE_MODE: $paste_mode"
            xdotool key --clearmodifiers ctrl+v
            ;;
    esac
}

# Stop recording
kill $(cat $HOME/s2t/tmp/recording_pid)

AUDIO_FILE="$HOME/s2t/tmp/recording.wav"
TEXT_FILE="$HOME/s2t/tmp/recording.txt"

# Try warm daemon first (sub-second). Fall back to direct faster-whisper+tiny (~2s).
if curl -sf --max-time 0.5 http://127.0.0.1:7979/health > /dev/null 2>&1; then
    TEXT=$(curl -sf --max-time 15 -X POST http://127.0.0.1:7979/transcribe \
        -H "Content-Type: application/json" \
        -d "{\"path\":\"$AUDIO_FILE\"}" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['text'])" 2>/dev/null)
    echo "$TEXT" > "$TEXT_FILE"
else
    $HOME/env_sandbox/bin/python3 $HOME/s2t/transcribe.py "$AUDIO_FILE" "$TEXT_FILE"
fi

# Apply phrase expansions (phrases.json)
$HOME/env_sandbox/bin/python3 $HOME/s2t/expand_phrases.py "$TEXT_FILE"

# Copy transcription to clipboard
xclip -selection clipboard < "$TEXT_FILE"

# Notify
notify-send "Transcription Complete" "$(cat "$TEXT_FILE")"

# Ensure the clipboard has time to update
sleep 0.1

# Simulate the paste action
paste_transcription

# Clean up
rm -rf $HOME/s2t/tmp/
