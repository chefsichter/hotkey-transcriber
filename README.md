# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**🎙️ Live dictation tool with Whisper**

With Hotkey Transcriber you can start and stop short audio recordings via a hotkey (Alt+R). The recognized text is automatically pasted into the active window.

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
- 🐍 Python 3.10+
- 🦊 Git
- OS-specific libraries:
  - 🐧 Linux (Debian/Ubuntu): `sudo apt install python3-venv python3-dev portaudio19-dev`
  - 🪟 Windows: Visual Studio Build Tools (for native dependencies)

## ⚙️ Installation

### 1️⃣ One-step installer

Use the one-shot setup script (`tools/setup_env.py`) to automatically create a virtual environment and install all dependencies, including PyTorch:

```bash
python3 tools/setup_env.py
```

On Windows:
```powershell
py tools/setup_env.py
```

### 2️⃣ Manual installation

1. Clone the repository:
   ```bash
   git clone <REPO_URL>
   cd hotkey-transcriber
   ```

2. Create and activate a virtual environment:
   - Linux/macOS:
     ```bash
     python3 -m venv .venv && source .venv/bin/activate
     ```
   - Windows PowerShell:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - Windows CMD:
     ```cmd
     python -m venv .venv
     .\.venv\Scripts\activate.bat
     ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

4. Optional: Choose a PyTorch build:
   - CPU-only:
     ```bash
     pip install torch==2.2.* torchvision==0.17.* torchaudio==2.2.* --index-url https://download.pytorch.org/whl/cpu
     ```
   - ROCm 6.3 (AMD GPU):
     ```bash
     pip install torch==2.2.2+rocm6.3 torchvision==0.17.2+rocm6.3 torchaudio==2.2.2+rocm6.3 --index-url https://download.pytorch.org/whl/rocm6.3
     ```

## 🐧 Linux-specific steps
- When installed system-wide (`sudo pip install .`), the desktop entry and icon are automatically placed under `/usr/share/applications` and `/usr/share/icons/hicolor/256x256/apps`.
- For user installations, copy manually:
  ```bash
  cp resources/linux/hotkey_transcriber.desktop ~/.local/share/applications/
  cp resources/icon/hotkey-transcriber.png ~/.local/share/icons/hicolor/256x256/apps/
  ```

## 🪟 Windows-specific steps
- After activating the virtual environment, run:
  ```cmd
  hotkey-transcriber
  ```
- The application will run in the system tray.

## 🎉 Usage
1. Launch the app with `hotkey-transcriber`.
2. A tray icon will appear.
3. Press `Alt+R` to start recording. A red icon indicates recording.
4. Release `R` to stop. The recognized text will be pasted and copied.
5. Use the tray menu to adjust the transcription interval, language, or exit.

## ⚙️ Configuration
Default settings are stored in `~/.config/hotkey-transcriber/config.json`. Model size, interval, and language choices are preserved automatically.

## 💡 Tips & Tricks
- Use short intervals (e.g. **0.5s**) for fluid dictation.
- Choose lighter models (`tiny` or `base`) on less powerful hardware.

## 📄 Contributing
- Report issues via GitHub Issues.
- Pull requests are welcome.
- See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details.

## 📜 License
This project is licensed under the [MIT License](LICENSE).
