# Linux Speech-to-Text with Whisper
This project enables speech-to-text functionality on Linux using OpenAI's Whisper. It allows users to record audio with a press of a key (F9 by default), transcribe the audio to text using Whisper, and automatically paste the transcribed text where the cursor is located. This functionality is particularly useful for quickly converting speech into text without navigating through multiple applications.

## Prerequisites
Before you start, ensure you have the following installed on your Linux system:

**`ffmpeg`** for audio recording.
**`xclip`** for clipboard management.
**`whisper`** for audio transcription.
A Python virtual environment with Whisper installed (`$HOME/env_sandbox` in this guide, if yours is different, modify `stop_and_process_recording.sh` with yours).
You can install ffmpeg and xclip using your distribution's package manager. For Whisper, follow the installation instructions provided by OpenAI.

## Setup
### 1. Clone the Repository
Clone this repository to your local machine:

```
git clone https://github.com/franchesoni/linux-speech-to-text.git
cd linux-speech-to-text
```
### 2. Configure Keybindings
**Disable Key Repeat for F9**: Add **`xset -r 75`** to your **`~/.profile`** to disable key repeat for F9. Log out and log back in for the change to take effect.

**Set Up `xbindkeys`**: Install **`xbindkeys`** and create a **`.xbindkeysrc`** in your home directory with the following content:

```
"/path/to/linux-speech-to-text/start_recording.sh"
    m:0x0 + c:75

"/path/to/linux-speech-to-text/stop_and_process_recording.sh"
    Release + m:0x0 + c:75
```
Replace **`/path/to/linux-speech-to-text/`** with the actual path to the cloned repository.

### 3. Scripts Configuration
**Modify the Scripts**: Ensure **`start_recording.sh`** and **`stop_and_process_recording.sh`** are executable. If necessary, modify the scripts to match your system configuration, such as the path to your Python virtual environment.
```
chmod +x start_recording.sh stop_and_process_recording.sh
```

### 4. Using the Speech-to-Text Functionality
**Start Recording**: Press and hold F9 to start recording your speech.
**Stop Recording and Transcribe**: Release F9 to stop recording. The audio will be transcribed to text using Whisper, and the text will be automatically pasted from the clipboard to where your cursor is located.

## Troubleshooting
If the transcription does not work, ensure Whisper is correctly installed in your virtual environment and that the scripts point to the correct path of the virtual environment.
Make sure `ffmpeg` and `xclip` are correctly installed and accessible from your PATH.

## Contributions
Contributions are welcome! If you have improvements or bug fixes, please open a pull request or issue.

## Credit
https://chat.openai.com/share/db168b73-7dfe-4467-a450-35791e48403b