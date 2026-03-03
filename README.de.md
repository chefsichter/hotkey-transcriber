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

**Backend-Erkennung:** Die App erkennt die GPU und waehlt automatisch das beste Backend. Ueberschreibbar mit der Umgebungsvariable `HOTKEY_TRANSCRIBER_BACKEND`:

| Wert | Bedeutung |
|------|-----------|
| `auto` (Standard) | Automatische Erkennung: unter **Windows** wird geprueft ob eine AMD-GPU und eine funktionierende WSL-ROCm-Umgebung vorhanden sind → nutzt `wsl_amd` falls ja; unter **Linux** wird immer `native` gewaehlt. In allen anderen Faellen Fallback auf `native`. |
| `native` | Modell laeuft direkt im gleichen Prozess auf dem lokalen System — nutzt CTranslate2/faster-whisper (CPU, CUDA oder ROCm/HIP) bzw. das torch-Backend (AMD-GPU unter Windows). Dies ist das einzige Backend unter Linux. |
| `wsl_amd` | **Nur Windows.** Transkription wird an eine WSL2-Linux-VM mit ROCm delegiert. Workaround fuer AMD-GPUs, bei denen CTranslate2s HIP-Kernel nicht kompatibel sind (z.B. RDNA 4). Hat unter Linux keine Wirkung. |

### Einfacher Installer (Linux & Windows)

Du kannst direkt die lokalen Installer-Skripte nutzen (inkl. Autostart-Auswahl):

- Linux:
  ```bash
  bash ./tools/install_linux.sh --autostart=ask
  ```
- Linux mit AMD-GPU (ROCm) — Details und Voraussetzungen siehe [Linux + AMD-GPU (ROCm)](#linux--amd-gpu-rocm):
  ```bash
  bash ./tools/install_linux.sh --amd-gpu --autostart=ask
  ```
  Der `--amd-gpu`-Schalter erstellt eine venv (`.venv`) im Projektverzeichnis, baut CTranslate2 from Source mit HIP/ROCm-Support und installiert `faster-whisper`. Erfordert ROCm-Runtime und Build-Tools (`cmake`, `ninja`, `git`).
- Windows (PowerShell):
  ```powershell
  .\tools\install_windows.ps1 -Autostart ask
  ```
- Windows mit AMD-GPU (PowerShell) — zwei Methoden verfuegbar, siehe [natives ROCm (empfohlen)](#windows-11--amd-gpu-natives-rocm) vs. [ROCm ueber WSL (Alternative)](#windows-11--amd-rocm-ueber-wsl-alternative).
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

> **Hinweis:** Die pipx-Installation unterstuetzt nur NVIDIA-GPUs und CPU. Fuer AMD-GPUs nutze stattdessen die Installer-Skripte (`install_linux.sh --amd-gpu` bzw. `install_windows.ps1 -AmdGpu`).

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

### AMD-GPU Setup

Es gibt drei AMD-GPU-Wege je nach Betriebssystem. Alle drei nutzen dieselbe App — nur Backend und Installationsmethode unterscheiden sich.

| | Linux (ROCm) | Windows nativ (empfohlen) | Windows WSL (Alternative) |
|---|---|---|---|
| **Backend** | `faster-whisper` (CTranslate2 mit HIP) | `openai-whisper` (PyTorch ROCm) | `faster-whisper` (CTranslate2 in WSL2) |
| **Wann nutzen** | AMD-GPU unter Linux | AMD-GPU unter Windows (besonders RDNA 4+) | AMD-GPU unter Windows, wenn CTranslate2s HIP-Kernel funktionieren (z.B. RDNA 3) |
| **Vorteile** | Native GPU-Beschleunigung, int8-Quantisierung, alle Modelle verfuegbar | Einfaches Setup, kein Build-Schritt, breite GPU-Kompatibilitaet | CTranslate2-Performance + int8-Quantisierung unter Windows |
| **Nachteile** | CTranslate2 muss from Source gebaut werden (~15 Min.) | Keine Distil-Modelle, keine int8-Quantisierung, Python 3.12 erforderlich | WSL2-Setup noetig, hoeherer RAM-Verbrauch, komplexer |
| **Installer** | `install_linux.sh --amd-gpu` | `install_windows.ps1 -AmdGpu` | `setup_wsl_amd.ps1` + `install_windows.ps1` |

---

### Linux + AMD-GPU (ROCm)

Fuer AMD-GPUs unter Linux (RDNA 3 / gfx1100 etc.) wird CTranslate2 from Source mit HIP-Support gebaut. Das ergibt native GPU-Beschleunigung mit voller Modell- und Quantisierungs-Unterstuetzung.

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

---

### Windows 11 + AMD-GPU (natives ROCm)

**Empfohlen** fuer AMD-GPUs unter Windows. Nutzt `openai-whisper` mit PyTorch ROCm — kein CTranslate2-Build noetig. Beste Option fuer neuere AMD-GPUs (RDNA 4 / gfx1150 und neuer), bei denen CTranslate2s HIP-Kernel nicht kompatibel sind.

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
.\.venv\Scripts\hotkey-transcriber.exe
```

Hinweise:
- Python `3.12` ist fuer die AMD-ROCm-Wheels (`cp312`) erforderlich.
- Die App erkennt die AMD-GPU automatisch und nutzt das torch-Backend mit `float16` fuer optimale Performance.
- Distil-Modelle (`distil-small.en`, `distil-medium.en`, `distil-large-v3`) und eigene HuggingFace-Modelle sind mit dem torch-Backend nicht verfuegbar.
- Detaillierte Anleitung: [Windows AMD-GPU Setup (Deutsch)](./tools/WINDOWS_ROCM_NATIVE_MANUAL.de.md)

---

### Windows 11 + AMD (ROCm ueber WSL, Alternative)

Alternative fuer AMD-GPUs unter Windows, bei denen CTranslate2s HIP-Kernel funktionieren (z.B. RDNA 3 / gfx1100). Fuehrt `faster-whisper`/CTranslate2 in einer WSL2-Linux-VM aus — mit Zugang zu int8-Quantisierung und Distil-Modellen, auf Kosten von hoeherem RAM-Verbrauch und komplexerem Setup. Beide Windows-Methoden nutzen denselben Installer (`install_windows.ps1`); der Unterschied ist der zusaetzliche WSL-Setup-Schritt.

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
