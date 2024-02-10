#!/bin/bash

# Start recording audio
rm -rf $HOME/s2t/tmp
mkdir $HOME/s2t/tmp
AUDIO_FILE="$HOME/s2t/tmp/recording.wav"
ffmpeg -f alsa -i default -ar 44100 -ac 2 $AUDIO_FILE &
echo $! > $HOME/s2t/tmp/recording_pid

