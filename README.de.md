# 🚀 Hotkey Transcriber

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**🎙️ Live-Diktier-Tool mit Whisper**

Mit Hotkey Transcriber kannst du per Tastenkombination (Alt+R) kurze Sprachaufnahmen starten und stoppen. Der erkannte Text wird automatisch in das aktive Fenster eingefügt und in die Zwischenablage kopiert.

## 📑 Inhaltsverzeichnis
- [✨ Features](#features)
- [🛠️ Voraussetzungen](#voraussetzungen)
- [⚙️ Installation](#installation)
- [🐧 Linux-spezifische Schritte](#linux-spezifische-schritte)
- [🪟 Windows-spezifische Schritte](#windows-spezifische-schritte)
- [🎉 Nutzung](#nutzung)
- [⚙️ Konfiguration](#konfiguration)
- [💡 Tipps & Tricks](#tipps--tricks)
- [📄 Mitwirken](#mitwirken)
- [📜 Lizenz](#lizenz)

## ✨ Features
- 🔊 Live-Diktat mit OpenAI Whisper (via `faster-whisper`)
- ⌨️ Aufnahme per Hotkey (Alt+R)
- 🖥️ Traysymbol (Windows & Linux)
- 📋 Automatisches Einfügen des Transkripts
- ⚙️ Einstellbares Transkriptions-Intervall und Sprache

## 🛠️ Voraussetzungen
- 🐍 Python 3.10+
- 🦊 Git
- Betriebssystemabhängige Bibliotheken:
  - 🐧 Linux (Debian/Ubuntu): `sudo apt install python3-venv python3-dev portaudio19-dev`
  - 🪟 Windows: Visual Studio Build Tools (für native Abhängigkeiten)

## ⚙️ Installation
  
### 1️⃣ Einfache Installation (One-shot-Skript)

Nutze das One-shot-Installer-Skript (`tools/setup_env.py`), das automatisch eine virtuelle Umgebung anlegt und alle Abhängigkeiten inklusive PyTorch installiert:

```bash
python3 tools/setup_env.py
```

Auf Windows:
```powershell
py tools/setup_env.py
```

### 2️⃣ Manuelle Installation
  
1. Repository klonen
   ```bash
   git clone <REPO_URL>
   cd hotkey-transcriber
   ```

2. Virtuelle Umgebung anlegen und aktivieren
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

3. Abhängigkeiten installieren
   ```bash
   pip install -e .
   ```

4. Optional: PyTorch-Version wählen
   - CPU-Variante:
     ```bash
     pip install torch==2.2.* torchvision==0.17.* torchaudio==2.2.* --index-url https://download.pytorch.org/whl/cpu
     ```
   - ROCm 6.3 (AMD GPU):
     ```bash
     pip install torch==2.2.2+rocm6.3 torchvision==0.17.2+rocm6.3 torchaudio==2.2.2+rocm6.3 --index-url https://download.pytorch.org/whl/rocm6.3
     ```

## 🐧 Linux-spezifische Schritte
- Desktop-Eintrag und Icon werden bei systemweiter Installation (`sudo pip install .`) automatisch unter `/usr/share/applications` und `/usr/share/icons/hicolor/256x256/apps` abgelegt.
- Für Benutzerinstallationen manuell kopieren:
  ```bash
  cp resources/linux/hotkey_transcriber.desktop ~/.local/share/applications/
  cp resources/icon/hotkey-transcriber.png ~/.local/share/icons/hicolor/256x256/apps/
  ```

## 🪟 Windows-spezifische Schritte
- Nach Aktivierung der virtuellen Umgebung genügt der Befehl:
  ```cmd
  hotkey-transcriber
  ```
- Das Programm startet als Tray-Anwendung.

## 🎉 Nutzung
1. Starte das Programm mit `hotkey-transcriber`.
2. Ein Tray-Symbol erscheint.
3. Drücke `Alt+R`, um die Aufnahme zu starten. Ein rotes Symbol signalisiert die Aufnahme.
4. Lasse `R` los, um die Aufnahme zu stoppen. Der erkannte Text wird eingefügt und kopiert.
5. Über das Tray-Menü kannst du das Transkriptions-Intervall und die Sprache anpassen oder das Programm beenden.

## ⚙️ Konfiguration
Standardwerte werden in einer JSON-Datei unter `~/.config/hotkey-transcriber/config.json` gespeichert. Einstellungen wie Modellgröße, Intervall und Sprache werden automatisch beibehalten.

## 💡 Tipps & Tricks
- Verwende kurze Intervalle (z.B. **0.5s**) für flüssiges Diktat.
- Wähle leichtere Modelle (`tiny` oder `base`) auf schwacher Hardware.

## 📄 Mitwirken
- Fehler melden via Issues
- Pull Requests willkommen
- Siehe [CONTRIBUTING.md](.github/CONTRIBUTING.md) für Details

## 📜 Lizenz
Dieses Projekt steht unter der [MIT License](LICENSE).
