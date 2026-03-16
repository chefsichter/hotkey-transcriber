🇬🇧 [English](./README.md) | 🇩🇪 [German](./README.de.md)

# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎙️ Live dictation tool with Whisper

With Hotkey Transcriber you can transcribe in real time (Speech-To-Text) using a key combination (Alt+R). The recognized text is automatically inserted into the active window.

## 📑 Table of contents
- [✨ Features](#features)
- [🛠️ Requirements](#requirements)
- [⚙️ Installation](#installation)
- [🔄 Update](#update)
- [🪟 Start program](#start-program)
- [🎉 Usage](#usage)
- [⚙️ Configuration](#configuration)
- [🏗️ Architecture](#architecture)
- [🧑‍💻 Developer setup](#developer-setup)
- [📄 Contribute](#contribute)
- [📜 License](#license)

## ✨ Features
- 🔊 Live dictation locally with OpenAI Whisper
- ⌨️ Recording via hotkey (Alt+R)
- 🖥️ Tray icon (Windows & Linux)
- 📋 Automatic insertion of the recognized transcript
- ⚙️ Configurable model, language, silence detection, wake word

## 🛠️ Requirements

Hotkey Transcriber uses OpenAI Whisper for real-time speech recognition. Depending on hardware, one of two backends is used:

| Backend | Used when |
|---------|-----------|
| `faster-whisper` (CTranslate2) | NVIDIA GPU (CUDA) or CPU |
| `faster-whisper` (CTranslate2 with HIP) | AMD GPU on Linux (ROCm) |
| `whisper.cpp` (Vulkan) | AMD GPU on Windows — native path, no ROCm stack |
| `faster-whisper` via WSL2 (ROCm) | AMD GPU on Windows — WSL path, higher RAM usage |

A GPU is recommended for smooth, near-instant transcription. Without a GPU (CPU-only), transcription is also possible, but noticeably slower.

On first start, the selected Whisper model is downloaded once and cached locally. An internet connection is required for this initial download.

**Runtime backend override** — override the backend with the environment variable `HOTKEY_TRANSCRIBER_BACKEND`:

| Value | Meaning |
|-------|---------|
| `native` (default) | Run model directly in-process: faster-whisper (CPU/CUDA/ROCm on Linux), or whisper.cpp Vulkan on Windows with AMD GPU. |
| `wsl_amd` | Windows only. Delegate transcription to WSL2 with ROCm. Set automatically by the installer when choosing option [2], or manually via env var. Requires WSL setup via `setup_wsl_amd.ps1`. |

## ⚙️ Installation

### Linux

Standard install (CPU / NVIDIA):
```bash
bash ./tools/install_linux.sh --autostart=ask
```

With AMD GPU (ROCm) — see [Linux + AMD GPU (ROCm)](#linux--amd-gpu-rocm) for prerequisites:
```bash
bash ./tools/install_linux.sh --amd-gpu --autostart=ask
```

The `--amd-gpu` flag creates a venv (`.venv`) in the project directory, builds CTranslate2 from source with HIP/ROCm support, and installs `faster-whisper`. Requires ROCm runtime and build tools (`cmake`, `ninja`, `git`).

### Windows

```powershell
.\tools\install_windows.ps1 -Autostart ask
```

The installer asks which backend to set up:

```
[1] whisper.cpp + Vulkan  (GPU native, recommended for AMD/NVIDIA)
    Prerequisites: Vulkan SDK, git, cmake
[2] WSL ROCm              (AMD GPU via WSL; WSL setup is separate via setup_wsl_amd.ps1)
[3] CPU / Standard        (no GPU, faster-whisper on CPU)
```

The installer also creates a Start Menu shortcut (`Hotkey Transcriber`).

Autostart values: `ask`, `on`, `off`.

### Uninstall

Linux:
```bash
bash ./tools/uninstall_linux.sh
```

Windows (PowerShell):
```powershell
.\tools\uninstall_windows.ps1
```

---

### Linux + AMD GPU (ROCm)

For AMD GPUs on Linux (RDNA 3 / gfx1100 etc.), CTranslate2 is built from source with HIP support, giving native GPU acceleration with full model and quantization support.

**Prerequisites:**
- ROCm runtime installed (`rocminfo` and `hipconfig` must be available)
- Build tools: `sudo apt install -y build-essential git cmake ninja-build pkg-config libnuma-dev`

**Installation:**
```bash
bash ./tools/install_linux.sh --amd-gpu --autostart=ask
```

The installer:
- Detects GPU architecture automatically via `rocminfo`
- Creates a venv (`.venv`) in the project directory
- Clones and builds CTranslate2 with HIP from source (~15 min)
- Installs `faster-whisper` and the project
- Creates a launcher at `~/.local/bin/hotkey-transcriber` with the correct `LD_LIBRARY_PATH`

Start via:
```bash
~/.local/bin/hotkey-transcriber
```

Note: The CTranslate2 source directory (`~/CTranslate2`, ~556 MB) can be deleted after installation.

---

### Windows + AMD GPU (whisper.cpp + Vulkan, recommended)

Native Windows path using `whisper.cpp` with Vulkan. No ROCm or PyTorch stack needed.

**Prerequisites:**
1. AMD Software: Adrenalin Edition (includes Vulkan runtime) — reboot after install.
2. Vulkan SDK:
   ```powershell
   winget install --id KhronosGroup.VulkanSDK --exact --silent --accept-package-agreements --accept-source-agreements
   ```
3. git + CMake (with a C++ compiler, e.g. Visual Studio Build Tools)

**Installation:**
```powershell
.\tools\install_windows.ps1 -Autostart ask
```
Choose **[1] whisper.cpp + Vulkan**.

The installer:
- Creates/updates a venv (`.venv`) in the repo
- Clones/updates `whisper.cpp` and builds it with `GGML_VULKAN=ON`
- Sets `HOTKEY_TRANSCRIBER_WHISPER_CPP_CLI` as a user environment variable
- Creates a Start Menu shortcut

Start via Start Menu shortcut or directly:
```powershell
.\.venv\Scripts\hotkey-transcriber.exe
```

Notes:
- Distil models (`distil-small.en`, `distil-medium.en`, `distil-large-v3`) and CTranslate2-only models are not available with `whisper.cpp`.
- `cstr/whisper-large-v3-turbo-german-ggml` is whisper.cpp format — selectable in the tray model menu.
- On `faster-whisper` backends (Linux / WSL), use `TheChola/whisper-large-v3-turbo-german-faster-whisper` instead.

---

### Windows + AMD GPU (WSL ROCm, alternative)

Runs `faster-whisper`/CTranslate2 inside a WSL2 Linux VM with ROCm. Gives access to int8 quantization and distil models at the cost of higher RAM usage and more complex setup.

**Prerequisites:**
- AMD Software: Adrenalin Edition (includes WSL GPU support) — reboot after install.

**Setup (once):**
```powershell
.\tools\setup_wsl_amd.ps1
```

**Installation:**
```powershell
.\tools\install_windows.ps1 -Autostart ask
```
Choose **[2] WSL ROCm**.

This installs the app via pipx and sets `HOTKEY_TRANSCRIBER_BACKEND=wsl_amd` as a user environment variable. The app will use the WSL backend on every start.

Manual override (without reinstalling):
```powershell
$env:HOTKEY_TRANSCRIBER_BACKEND="wsl_amd"
hotkey-transcriber
```

---

### Manual installation (pipx)

> Note: pipx installation only supports NVIDIA GPU and CPU. For AMD GPUs use the installer scripts.

Linux:
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
# Restart shell
pipx install git+https://github.com/chefsichter/hotkey-transcriber
```

Windows (PowerShell):
```powershell
py -m pip install --user pipx
py -m pipx ensurepath
# Restart PowerShell
pipx install git+https://github.com/chefsichter/hotkey-transcriber
```

## 🔄 Update

**Standard install (pipx, CPU/NVIDIA):**
```powershell
git pull
.\tools\install_windows.ps1 -Autostart ask   # choose [3]
```
Linux:
```bash
git pull
bash ./tools/install_linux.sh --autostart=ask
```

**Vulkan backend (venv in repo):**
Fast code-only update (keeps existing whisper.cpp build):
```powershell
git pull
.\.venv\Scripts\python.exe -m pip install -e .
```
Full reinstall only needed if whisper.cpp/Vulkan toolchain changed or venv is broken:
```powershell
.\tools\install_windows.ps1 -Autostart ask   # choose [1]
```

**Manual pipx install from git:**
```powershell
pipx upgrade hotkey-transcriber
```

## 🪟 Start program
- After standard install: `hotkey-transcriber`
- After Vulkan install: `.\.venv\Scripts\hotkey-transcriber.exe` or via Start Menu shortcut
- The program starts as a tray application.

## 🎉 Usage
1. Press `Alt+R` to start recording. A red symbol indicates recording.
2. Release `R` to stop recording. The recognized text is pasted.
3. Use the tray menu to change model, language, hotkey, wake word, or autostart.
4. Model selection (tray → "Modell"):
   - whisper.cpp (Vulkan): `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `cstr/whisper-large-v3-turbo-german-ggml`
   - faster-whisper (CPU/NVIDIA/Linux): same base models + `distil-small.en`, `distil-medium.en`, `distil-large-v3`, `TheChola/whisper-large-v3-turbo-german-faster-whisper`
   - VRAM guidance: `tiny`/`base`: 2–4 GB; `small`/`medium`/`large*`: ≥6 GB

## ⚙️ Configuration
Settings are saved in `~/.config/hotkey-transcriber/config.json`. Model, language, hotkey, silence timeout, wake word and spoken-text actions are all stored there and persist across restarts.

## 🏗️ Architecture

PyQt5 tray app. Source under `src/hotkey_transcriber/`:

```
src/hotkey_transcriber/
├── main.py                         # Entry point: tray, menus, signal wiring
├── app_log_capture.py              # In-memory log ring-buffer (tray log window)
├── speech_recorder.py              # Audio capture loop + VAD + Whisper dispatch
├── resource_path_resolver.py       # Microphone icon path
├── autostart.py                    # OS autostart registration (Linux/Windows)
│
├── config/
│   └── config_manager.py           # load_config / save_config (JSON)
│
├── transcription/
│   ├── compute_device_detector.py  # CUDA / HIP / CPU detection
│   ├── whisper_backend_selector.py # Resolves backend from config + environment
│   ├── model_and_recorder_factory.py  # Instantiates model, recorder, keyboard listener
│   ├── whisper_cpp_backend.py      # whisper.cpp wrapper (Windows AMD/Vulkan)
│   └── wsl_whisper_bridge.py       # JSON-IPC bridge to faster-whisper in WSL2
│
├── keyboard/
│   ├── keyboard_listener.py        # Win32 / evdev hotkey detection
│   ├── keyboard_controller.py      # Text output (pyautogui / ydotool)
│   └── hotkey_change_dialog.py     # Qt5 hotkey-capture dialog
│
├── wake_word/
│   ├── wake_word_listener.py       # openwakeword background listener thread
│   └── wake_word_script_actions.py # Wake-word → script action mapping
│
├── actions/
│   ├── spoken_text_actions.py      # Spoken-text trigger matching + execution
│   └── action_settings_ui_rows.py  # Qt5 settings rows for script actions
│
└── builtin_scripts/                # Bundled helper scripts
```

See [docs/architecture.md](docs/architecture.md) for event-flow and backend-selection diagrams.

## 🧑‍💻 Developer setup

```bash
git clone https://github.com/chefsichter/hotkey-transcriber
cd hotkey-transcriber
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
pytest
```

> Dev extras include `pytest`, `pytest-cov`, `black`, `ruff`, `mypy`. All settings in `pyproject.toml`.

## 📄 Contribute
- Report bugs via Issues
- Pull requests welcome
- See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details

## 📜 License
This project is licensed under the [MIT License](LICENSE).
