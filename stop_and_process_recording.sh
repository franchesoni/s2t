#!/bin/bash

# Stop recording
kill $(cat $HOME/s2t/tmp/recording_pid)

# Transcribe audio
source $HOME/env_sandbox/bin/activate
whisper $HOME/s2t/tmp/recording.wav --model tiny.en --output_dir="${HOME}/s2t/tmp/" --output_format="txt"
deactivate

# Temporary file for transcription
TRANSCRIPTION_FILE="$HOME/s2t/tmp/recording.txt"

# Copy transcription to clipboard
xclip -selection clipboard < $TRANSCRIPTION_FILE

# Optional: Notify the user that transcription is complete
notify-send "Transcription Complete" "Your speech has been transcribed and is now in the clipboard."

# Clean up
rm -rf $HOME/s2t/tmp/



