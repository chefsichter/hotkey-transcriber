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
- [💡 Tips &amp; tricks](#tips--tricks)
- [📄 Contribute](#contribute)
- [📜 License](#license)

## ✨ Features
- 🔊 Live dictation locally with OpenAI Whisper (`faster-whisper` for NVIDIA/CPU, `openai-whisper` torch backend for AMD GPUs on Windows)
- ⌨️ Recording via hotkey (Alt+R)
- 🖥️ Tray icon (Windows &amp; Linux)
- 📋 Automatic insertion of the recognized transcript
- ⚙️ Adjustable transcription interval and recognition language

## 🛠️ Requirements

Hotkey Transcriber uses OpenAI Whisper for real-time speech recognition. Depending on hardware, one of two backends is used:

- **NVIDIA / CPU**: `faster-whisper` (CTranslate2) — fast, supports int8 quantization
- **AMD GPU on Linux**: `faster-whisper` (CTranslate2 built from source with HIP/ROCm) — native GPU acceleration for RDNA 3 (gfx1100/1101/1102) and other supported architectures
- **AMD GPU on Windows**: `openai-whisper` (torch) — CTranslate2's HIP kernels are incompatible with newer AMD GPUs (e.g. RDNA 4 / gfx1150), so the app automatically switches to the torch-based backend

A GPU is recommended for smooth, almost lag-free transcription:
  - **NVIDIA** GPUs with CUDA drivers (>=11.7).
  - **AMD** GPUs on Linux via ROCm (CTranslate2 built with HIP support).
  - **AMD** GPUs on Windows via ROCm 7.2 + PyTorch (native, no WSL needed). Alternatively, a WSL-ROCm backend is also supported.

Without a GPU (CPU-only), transcription is also possible, but significantly slower and with a latency of several seconds per recording interval.

On first start, the selected Whisper model is downloaded once and then reused from the local cache. An internet connection is required for this initial download.

**Backend auto-detection:** The app detects the GPU and selects the best backend automatically. You can override with the environment variable `HOTKEY_TRANSCRIBER_BACKEND`:

| Value | Meaning |
|-------|---------|
| `auto` (default) | Auto-detect: on **Windows** checks for an AMD GPU + working WSL-ROCm environment → uses `wsl_amd` if found; on **Linux** always selects `native`. Falls back to `native` in all other cases. |
| `native` | Run the model directly in the same process on the local system — uses CTranslate2/faster-whisper (CPU, CUDA, or ROCm/HIP) or the torch backend (AMD GPU on Windows). This is the only backend used on Linux. |
| `wsl_amd` | **Windows only.** Delegate transcription to a WSL2 Linux VM with ROCm. Workaround for AMD GPUs where CTranslate2's HIP kernels are incompatible (e.g. RDNA 4). Has no effect on Linux. |

### Simple installer (Linux & Windows)

You can use the local installer scripts directly (including autostart choice):

- Linux:
  ```bash
  bash ./tools/install_linux.sh --autostart=ask
  ```
- Linux with AMD GPU (ROCm) — details and prerequisites see [Linux + AMD GPU (ROCm)](#linux--amd-gpu-rocm):
  ```bash
  bash ./tools/install_linux.sh --amd-gpu --autostart=ask
  ```
  The `--amd-gpu` flag creates a venv (`.venv`) in the project directory, builds CTranslate2 from source with HIP/ROCm support, and installs `faster-whisper`. Requires ROCm runtime and build tools (`cmake`, `ninja`, `git`).
- Windows (PowerShell):
  ```powershell
  .\tools\install_windows.ps1 -Autostart ask
  ```
- Windows with AMD GPU (PowerShell) — two methods available, see [native ROCm (recommended)](#windows-11--amd-gpu-native-rocm) vs. [ROCm via WSL (alternative)](#windows-11--amd-rocm-via-wsl-alternative).
  ```powershell
  .\tools\install_windows.ps1 -AmdGpu -Autostart ask
  ```
  The `-AmdGpu` switch creates a Python 3.12 venv with ROCm SDK, PyTorch ROCm and `openai-whisper` instead of using pipx.

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

## 🔄 Update

How to update depends on how you installed it:

- **Windows/Linux via installer (without `-AmdGpu`, uses local repo pipx install):**
  ```powershell
  git pull
  .\tools\install_windows.ps1 -Autostart ask
  ```
  Linux:
  ```bash
  git pull
  bash ./tools/install_linux.sh --autostart=ask
  ```

- **Manual `pipx install git+https://...`:**
  ```powershell
  pipx upgrade hotkey-transcriber
  ```

- **AMD GPU with `-AmdGpu` (repo-local venv):**
  Fast code update (keeps existing ROCm/PyTorch stack):
  ```powershell
  git pull
  .\.venv\Scripts\python.exe -m pip install -e .
  ```
  Use full AMD installer only for base stack changes (ROCm/PyTorch/Python) or a broken venv:
  ```powershell
  .\tools\install_windows.ps1 -AmdGpu -Autostart ask
  ```

### 🧰 Manual installation (pipx / git)

> **Note:** The pipx installation only supports NVIDIA GPUs and CPU. For AMD GPUs use the installer scripts instead (`install_linux.sh --amd-gpu` or `install_windows.ps1 -AmdGpu`).

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

### AMD GPU setup

There are three AMD GPU paths depending on your OS. All three use the same app — only the backend and installation method differ.

| | Linux (ROCm) | Windows native (recommended) | Windows WSL (alternative) |
|---|---|---|---|
| **Backend** | `faster-whisper` (CTranslate2 with HIP) | `openai-whisper` (PyTorch ROCm) | `faster-whisper` (CTranslate2 in WSL2) |
| **When to use** | AMD GPU on Linux | AMD GPU on Windows (especially RDNA 4+) | AMD GPU on Windows where CTranslate2's HIP kernels work (e.g. RDNA 3) |
| **Pros** | Native GPU acceleration, int8 quantization, all models supported | Simple setup, no build step, broad GPU compatibility | CTranslate2 performance + int8 quantization on Windows |
| **Cons** | Requires building CTranslate2 from source (~15 min) | No distil models, no int8 quantization, Python 3.12 required | Requires WSL2 setup, higher RAM usage, more complex |
| **Installer** | `install_linux.sh --amd-gpu` | `install_windows.ps1 -AmdGpu` | `setup_wsl_amd.ps1` + `install_windows.ps1` |

---

### Linux + AMD GPU (ROCm)

For AMD GPUs on Linux (RDNA 3 / gfx1100 etc.), CTranslate2 is built from source with HIP support. This gives native GPU acceleration with full model and quantization support.

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
- Clones and builds CTranslate2 with HIP from source
- Installs `faster-whisper` and the project
- Verifies GPU access
- Creates a launcher at `~/.local/bin/hotkey-transcriber` with the correct `LD_LIBRARY_PATH`

After installation, start via:
```bash
~/.local/bin/hotkey-transcriber
```

Notes:
- The CTranslate2 source directory (`~/CTranslate2`, ~556 MB) can be deleted after installation to save space.
- The app auto-detects the AMD GPU and uses the CTranslate2/faster-whisper backend with `float16`.

---

### Windows 11 + AMD GPU (native ROCm)

**Recommended** for AMD GPUs on Windows. Uses `openai-whisper` with PyTorch ROCm — no CTranslate2 build required. This is the best option for newer AMD GPUs (RDNA 4 / gfx1150 and above) where CTranslate2's HIP kernels are incompatible.

1. Install AMD Software: Adrenalin Edition for Windows (includes ROCm support), then reboot.
2. Run the installer with `-AmdGpu`:
   ```powershell
   .\tools\install_windows.ps1 -AmdGpu -Autostart ask
   ```

The installer:
- Creates a Python 3.12 venv (`.venv`) in the repo
- Installs ROCm SDK wheels + PyTorch ROCm wheels (ROCm 7.2, cp312)
- Installs `openai-whisper` and the project
- Verifies GPU access via `torch.cuda.is_available()`
- Creates a Start Menu shortcut

After installation, start via the Start Menu shortcut or directly:

```powershell
.\.venv\Scripts\hotkey-transcriber.exe
```

Notes:
- Python `3.12` is required for AMD ROCm wheels (`cp312`).
- The app auto-detects the AMD GPU and uses the torch backend with `float16` for optimal performance.
- Distil models (`distil-small.en`, `distil-medium.en`, `distil-large-v3`) and custom HuggingFace models are not available with the torch backend.
- Detailed manual: [Windows AMD GPU setup (English)](./tools/WINDOWS_ROCM_NATIVE_MANUAL.md)

---

### Windows 11 + AMD (ROCm via WSL, alternative)

Alternative for AMD GPUs on Windows where CTranslate2's HIP kernels work (e.g. RDNA 3 / gfx1100). Runs `faster-whisper`/CTranslate2 inside a WSL2 Linux VM, giving access to int8 quantization and distil models — at the cost of higher RAM usage and a more complex setup. Both methods use the same Windows installer (`install_windows.ps1`); the difference is the additional WSL setup step.

1. Install AMD Software: Adrenalin Edition for Windows (includes WSL support), then reboot.
2. Open elevated PowerShell in this repo and run:
   ```powershell
   .\tools\setup_wsl_amd.ps1
   ```
3. Install/start:
   ```powershell
   .\tools\install_windows.ps1 -Autostart ask
   ```
   The app auto-detects WSL-ROCm readiness and uses it when available.

   Manual override:
   ```powershell
   $env:HOTKEY_TRANSCRIBER_BACKEND="wsl_amd"
   hotkey-transcriber
   ```

## 🪟 Start program
- After installation, run:
  ```cmd
  hotkey-transcriber
  ```
- For the AMD GPU venv install, use the exe directly: `.\.venv\Scripts\hotkey-transcriber.exe`
- The program starts as a tray application.

## 🎉 Usage
1. Press `Alt+R` to start recording. A red symbol indicates recording.
2. Release `R` to stop the recording. The recognized text is pasted and copied.
3. You can use the tray menu to change the transcription interval, recognition language, and autostart, or exit the program.
4. Model selection (tray icon → "Select model"):
    - Models: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`
    - Additional CTranslate2-only models (NVIDIA/CPU): `distil-small.en`, `distil-medium.en`, `distil-large-v3`, `TheChola/whisper-large-v3-turbo-german-faster-whisper`
    - Smaller models: reduced VRAM &amp; CPU requirements → faster transcription (slightly lower accuracy)
    - VRAM recommendation: `tiny`/`base`: 2-4 GB; `small`/`medium`/`large*`: ≥6 GB

## ⚙️ Configuration
Default values are saved in a JSON file under `~/.config/hotkey-transcriber/config.json`. Settings such as model size, interval and detection language are automatically retained.

## 🏗️ Architecture

The application is a PyQt5 system-tray app. Source lives under `src/hotkey_transcriber/` and is organized into focused subpackages:

```
src/hotkey_transcriber/
├── main.py                         # Entry point: tray icon, menus, signal wiring
├── app_log_capture.py              # In-memory log ring-buffer (tray log window)
├── speech_recorder.py              # Audio capture loop + VAD + Whisper dispatch
├── resource_path_resolver.py       # Microphone icon path (package or filesystem)
├── autostart.py                    # OS autostart registration (Linux/Windows)
│
├── config/
│   └── config_manager.py           # load_config / save_config (JSON)
│
├── transcription/
│   ├── compute_device_detector.py  # CUDA / HIP / CPU detection via CTranslate2
│   ├── whisper_backend_selector.py # Resolves backend from config + environment
│   ├── model_and_recorder_factory.py  # Instantiates model, recorder, keyboard listener
│   ├── torch_whisper_fallback_backend.py  # openai-whisper wrapper (AMD/Windows)
│   └── wsl_whisper_bridge.py       # JSON-IPC bridge to faster-whisper in WSL2
│
├── keyboard/
│   ├── keyboard_listener.py        # Win32 / evdev hotkey detection
│   ├── keyboard_controller.py      # Text output (pyautogui / ydotool)
│   └── hotkey_change_dialog.py     # Qt5 hotkey-capture dialog
│
├── wake_word/
│   ├── wake_word_listener.py       # openwakeword background listener thread
│   └── wake_word_script_actions.py # Wake-word → shell-script action mapping
│
├── actions/
│   ├── spoken_text_actions.py      # Spoken-text trigger matching + execution
│   └── action_settings_ui_rows.py  # Qt5 settings rows for script actions
│
└── builtin_scripts/                # Bundled shell/Python helper scripts
```

See [docs/architecture.md](docs/architecture.md) for the full event-flow and backend-selection diagrams.

## 🧑‍💻 Developer setup

```bash
# 1. Clone and create a venv
git clone https://github.com/chefsichter/hotkey-transcriber
cd hotkey-transcriber
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install with dev extras
pip install -e ".[dev]"

# 3. Install pre-commit hooks
pre-commit install

# 4. Run the test suite
pytest

# 5. Format, lint, type-check
black src tests
ruff check src tests
mypy src
```

> The `dev` extras include `pytest`, `pytest-cov`, `black`, `ruff`, and `mypy`.
> All tool settings are in `pyproject.toml`.

## 📄 Contribute
- Report bugs via Issues
- Pull requests welcome
- See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details

## 📜 License
This project is licensed under the [MIT License](LICENSE).
