import platform
import shutil
import sys
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction, QActionGroup
)
from PyQt5.QtGui import QIcon

from .device_detector import detect_device
from .keyboard_controller import KeyboardController
from .keyboard_listener  import KeyBoardListener
from .speech_recorder    import SpeechRecorder
from .config.config_manger import load_config, save_config


# ─────────────────────── Konfiguration ────────────────────────
config = load_config()
MODEL_SIZE          = config.get("model_size", "large-v3") # tiny, base, small, medium, large-v3, distil-large-v3, large-v3-turbo, turbo
TRANSCRIBE_INTERVAL = config.get("interval", 1) # Alle 1 Sekunden wird Audio mit Modell transcribiert
WAIT_ON_KEYBOARD    = config.get("wait_on_keyboard", 0.02) # Wartezeitinterval bei mehrerem Tastendrücken
LANGUAGE            = config.get("language", "de") # whisper unterstützt multilingual (=de) oder en
REC_MARK            = config.get("rec_mark", "🔴 REC")
CHANNELS            = config.get("channels", 1) # 1 Channel = Mono
CHUNK_MS            = config.get("chunk_ms", 30) # wie viele Millisekunden Audio auf einmal geliefert wird

# ───────── Whisper-Modell laden ──────────────────────────────
device = detect_device()
c_type = "float16" if device == 'cuda' else "float32"
print(f"⏳  Lade Whisper-Modell auf '{device}'…", flush=True)
model = WhisperModel(MODEL_SIZE, device=device, compute_type=c_type)
print(f"✅  Whisper-Modell mit Grösse '{MODEL_SIZE}' bereit.")

# ─────────────────── Aufnahme-Logik ──────────────────────────
print(f"⏳  Lade SpeechRecorder…", flush=True)
keyboard_controller = KeyboardController(wait=WAIT_ON_KEYBOARD)

recorder = SpeechRecorder(
    model=model,
    keyboard_controller=keyboard_controller,
    channels=CHANNELS,
    chunk_ms=CHUNK_MS,
    interval=TRANSCRIBE_INTERVAL,
    language=LANGUAGE,
    rec_mark=REC_MARK
)
print("✅  SpeechRecorder bereit.")

# ─────────────────── Keyboard-Logik ──────────────────────────
print(f"⏳  Lade KeyBoardListener...", flush=True)
hotkey = KeyBoardListener(
    start_callback=recorder.start,
    stop_callback=recorder.stop
)
hotkey.start()
print("✅  KeyBoardListener bereit.")

def main():
    # Erlaube Unterbrechen mit Ctrl+C in der Konsole
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)

    # Tray-Icon (schwarz) versuchen, sonst lokales PNG
    icon = QIcon("resources/icon/microphone.png")

    tray = QSystemTrayIcon(icon, parent=app)
    tray.setToolTip("Live-Diktat (Alt+R oder Tray-Menü)")

    menu = QMenu()

    # 1) Start/Stop
    act_start = QAction("Aufnahme starten")
    act_stop  = QAction("Aufnahme stoppen")
    act_start.triggered.connect(recorder.start)
    act_stop.triggered.connect(recorder.stop)
    menu.addAction(act_start)
    menu.addAction(act_stop)
    menu.addSeparator()

    # 2) Modell wählen
    model_menu = menu.addMenu("Modell")
    model_group = QActionGroup(menu)
    model_group.setExclusive(True)
    for m in ["tiny", "base", 
              "small", "distil-small.en", 
              "medium", "distil-medium.en", 
              "large-v3", "large-v3-turbo", "distil-large-v3"]:
        action = QAction(m)
        action.setCheckable(True)
        if MODEL_SIZE == m:
            action.setChecked(True)
        def make_model_slot(model_name):
            def slot():
                was_running = recorder.running
                if was_running:
                    recorder.stop()
                new_model = WhisperModel(model_name, device=device, compute_type=c_type)
                recorder.model = new_model
                config["model_size"] = model_name
                save_config(config)
                tray.showMessage("Modell geändert", f"Neues Modell: {model_name}", QSystemTrayIcon.Information, 1500)
                if was_running:
                    recorder.start()
            return slot
        action.triggered.connect(make_model_slot(m))
        model_group.addAction(action)
        model_menu.addAction(action)

    # 3) Erkennungssprache-Submenu
    language_menu = menu.addMenu("Erkennungssprache")
    lang_group    = QActionGroup(menu)
    lang_group.setExclusive(True)

    for code, label in [("de", "Deutsch"), ("en", "English")]:
        action = QAction(label)
        action.setCheckable(True)
        if recorder.language == code:
            action.setChecked(True)

        def make_lang_slot(c, l):
            def slot():
                recorder.set_language(c)
                config["language"] = c
                save_config(config)
                tray.showMessage(
                    "Erkennungssprache geändert",
                    f"Neue Erkennungssprache: {l}",
                    QSystemTrayIcon.Information,
                    1500
                )
            return slot

        action.triggered.connect(make_lang_slot(code, label))
        lang_group.addAction(action)
        language_menu.addAction(action)


    # 4) Intervall-Submenu
    interval_menu = menu.addMenu("Intervall")
    group = QActionGroup(menu)
    group.setExclusive(True)
    for val in [0.2, 0.5, 1, 2, 3, 5, 10]:
        action = QAction(f"{val}s")
        action.setCheckable(True)
        if recorder.interval == val:
            action.setChecked(True)
        # Mit Closure den Wert binden
        def make_slot(v):
            def slot():
                recorder.set_interval(v)
                config["interval"] = v
                save_config(config)
                tray.showMessage(
                    "Intervall geändert",
                    f"Neues Intervall: {v} Sekunden",
                    QSystemTrayIcon.Information,
                    1500
                )
            return slot
        action.triggered.connect(make_slot(val))
        group.addAction(action)
        interval_menu.addAction(action)

    menu.addSeparator()

    # 5) Exit
    act_exit = QAction("Beenden")
    act_exit.triggered.connect(lambda: (recorder.stop(), hotkey.stop(), app.quit()))
    menu.addAction(act_exit)

    tray.setContextMenu(menu)
    tray.show()
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    print("📥  Tray-Icon verfügbar." if tray_available else "❌ Fehler, Tray-Icon nicht verfügbar." )
    print("🎤  Live-Diktat bereit (Alt+R oder über das Tray-Menü starten).")

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()