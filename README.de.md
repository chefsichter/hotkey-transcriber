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
  - NVIDIA GPUs mit CUDA-Treibern (>=11.7) oder
  - AMD GPUs mit aktivierter ROCm-Unterstützung.

Ohne GPU (CPU-only) ist Transkription ebenfalls möglich, jedoch deutlich langsamer und mit einer Latenz von mehreren Sekunden pro Aufnahmeintervall.

## ⚙️ Installation
  
### 🎉 Einfache Installation

Gehe zur GitHub Releases Seite: https://github.com/chefsichter/hotkey-transcriber/releases und lade das Paket für dein System herunter.

- Linux (AppImage):

  ```bash
  chmod +x hotkey-transcriber-*.AppImage
  ./hotkey-transcriber-*.AppImage
  ```

- Windows (EXE):

  Lade die Datei `hotkey-transcriber-*.exe` herunter und führe sie per Doppelklick aus.

### 🧰 Manuelle Installation

#### pipx installieren

pipx ist notwendig, um die Anwendung isoliert zu installieren:

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
1. Direkte Installation aus dem Git-Repository (einfach):
   ```bash
   pipx install git+https://github.com/chefsichter/hotkey-transcriber
   ```

   oder

2. Manuelle Installation aus dem lokalen Klon:
   ```bash
   git clone https://github.com/chefsichter/hotkey-transcriber.git
   cd hotkey-transcriber
   pipx install .
   ```

## 🪟 Programm starten
- Nach Aktivierung der virtuellen Umgebung genügt der Befehl:
  ```cmd
  hotkey-transcriber
  ```
- Das Programm startet als Tray-Anwendung.

## 🎉 Nutzung
1. Drücke `Alt+R`, um die Aufnahme zu starten. Ein rotes Symbol signalisiert die Aufnahme.
2. Lasse `R` los, um die Aufnahme zu stoppen. Der erkannte Text wird eingefügt und kopiert.
3. Über das Tray-Menü kannst du das Transkriptions-Intervall, die Erkennungssprache ändern oder das Programm beenden.
4. Modellwahl (Tray-Icon → „Modell wählen“):
    - Modelle: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`
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
