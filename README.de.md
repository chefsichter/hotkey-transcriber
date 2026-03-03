🇬🇧 [English](./README.md) | 🇩🇪 [Deutsch](./README.de.md)

# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎙️ Live-Diktier-Tool mit Whisper

Mit Hotkey Transcriber kannst du per Tastenkombination (Alt+R) in Echtzeit transcribieren (Speech-To-Text). Der erkannte Text wird automatisch in das aktive Fenster eingefügt.

## 📑 Inhaltsverzeichnis
- [✨ Features](#features)
- [🛠️ Voraussetzungen](#voraussetzungen)
- [⚙️ Installation](#installation)
- [🪟 Programm starten](#programm-starten)
- [🎉 Nutzung](#nutzung)
- [⚙️ Konfiguration](#konfiguration)
- [💡 Tipps & Tricks](#tipps--tricks)
- [📄 Mitwirken](#mitwirken)
- [📜 Lizenz](#lizenz)

## ✨ Features
- 🔊 Live-Diktat lokal mit OpenAI Whisper (`faster-whisper` fuer NVIDIA/CPU, `openai-whisper` torch-Backend fuer AMD-GPUs unter Windows)
- ⌨️ Aufnahme per Hotkey (Alt+R)
- 🖥️ Traysymbol (Windows & Linux)
- 📋 Automatisches Einfügen des erkannten Transkripts
- ⚙️ Einstellbares Transkriptions-Intervall und Erkennungssprache

## 🛠️ Voraussetzungen

Hotkey Transcriber nutzt OpenAI Whisper fuer Echtzeit-Spracherkennung. Je nach Hardware wird eines von zwei Backends verwendet:

- **NVIDIA / CPU**: `faster-whisper` (CTranslate2) — schnell, unterstuetzt int8-Quantisierung
- **AMD-GPU unter Linux**: `faster-whisper` (CTranslate2 from Source mit HIP/ROCm gebaut) — native GPU-Beschleunigung fuer RDNA 3 (gfx1100/1101/1102) und andere unterstuetzte Architekturen
- **AMD-GPU unter Windows**: `openai-whisper` (torch) — CTranslate2s HIP-Kernel sind mit neueren AMD-GPUs (z.B. RDNA 4 / gfx1150) nicht kompatibel, daher wechselt die App automatisch auf das torch-Backend

Fuer eine fluessige, nahezu verzoegerungsfreie Transkription wird eine GPU empfohlen:
  - **NVIDIA**-GPUs mit CUDA-Treibern (>=11.7).
  - **AMD**-GPUs unter Linux via ROCm (CTranslate2 mit HIP-Support gebaut).
  - **AMD**-GPUs unter Windows via ROCm 7.2 + PyTorch (nativ, kein WSL noetig). Alternativ wird auch ein WSL-ROCm-Backend unterstuetzt.

Ohne GPU (CPU-only) ist Transkription ebenfalls moeglich, jedoch deutlich langsamer und mit einer Latenz von mehreren Sekunden pro Aufnahmeintervall.

Beim ersten Start wird das gewaehlte Whisper-Modell einmalig heruntergeladen und danach aus dem lokalen Cache genutzt. Fuer diesen initialen Download ist eine Internetverbindung erforderlich.

Backend-Erkennung: Die App erkennt die GPU und waehlt automatisch das beste Backend. Ueberschreibbar mit `HOTKEY_TRANSCRIBER_BACKEND` (`auto`, `native`, `wsl_amd`).

### Einfacher Installer (Linux & Windows)

Du kannst direkt die lokalen Installer-Skripte nutzen (inkl. Autostart-Auswahl):

- Linux:
  ```bash
  bash ./tools/install_linux.sh --autostart=ask
  ```
- Linux mit AMD-GPU (ROCm):
  ```bash
  bash ./tools/install_linux.sh --amd-gpu --autostart=ask
  ```
  Der `--amd-gpu`-Schalter erstellt eine venv (`.venv`) im Projektverzeichnis, baut CTranslate2 from Source mit HIP/ROCm-Support und installiert `faster-whisper`. Erfordert ROCm-Runtime und Build-Tools (`cmake`, `ninja`, `git`).
- Windows (PowerShell):
  ```powershell
  .\tools\install_windows.ps1 -Autostart ask
  ```
- Windows mit AMD-GPU (PowerShell):
  ```powershell
  .\tools\install_windows.ps1 -AmdGpu -Autostart ask
  ```
  Der `-AmdGpu`-Schalter erstellt eine Python-3.12-venv mit ROCm SDK, PyTorch ROCm und `openai-whisper` statt pipx.

Autostart-Werte: `ask`, `on`, `off`.
Unter Windows legt der Installer zusaetzlich einen Startmenue-Eintrag (`Hotkey Transcriber`) an.

Deinstallation:

- Linux:
  ```bash
  bash ./tools/uninstall_linux.sh
  ```
- Windows (PowerShell):
  ```powershell
  .\tools\uninstall_windows.ps1
  ```

### 🧰 Manuelle Installation (pipx / git)

#### pipx installieren

pipx ist notwendig, um die Anwendung isoliert zu installieren:

1. pipx:
- Auf Linux:
  ```bash
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  # Shell neu starten oder neu anmelden
  ```
  Oder via Paketmanager (Debian/Ubuntu):
  ```bash
  sudo apt update
  sudo apt install pipx
  ```

- Auf Windows (PowerShell):
  ```powershell
  py -m pip install --user pipx
  py -m pipx ensurepath
  # PowerShell neu starten
  ```
2. Direkte Installation aus dem Git-Repository:
   ```bash
   pipx install git+https://github.com/chefsichter/hotkey-transcriber
   ```

### Linux + AMD-GPU (ROCm)

Fuer AMD-GPUs unter Linux (RDNA 3 / gfx1100 etc.) wird CTranslate2 from Source mit HIP-Support gebaut.

**Voraussetzungen:**
- ROCm-Runtime installiert (`rocminfo` und `hipconfig` muessen verfuegbar sein)
- Build-Tools: `sudo apt install -y build-essential git cmake ninja-build pkg-config libnuma-dev`

**Installation:**
```bash
bash ./tools/install_linux.sh --amd-gpu --autostart=ask
```

Der Installer:
- Erkennt die GPU-Architektur automatisch via `rocminfo`
- Erstellt eine venv (`.venv`) im Projektverzeichnis
- Klont und baut CTranslate2 mit HIP from Source
- Installiert `faster-whisper` und das Projekt
- Verifiziert GPU-Zugriff
- Erstellt einen Launcher unter `~/.local/bin/hotkey-transcriber` mit korrektem `LD_LIBRARY_PATH`

Nach der Installation starten via:
```bash
~/.local/bin/hotkey-transcriber
```

Hinweise:
- Das CTranslate2-Quellverzeichnis (`~/CTranslate2`, ~556 MB) kann nach der Installation geloescht werden um Speicher zu sparen.
- Die App erkennt die AMD-GPU automatisch und nutzt das CTranslate2/faster-whisper-Backend mit `float16`.

### Windows 11 + AMD-GPU (natives ROCm)

Der empfohlene Weg fuer AMD-GPUs unter Windows. Die App nutzt `openai-whisper` mit PyTorch ROCm statt CTranslate2 (dessen HIP-Kernel auf neueren AMD-GPUs wie RDNA 4 abstuerzen).

1. AMD Software: Adrenalin Edition fuer Windows installieren (inkl. ROCm-Support), danach neu starten.
2. Installer mit `-AmdGpu` ausfuehren:
   ```powershell
   .\tools\install_windows.ps1 -AmdGpu -Autostart ask
   ```

Der Installer:
- Erstellt eine Python-3.12-venv (`.venv`) im Repo
- Installiert ROCm-SDK-Wheels + PyTorch-ROCm-Wheels (ROCm 7.2, cp312)
- Installiert `openai-whisper` und das Projekt
- Verifiziert GPU-Zugriff via `torch.cuda.is_available()`
- Erstellt eine Startmenue-Verknuepfung

Nach der Installation ueber die Startmenue-Verknuepfung oder direkt starten:

```powershell
& ".\.venv\Scripts\hotkey-transcriber.exe"
```

Hinweise:
- Python `3.12` ist fuer die AMD-ROCm-Wheels (`cp312`) erforderlich.
- Die App erkennt die AMD-GPU automatisch und nutzt das torch-Backend mit `float16` fuer optimale Performance.
- Distil-Modelle (`distil-small.en`, `distil-medium.en`, `distil-large-v3`) und eigene HuggingFace-Modelle sind mit dem torch-Backend nicht verfuegbar.
- Detaillierte Anleitung: [Windows AMD-GPU Setup (Deutsch)](./tools/WINDOWS_ROCM_NATIVE_MANUAL.de.md)

### Windows 11 + AMD (ROCm ueber WSL, Alternative)

Falls du `faster-whisper`/CTranslate2 ueber WSL bevorzugst (z.B. auf Hardware wo CTranslate2s HIP-Kernel funktionieren):

1. AMD Software: Adrenalin Edition fuer Windows installieren (inkl. WSL-Support), danach neu starten.
2. PowerShell als Administrator im Repo oeffnen und ausfuehren:
   ```powershell
   .\tools\setup_wsl_amd.ps1
   ```
3. Installation/Start:
   ```powershell
   .\tools\install_windows.ps1 -Autostart ask
   ```
   Die App erkennt WSL-ROCm-Bereitschaft automatisch und nutzt es wenn verfuegbar.

   Manuelles Override:
   ```powershell
   $env:HOTKEY_TRANSCRIBER_BACKEND="wsl_amd"
   hotkey-transcriber
   ```

## 🪟 Programm starten
- Nach der Installation genuegt:
  ```cmd
  hotkey-transcriber
  ```
- Fuer die AMD-GPU-venv-Installation die Exe direkt nutzen: `.\.venv\Scripts\hotkey-transcriber.exe`
- Das Programm startet als Tray-Anwendung.

## 🎉 Nutzung
1. Drücke `Alt+R`, um die Aufnahme zu starten. Ein rotes Symbol signalisiert die Aufnahme.
2. Lasse `R` los, um die Aufnahme zu stoppen. Der erkannte Text wird eingefügt und kopiert.
3. Über das Tray-Menü kannst du das Transkriptions-Intervall, die Erkennungssprache ändern oder das Programm beenden.
4. Modellwahl (Tray-Icon → „Modell wählen“):
    - Modelle: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`
    - Zusaetzliche CTranslate2-only Modelle (NVIDIA/CPU): `distil-small.en`, `distil-medium.en`, `distil-large-v3`, `TheChola/whisper-large-v3-turbo-german-faster-whisper`
    - Kleinere Modelle: reduzierter VRAM- & CPU-Bedarf → schnellere Transkription (leicht geringere Genauigkeit)
    - VRAM-Empfehlung: `tiny`/`base`: 2–4 GB; `small`/`medium`/`large*`: ≥6 GB

## ⚙️ Konfiguration
Standardwerte werden in einer JSON-Datei unter `~/.config/hotkey-transcriber/config.json` gespeichert. Einstellungen wie Modellgröße, Intervall und Erkennungssprache werden automatisch beibehalten.

## 💡 Tipps & Tricks
- Verwende kurze Intervalle (z.B. **0.5s**) für flüssiges Diktat.
- Wähle leichtere Modelle (`tiny` oder `base`) auf schwacher Hardware.

## 📄 Mitwirken
- Fehler melden via Issues
- Pull Requests willkommen
- Siehe [CONTRIBUTING.md](.github/CONTRIBUTING.md) für Details

## 📜 Lizenz
Dieses Projekt steht unter der [MIT License](LICENSE).
