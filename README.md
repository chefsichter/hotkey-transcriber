🇬🇧 [English](./README.md) | 🇩🇪 [German](./README.de.md)

# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎙️ Live dictation tool with Whisper

With Hotkey Transcriber you can transcribe in real time (Speech-To-Text) using a key combination (Alt+R). The recognized text is automatically inserted into the active window.

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
- 🔊 Live dictation locally with OpenAI Whisper (via `faster-whisper`)
- ⌨️ Recording via hotkey (Alt+R)
- 🖥️ Tray icon (Windows &amp; Linux)
- 📋 Automatic insertion of the recognized transcript
- ⚙️ Adjustable transcription interval and recognition language

## 🛠️ Requirements

Hotkey Transcriber uses `faster-whisper` in the background, an optimized whisper implementation for real-time speech recognition.

A GPU is recommended for smooth, almost lag-free transcription:
  - NVIDIA GPUs with CUDA drivers (&gt;=11.7).
  - AMD GPUs via ROCm are currently a Linux-focused path for this stack (`faster-whisper`/CTranslate2), not a native Windows setup.

Without a GPU (CPU-only), transcription is also possible, but significantly slower and with a latency of several seconds per recording interval.

On first start, the selected Whisper model is downloaded once from Hugging Face and then reused from the local cache. An internet connection is required for this initial download.

On Windows, when an AMD GPU is detected, the app now prepares and uses a WSL backend automatically. You can override this with `HOTKEY_TRANSCRIBER_BACKEND` (`auto`, `native`, `wsl_amd`).

### Simple installer (Linux & Windows)

You can use the local installer scripts directly (including autostart choice):

- Linux:
  ```bash
  bash ./tools/install_linux.sh --autostart=ask
  ```
- Windows (PowerShell):
  ```powershell
  .\tools\install_windows.ps1 -Autostart ask
  ```

Autostart values: `ask`, `on`, `off`.
On Windows, the installer also creates a Start Menu entry (`Hotkey Transcriber`).

Uninstall:

- Linux:
  ```bash
  bash ./tools/uninstall_linux.sh
  ```
- Windows (PowerShell):
  ```powershell
  .\tools\uninstall_windows.ps1
  ```

### 🧰 Manual installation (pipx / git)

pipx is required to install the application in isolation:

1. pipx:
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
2. Direct installation from the Git repository:
   ```bash
   pipx install git+https://github.com/chefsichter/hotkey-transcriber
   ```

### Windows 11 + AMD (ROCm via WSL)

1. Install AMD Software: Adrenalin Edition for Windows (includes WSL support), then reboot.
2. Open elevated PowerShell in this repo and run:
   ```powershell
   .\tools\setup_wsl_amd.ps1
   ```
3. Install/start (recommended):
   ```powershell
   .\tools\install_windows.ps1 -Autostart ask
   ```
   The installer sets `HOTKEY_TRANSCRIBER_BACKEND=auto` and configures tray-only startup.

   Manual alternative:
   ```powershell
   $env:HOTKEY_TRANSCRIBER_BACKEND="auto"
   hotkey-transcriber
   ```

### Windows + AMD native ROCm (experimental)

If you already have the ROCm Windows Python environment from AMD's guide (`rocm-sdk-core`, `rocm-sdk-devel`, ROCm PyTorch in a Python 3.12 venv), you can rebuild `ctranslate2` with HIP for native Windows use:

```powershell
.\tools\build_ctranslate2_rocm_windows.ps1
```

Detailed step-by-step manual (German):
- [Windows ROCm + CTranslate2 manual](./tools/WINDOWS_ROCM_NATIVE_MANUAL.de.md)

Then start the app with native backend:

```powershell
$env:HOTKEY_TRANSCRIBER_BACKEND="native"
$env:HOTKEY_TRANSCRIBER_ROCM_ROOT="C:\rdev\_rocm_sdk_devel"
hotkey-transcriber
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
3. You can use the tray menu to change the transcription interval, recognition language, and autostart, or exit the program.
4. Model selection (tray icon → "Select model"):
    - Models: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `TheChola/whisper-large-v3-turbo-german-faster-whisper`
    - Smaller models: reduced VRAM &amp; CPU requirements → faster transcription (slightly lower accuracy)
    - VRAM recommendation: `tiny`/`base`: 2-4 GB; `small`/`medium`/`large*`: ≥6 GB

## ⚙️ Configuration
Default values are saved in a JSON file under `~/.config/hotkey-transcriber/config.json`. Settings such as model size, interval and detection language are automatically retained.

## 💡 Tips &amp; tricks
- Use short intervals (e.g. **0.5s**) for smooth dictation.
- Choose lighter models (`tiny` or `base`) on weak hardware.

## 📄 Contribute
- Report bugs via Issues
- Pull requests welcome
- See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details

## 📜 License
This project is licensed under the [MIT License](LICENSE).
