# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎙️ Live dictation tool with Whisper

With Hotkey Transcriber you can start and stop short voice recordings using a key combination (Alt+R). The recognized text is automatically pasted into the active window and copied to the clipboard.

## 📑 Table of contents
- [✨ Features](#features)
- [🛠️ Requirements](#requirements)
- [⚙️ Installation](#installation)
- [🪟 Start program](#start program)
- [🎉 Usage](#usage)
- [⚙️ Configuration](#configuration)
- [💡 Tips &amp; tricks](#tips--tricks)
- [📄 Contribute](#contribute)
- [📜 License](#license)

## ✨ Features
- 🔊 Live dictation with OpenAI Whisper (via `faster-whisper`)
- ⌨️ Recording via hotkey (Alt+R)
- 🖥️ Tray icon (Windows &amp; Linux)
- 📋 Automatic insertion of the transcript
- ⚙️ Adjustable transcription interval and language

## 🛠️ Requirements

Hotkey Transcriber uses `faster-whisper` in the background, an optimized whisper implementation for real-time speech recognition.

A GPU is recommended for smooth, almost lag-free transcription:
  - NVIDIA GPUs with CUDA drivers (&gt;=11.7) or
  - AMD GPUs with ROCm support enabled.

Without a GPU (CPU-only), transcription is also possible, but significantly slower and with a latency of several seconds per recording interval.

## ⚙️ Installation
  
### 🎉 Simple installation

Go to the GitHub releases page: https://github.com/chefsichter/hotkey-transcriber/releases and download the package for your system.

- Linux (AppImage):

  ```bash
  chmod +x hotkey-transcriber-*.AppImage
  ./hotkey-transcriber-*.AppImage
  ```

- Windows (EXE):

  Download the file `hotkey-transcriber-*.exe` and execute it by double-clicking.

### 🧰 Manual installation

#### Install pipx

pipx is required to install the application in isolation:

- On Linux:
  ```bash
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  # Restart shell or log in again
  ```
  Or via package manager (Debian/Ubuntu):
  ```bash
  sudo apt update
  sudo apt install pipx
  ```

- On Windows (PowerShell):
  ```powershell
  py -m pip install --user pipx
  py -m pipx ensurepath
  # Restart PowerShell
  ```
1. Direct installation from the Git repository (simple):
   ```bash
   pipx install git+https://github.com/chefsichter/hotkey-transcriber
   ```

   or

2. Manual installation from the local clone:
   ```bash
   git clone https://github.com/chefsichter/hotkey-transcriber.git
   cd hotkey-transcriber
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   # Restart shell so that pipx is available in PATH
   pipx install .
   ```

## 🪟 Start program
- After activating the virtual environment, the command is sufficient:
  ```cmd
  hotkey-transcriber
  ```
- The program starts as a tray application.

## 🎉 Usage
1. Press `Alt+R` to start recording. A red symbol indicates recording.
2. Release `R` to stop the recording. The recognized text is pasted and copied.
3. You can use the tray menu to change the transcription interval, the language or exit the program.
4. Model selection (tray icon → "Select model"):
    - Models: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`
    - Smaller models: reduced VRAM &amp; CPU requirements → faster transcription (slightly lower accuracy)
    - VRAM recommendation: `tiny`/`base`: 2-4 GB; `small`/`medium`/`large*`: ≥6 GB

## ⚙️ Configuration
Default values are saved in a JSON file under `~/.config/hotkey-transcriber/config.json`. Settings such as model size, interval and language are automatically retained.

## 💡 Tips &amp; tricks
- Use short intervals (e.g. **0.5s**) for smooth dictation.
- Choose lighter models (`tiny` or `base`) on weak hardware.

## 📄 Contribute
- Report bugs via Issues
- Pull requests welcome
- See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details

## 📜 License
This project is licensed under the [MIT License](LICENSE).
