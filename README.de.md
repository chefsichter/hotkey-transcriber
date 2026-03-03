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
- 🔊 Live-Diktat lokal mit OpenAI Whisper (via `faster-whisper`)
- ⌨️ Aufnahme per Hotkey (Alt+R)
- 🖥️ Traysymbol (Windows & Linux)
- 📋 Automatisches Einfügen des erkannten Transkripts
- ⚙️ Einstellbares Transkriptions-Intervall und Erkennungssprache

## 🛠️ Voraussetzungen

Hotkey Transcriber nutzt im Hintergrund `faster-whisper`, eine optimierte Whisper-Implementierung für Echtzeit-Spracherkennung.

Für eine flüssige, nahezu verzögerungsfreie Transkription wird eine GPU empfohlen:
  - NVIDIA GPUs mit CUDA-Treibern (>=11.7).
  - AMD-GPUs per ROCm sind in diesem Stack (`faster-whisper`/CTranslate2) derzeit vor allem ein Linux-Pfad, kein natives Windows-Setup.

Ohne GPU (CPU-only) ist Transkription ebenfalls möglich, jedoch deutlich langsamer und mit einer Latenz von mehreren Sekunden pro Aufnahmeintervall.

Beim ersten Start wird das gewählte Whisper-Modell einmalig von Hugging Face heruntergeladen und danach aus dem lokalen Cache genutzt. Für diesen initialen Download ist eine Internetverbindung erforderlich.

Auf Windows 11 wird bei erkannter AMD-GPU automatisch ein WSL-Backend vorbereitet und verwendet. Das Verhalten lässt sich über `HOTKEY_TRANSCRIBER_BACKEND` steuern (`auto`, `native`, `wsl_amd`).

### Einfacher Installer (Linux & Windows)

Du kannst direkt die lokalen Installer-Skripte nutzen (inkl. Autostart-Auswahl):

- Linux:
  ```bash
  bash ./tools/install_linux.sh --autostart=ask
  ```
- Windows (PowerShell):
  ```powershell
  .\tools\install_windows.ps1 -Autostart ask
  ```

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

### Windows 11 + AMD (ROCm über WSL)

1. AMD Software: Adrenalin Edition für Windows installieren (inkl. WSL-Support), danach neu starten.
2. PowerShell als Administrator im Repo öffnen und ausführen:
   ```powershell
   .\tools\setup_wsl_amd.ps1
   ```
3. Installation/Start (empfohlen):
   ```powershell
   .\tools\install_windows.ps1 -Autostart ask
   ```
   Der Installer setzt `HOTKEY_TRANSCRIBER_BACKEND=auto` und richtet den tray-only Start ein.

   Alternativ manuell:
   ```powershell
   $env:HOTKEY_TRANSCRIBER_BACKEND="auto"
   hotkey-transcriber
   ```

### Windows 11 + AMD natives ROCm (experimentell)

Du kannst `ctranslate2` mit HIP fuer native Windows-Nutzung neu bauen. Das Skript kann dabei die ROCm-Windows-Python-Pakete gemaess offizieller AMD-Anleitung automatisch installieren:

```powershell
.\tools\build_ctranslate2_rocm_windows.ps1 `
  -RocmVenv ".\.venv" `
  -RocmMergedRoot "C:\rdev\_rocm_sdk_devel" `
  -HipArch "gfx1150"
```

Hinweise:
- Python `3.12` ist fuer die AMD-ROCm-Wheels (`cp312`) erforderlich.
- `-InstallAmdRocmFromGuide` ist standardmaessig `true`.
- Wenn `-RocmVenv` fehlt, prueft das Skript im aktuellen Verzeichnis zuerst `.\.venv`, dann `.\venv`; falls beides fehlt, wird `.\.venv` erstellt.
- Verwendete offizielle AMD-Windows-Anleitung: https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html
- Wenn deine ROCm-venv bereits komplett vorbereitet ist, kannst du die Paket-Installation ueberspringen:
  ```powershell
  .\tools\build_ctranslate2_rocm_windows.ps1 -InstallAmdRocmFromGuide:$false
  ```

Detaillierte Schritt-fuer-Schritt-Anleitungen:
- [Windows ROCm + CTranslate2 Anleitung (Deutsch)](./tools/WINDOWS_ROCM_NATIVE_MANUAL.de.md)
- [Windows ROCm + CTranslate2 manual (English)](./tools/WINDOWS_ROCM_NATIVE_MANUAL.md)

Danach die App mit nativen Backend starten:

```powershell
$env:HOTKEY_TRANSCRIBER_BACKEND="native"
$env:HOTKEY_TRANSCRIBER_ROCM_ROOT="$((Resolve-Path .\build\rocm-win-ct2\_rocm_sdk_devel).Path)"
& ".\.venv\Scripts\hotkey-transcriber.exe"
```

Wichtig:
- Starte die Exe aus genau derselben ROCm-venv, in der gebaut wurde.
- `hotkey-transcriber` ohne Pfad kann sonst die globale/pipx-Installation starten.
- Schnelltest:
  ```powershell
  Get-Command hotkey-transcriber
  ```

## 🪟 Programm starten
- Nach Aktivierung der virtuellen Umgebung genügt der Befehl:
  ```cmd
  hotkey-transcriber
  ```
- Fuer den nativen Windows-ROCm-Fall nutze die Exe direkt aus `.\.venv\Scripts\`.
- Das Programm startet als Tray-Anwendung.

## 🎉 Nutzung
1. Drücke `Alt+R`, um die Aufnahme zu starten. Ein rotes Symbol signalisiert die Aufnahme.
2. Lasse `R` los, um die Aufnahme zu stoppen. Der erkannte Text wird eingefügt und kopiert.
3. Über das Tray-Menü kannst du das Transkriptions-Intervall, die Erkennungssprache ändern oder das Programm beenden.
4. Modellwahl (Tray-Icon → „Modell wählen“):
    - Modelle: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `TheChola/whisper-large-v3-turbo-german-faster-whisper`
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
