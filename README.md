# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**🎙️ Live dictation tool with Whisper**

With Hotkey Transcriber you can start and stop short audio recordings using the hotkey `Alt+R`. The recognized text is automatically inserted into the active window and copied to the clipboard.

## 📑 Table of Contents
- [✨ Features](#features)
- [🛠️ Requirements](#requirements)
- [⚙️ Installation](#installation)
- [🐧 Linux-specific steps](#linux-specific-steps)
- [🪟 Windows-specific steps](#windows-specific-steps)
- [🎉 Usage](#usage)
- [⚙️ Configuration](#configuration)
- [💡 Tips & Tricks](#tips--tricks)
- [📄 Contributing](#contributing)
- [📜 License](#license)

## ✨ Features
- 🔊 Live dictation with OpenAI Whisper (via `faster-whisper`)
- ⌨️ Recording via hotkey (Alt+R)
- 🖥️ System tray icon (Windows & Linux)
- 📋 Automatic insertion of the transcript
- ⚙️ Adjustable transcription interval and language

## 🛠️ Requirements

Hotkey Transcriber uses `faster-whisper`, an optimized Whisper implementation, under the hood for real-time speech recognition.

For smooth, near real-time transcription a GPU is recommended:
- NVIDIA GPUs with CUDA drivers (>=11.7)
- AMD GPUs with ROCm support

Without a GPU (CPU-only), transcription is possible but significantly slower, with a latency of several seconds per capture interval.

## ⚙️ Installation

### 🎉 Easy Installation

Go to the GitHub Releases page:
https://github.com/chefsichter/hotkey-transcriber/releases
and download the package for your system.

- **Linux (AppImage):**
  ```bash
  chmod +x hotkey-transcriber-*.AppImage
  ./hotkey-transcriber-*.AppImage
  ```

- **Windows (EXE):**
  Download `hotkey-transcriber-*.exe` and run it by double-clicking.

### 2️⃣ Manual Installation

1. **Direct installation from GitHub (easy):**
   ```bash
   pipx install git+https://github.com/chefsichter/hotkey-transcriber
   ```

   or

   **Manual installation from a local clone:**
   ```bash
   git clone https://github.com/chefsichter/hotkey-transcriber.git
   cd hotkey-transcriber
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   # Restart your shell so pipx is in your PATH
   pipx install .
   ```

## 🪟 Starting the app
- After installing (or activating your virtual environment), run:
  ```cmd
  hotkey-transcriber
  ```
- The program runs in the system tray.

## 🎉 Usage
1. Press **Alt+R** to start recording. A red icon indicates recording.
2. Release **R** to stop recording. The recognized text is inserted into the active window and copied to the clipboard.
3. Via the tray menu you can adjust the transcription interval, change the language, or quit the application.
4. **Model selection** (Tray icon → “Select model”):
   - Options: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`
   - Smaller models reduce VRAM & CPU usage → faster transcription (slightly lower accuracy)
   - VRAM guide: `tiny`/`base`: 2–4 GB; larger models (`small`, `medium`, `large*`): ≥6 GB


## ⚙️ Configuration
Default settings are stored in `~/.config/hotkey-transcriber/config.json`. Model, interval, and language preferences persist across restarts.

## 💡 Tips & Tricks
- Use short intervals (e.g. **0.5s**) for smoother dictation.
- On weaker hardware choose lightweight models (`tiny` or `base`).

## 📄 Contributing
- Report issues via GitHub Issues
- Pull requests welcome
- See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details

## 📜 License
This project is licensed under the [MIT License](LICENSE).