🇬🇧 [English](./README.md) | 🇩🇪 [Deutsch](./README.de.md)

# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎙️ Live-Diktier-Tool mit Whisper

Mit Hotkey Transcriber kannst du per Tastenkombination (Alt+R) in Echtzeit transkribieren (Speech-To-Text). Der erkannte Text wird automatisch in das aktive Fenster eingefügt.

## 📑 Inhaltsverzeichnis
- [✨ Features](#features)
- [🛠️ Voraussetzungen](#voraussetzungen)
- [⚙️ Installation](#installation)
- [🔄 Update](#update)
- [🪟 Programm starten](#programm-starten)
- [🎉 Nutzung](#nutzung)
- [⚙️ Konfiguration](#konfiguration)
- [🏗️ Architektur](#architektur)
- [🧑‍💻 Entwickler-Setup](#entwickler-setup)
- [📄 Mitwirken](#mitwirken)
- [📜 Lizenz](#lizenz)

## ✨ Features
- 🔊 Live-Diktat lokal mit OpenAI Whisper
- ⌨️ Aufnahme per Hotkey (Alt+R)
- 🖥️ Traysymbol (Windows & Linux)
- 📋 Automatisches Einfügen des erkannten Transkripts
- ⚙️ Einstellbares Modell, Sprache, Stille-Erkennung, Wake Word

## 🛠️ Voraussetzungen

Hotkey Transcriber nutzt OpenAI Whisper für Echtzeit-Spracherkennung. Je nach Hardware wird eines der folgenden Backends verwendet:

| Backend | Wann |
|---------|------|
| `faster-whisper` (CTranslate2) | NVIDIA-GPU (CUDA) oder CPU |
| `faster-whisper` (CTranslate2 mit HIP) | AMD-GPU unter Linux (ROCm) |
| `whisper.cpp` (Vulkan) | AMD-GPU unter Windows — nativer Pfad, kein ROCm-Stack |
| `faster-whisper` via WSL2 (ROCm) | AMD-GPU unter Windows — WSL-Pfad, höherer RAM-Verbrauch |

Eine GPU wird für flüssige, nahezu verzögerungsfreie Transkription empfohlen. Ohne GPU (CPU-only) ist Transkription möglich, aber deutlich langsamer.

Beim ersten Start wird das gewählte Whisper-Modell einmalig heruntergeladen und lokal gecacht. Für diesen Download ist eine Internetverbindung erforderlich.

**Laufzeit-Backend-Override** — Backend per Umgebungsvariable `HOTKEY_TRANSCRIBER_BACKEND` überschreiben:

| Wert | Bedeutung |
|------|-----------|
| `native` (Standard) | Modell direkt im Prozess: faster-whisper (CPU/CUDA/ROCm unter Linux), oder whisper.cpp Vulkan unter Windows mit AMD-GPU. |
| `wsl_amd` | Nur Windows. Transkription wird an WSL2 mit ROCm delegiert. Wird vom Installer bei Wahl von Option [2] automatisch gesetzt, oder manuell per Env-Variable. Erfordert WSL-Setup via `setup_wsl_amd.ps1`. |

## ⚙️ Installation

### Linux

Standard (CPU / NVIDIA):
```bash
bash ./tools/install_linux.sh --autostart=ask
```

Mit AMD-GPU (ROCm) — Voraussetzungen siehe [Linux + AMD-GPU (ROCm)](#linux--amd-gpu-rocm):
```bash
bash ./tools/install_linux.sh --amd-gpu --autostart=ask
```

Der `--amd-gpu`-Schalter erstellt eine venv (`.venv`) im Projektverzeichnis, baut CTranslate2 from Source mit HIP/ROCm-Support und installiert `faster-whisper`. Erfordert ROCm-Runtime und Build-Tools (`cmake`, `ninja`, `git`).

### Windows

```powershell
.\tools\install_windows.ps1 -Autostart ask
```

Der Installer fragt, welches Backend eingerichtet werden soll:

```
[1] whisper.cpp + Vulkan  (GPU nativ, empfohlen für AMD/NVIDIA)
    Voraussetzung: Vulkan SDK, git, cmake
[2] WSL ROCm              (AMD-GPU via WSL; WSL-Setup separat via setup_wsl_amd.ps1)
[3] CPU / Standard        (kein GPU, faster-whisper auf CPU)
```

Der Installer erstellt außerdem einen Startmenü-Eintrag (`Hotkey Transcriber`).

Autostart-Werte: `ask`, `on`, `off`.

### Deinstallation

Linux:
```bash
bash ./tools/uninstall_linux.sh
```

Windows (PowerShell):
```powershell
.\tools\uninstall_windows.ps1
```

---

### Linux + AMD-GPU (ROCm)

Für AMD-GPUs unter Linux (RDNA 3 / gfx1100 etc.) wird CTranslate2 from Source mit HIP-Support gebaut. Das ergibt native GPU-Beschleunigung mit voller Modell- und Quantisierungs-Unterstützung.

**Voraussetzungen:**
- ROCm-Runtime installiert (`rocminfo` und `hipconfig` müssen verfügbar sein)
- Build-Tools: `sudo apt install -y build-essential git cmake ninja-build pkg-config libnuma-dev`

**Installation:**
```bash
bash ./tools/install_linux.sh --amd-gpu --autostart=ask
```

Der Installer:
- Erkennt die GPU-Architektur automatisch via `rocminfo`
- Erstellt eine venv (`.venv`) im Projektverzeichnis
- Klont und baut CTranslate2 mit HIP from Source (~15 Min.)
- Installiert `faster-whisper` und das Projekt
- Erstellt einen Launcher unter `~/.local/bin/hotkey-transcriber` mit korrektem `LD_LIBRARY_PATH`

Starten via:
```bash
~/.local/bin/hotkey-transcriber
```

Hinweis: Das CTranslate2-Quellverzeichnis (`~/CTranslate2`, ~556 MB) kann nach der Installation gelöscht werden.

---

### Windows + AMD-GPU (whisper.cpp + Vulkan, empfohlen)

Nativer Windows-Pfad mit `whisper.cpp` und Vulkan. Kein ROCm- oder PyTorch-Stack nötig.

**Voraussetzungen:**
1. AMD Software: Adrenalin Edition (enthält Vulkan-Runtime) — danach neu starten.
2. Vulkan SDK:
   ```powershell
   winget install --id KhronosGroup.VulkanSDK --exact --silent --accept-package-agreements --accept-source-agreements
   ```
3. git + CMake (mit C++-Compiler, z.B. Visual Studio Build Tools)

**Installation:**
```powershell
.\tools\install_windows.ps1 -Autostart ask
```
Option **[1] whisper.cpp + Vulkan** wählen.

Der Installer:
- Erstellt/aktualisiert eine venv (`.venv`) im Repo
- Klont/aktualisiert `whisper.cpp` und baut es mit `GGML_VULKAN=ON`
- Setzt `HOTKEY_TRANSCRIBER_WHISPER_CPP_CLI` als Benutzer-Umgebungsvariable
- Erstellt eine Startmenü-Verknüpfung

Starten über Startmenü-Verknüpfung oder direkt:
```powershell
.\.venv\Scripts\hotkey-transcriber.exe
```

Hinweise:
- Distil-Modelle (`distil-small.en`, `distil-medium.en`, `distil-large-v3`) und CTranslate2-only Modelle sind mit `whisper.cpp` nicht verfügbar.
- `cstr/whisper-large-v3-turbo-german-ggml` ist whisper.cpp-Format — im Tray-Modellmenü wählbar.
- Bei `faster-whisper`-Backends (Linux / WSL) stattdessen `TheChola/whisper-large-v3-turbo-german-faster-whisper` verwenden.

---

### Windows + AMD-GPU (WSL ROCm, Alternative)

Führt `faster-whisper`/CTranslate2 in einer WSL2-Linux-VM mit ROCm aus. Ermöglicht int8-Quantisierung und Distil-Modelle, auf Kosten von höherem RAM-Verbrauch und komplexerem Setup.

**Voraussetzungen:**
- AMD Software: Adrenalin Edition (enthält WSL-GPU-Support) — danach neu starten.

**WSL-Setup (einmalig):**
```powershell
.\tools\setup_wsl_amd.ps1
```

**Installation:**
```powershell
.\tools\install_windows.ps1 -Autostart ask
```
Option **[2] WSL ROCm** wählen.

Installiert die App via pipx und setzt `HOTKEY_TRANSCRIBER_BACKEND=wsl_amd` als Benutzer-Umgebungsvariable. Die App nutzt bei jedem Start das WSL-Backend.

Manuelles Override (ohne Neuinstallation):
```powershell
$env:HOTKEY_TRANSCRIBER_BACKEND="wsl_amd"
hotkey-transcriber
```

---

### Manuelle Installation (pipx)

> Hinweis: Die pipx-Installation unterstützt nur NVIDIA-GPU und CPU. Für AMD-GPUs die Installer-Skripte verwenden.

Linux:
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
# Shell neu starten
pipx install git+https://github.com/chefsichter/hotkey-transcriber
```

Windows (PowerShell):
```powershell
py -m pip install --user pipx
py -m pipx ensurepath
# PowerShell neu starten
pipx install git+https://github.com/chefsichter/hotkey-transcriber
```

## 🔄 Update

**Standard-Install (pipx, CPU/NVIDIA):**
```powershell
git pull
.\tools\install_windows.ps1 -Autostart ask   # Option [3]
```
Linux:
```bash
git pull
bash ./tools/install_linux.sh --autostart=ask
```

**Vulkan-Backend (venv im Repo):**
Schnelles Code-Update (behält whisper.cpp-Build):
```powershell
git pull
.\.venv\Scripts\python.exe -m pip install -e .
```
Vollständige Neuinstallation nur bei Änderungen an whisper.cpp/Vulkan-Toolchain oder defekter venv:
```powershell
.\tools\install_windows.ps1 -Autostart ask   # Option [1]
```

**Manuell via pipx:**
```powershell
pipx upgrade hotkey-transcriber
```

## 🪟 Programm starten
- Nach Standard-Install: `hotkey-transcriber`
- Nach Vulkan-Install: `.\.venv\Scripts\hotkey-transcriber.exe` oder über Startmenü-Verknüpfung
- Das Programm startet als Tray-Anwendung.

## 🎉 Nutzung
1. `Alt+R` drücken, um die Aufnahme zu starten. Ein rotes Symbol zeigt die Aufnahme an.
2. `R` loslassen, um die Aufnahme zu stoppen. Der erkannte Text wird eingefügt.
3. Über das Tray-Menü Modell, Sprache, Hotkey, Wake Word und Autostart anpassen.
4. Modellwahl (Tray → „Modell"):
   - whisper.cpp (Vulkan): `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `cstr/whisper-large-v3-turbo-german-ggml`
   - faster-whisper (CPU/NVIDIA/Linux): gleiche Basismodelle + `distil-small.en`, `distil-medium.en`, `distil-large-v3`, `TheChola/whisper-large-v3-turbo-german-faster-whisper`
   - VRAM-Empfehlung: `tiny`/`base`: 2–4 GB; `small`/`medium`/`large*`: ≥6 GB

## ⚙️ Konfiguration
Einstellungen werden in `~/.config/hotkey-transcriber/config.json` gespeichert. Modell, Sprache, Hotkey, Stille-Timeout, Wake Word und Sprachaktionen werden dort gespeichert und bleiben über Neustarts erhalten.

## 🏗️ Architektur

PyQt5-Tray-App. Quellcode unter `src/hotkey_transcriber/`:

```
src/hotkey_transcriber/
├── main.py                         # Einstiegspunkt: Tray-Icon, Menüs, Signal-Verkabelung
├── app_log_capture.py              # In-Memory-Log-Ringpuffer (Tray-Log-Fenster)
├── speech_recorder.py              # Audio-Aufnahme-Schleife + VAD + Whisper-Dispatch
├── resource_path_resolver.py       # Mikrofon-Icon-Pfad
├── autostart.py                    # OS-Autostart-Registrierung (Linux/Windows)
│
├── config/
│   └── config_manager.py           # load_config / save_config (JSON)
│
├── transcription/
│   ├── compute_device_detector.py  # CUDA / HIP / CPU-Erkennung
│   ├── whisper_backend_selector.py # Backend-Auswahl aus Config + Umgebung
│   ├── model_and_recorder_factory.py  # Instanziert Modell, Recorder, Keyboard-Listener
│   ├── whisper_cpp_backend.py      # whisper.cpp-Wrapper (Windows AMD/Vulkan)
│   └── wsl_whisper_bridge.py       # JSON-IPC-Bridge zu faster-whisper in WSL2
│
├── keyboard/
│   ├── keyboard_listener.py        # Win32- / evdev-Hotkey-Erkennung
│   ├── keyboard_controller.py      # Textausgabe (pyautogui / ydotool)
│   └── hotkey_change_dialog.py     # Qt5-Hotkey-Erfassungsdialog
│
├── wake_word/
│   ├── wake_word_listener.py       # openwakeword-Hintergrund-Listener-Thread
│   └── wake_word_script_actions.py # Wake-Word → Skript-Aktionszuordnung
│
├── actions/
│   ├── spoken_text_actions.py      # Gesprochener-Text-Trigger + Ausführung
│   └── action_settings_ui_rows.py  # Qt5-Einstellungszeilen für Skript-Aktionen
│
└── builtin_scripts/                # Mitgelieferte Hilfsskripte
```

Vollständige Event-Flow- und Backend-Auswahldiagramme: [docs/architecture.md](docs/architecture.md)

## 🧑‍💻 Entwickler-Setup

```bash
git clone https://github.com/chefsichter/hotkey-transcriber
cd hotkey-transcriber
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
pytest
```

> Dev-Extras: `pytest`, `pytest-cov`, `black`, `ruff`, `mypy`. Alle Einstellungen in `pyproject.toml`.

## 📄 Mitwirken
- Fehler melden via Issues
- Pull Requests willkommen
- Siehe [CONTRIBUTING.md](.github/CONTRIBUTING.md) für Details

## 📜 Lizenz
Dieses Projekt steht unter der [MIT License](LICENSE).
