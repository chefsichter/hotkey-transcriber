import signal
import sys

from hotkey_transcriber.backend_manager import resolve_backend
from hotkey_transcriber.config.config_manger import load_config, save_config
from hotkey_transcriber.object_loader import (
    load_keyboard_listener,
    load_model,
    load_speech_recorder,
)
from hotkey_transcriber.resources_manger import get_microphone_icon_path


config = load_config()

MODEL_SIZE = config.get("model_size", "large-v3")
MODEL_INFOS = config.get("model_infos", {})
LANGUAGE_CODES = config.get("language_codes", [["de", "Deutsch"], ["en", "English"]])
WAIT_ON_KEYBOARD = config.get("wait_on_keyboard", 0.02)
LANGUAGE = config.get("language", "de")
REC_MARK = config.get("rec_mark", "🔴 REC")
CHANNELS = config.get("channels", 1)
CHUNK_MS = config.get("chunk_ms", 30)
DEFAULT_TRAY_TIP = "Live-Diktat (Alt+R oder Tray-Menue)"
MODEL_CHOICES = [
    "tiny",
    "base",
    "small",
    "distil-small.en",
    "medium",
    "distil-medium.en",
    "large-v3",
    "large-v3-turbo",
    "distil-large-v3",
    "TheChola/whisper-large-v3-turbo-german-faster-whisper",
]


def _init_runtime():
    runtime = resolve_backend(config)
    backend = runtime["backend"]
    device = runtime["device"]
    compute_type = runtime["compute_type"]

    model = load_model(
        size=MODEL_SIZE,
        device=device,
        compute_type=compute_type,
        backend=backend,
    )

    recorder = load_speech_recorder(
        model=model,
        wait_on_keyboard=WAIT_ON_KEYBOARD,
        channels=CHANNELS,
        chunk_ms=CHUNK_MS,
        language=LANGUAGE,
        rec_mark=REC_MARK,
    )
    hotkey = load_keyboard_listener(recorder)

    return backend, device, compute_type, recorder, hotkey


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    backend, device, compute_type, recorder, hotkey = _init_runtime()

    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QAction, QActionGroup, QApplication, QMenu, QSystemTrayIcon

    app = QApplication(sys.argv)

    icon = QIcon(get_microphone_icon_path())
    tray = QSystemTrayIcon(icon, parent=app)
    tray.setToolTip(DEFAULT_TRAY_TIP)

    menu = QMenu()

    act_start = QAction("Aufnahme starten")
    act_stop = QAction("Aufnahme stoppen")
    act_start.triggered.connect(recorder.start)
    act_stop.triggered.connect(recorder.stop)
    menu.addAction(act_start)
    menu.addAction(act_stop)
    menu.addSeparator()

    model_menu = menu.addMenu("Modell")
    model_menu.setToolTipsVisible(True)
    model_group = QActionGroup(menu)
    model_group.setExclusive(True)

    for m in MODEL_CHOICES:
        action = QAction(m)
        action.setToolTip(MODEL_INFOS.get(m, ""))

        def make_info_slot(a):
            def slot():
                info = a.toolTip() or a.text()
                tray.showMessage("Modell-Info", info, QSystemTrayIcon.Information, 5000)

            return slot

        slot = make_info_slot(action)
        action.triggered.connect(slot)

        action.setCheckable(True)
        if MODEL_SIZE == m:
            action.setChecked(True)

        def make_model_slot(model_name):
            def slot():
                was_running = recorder.running
                if was_running:
                    recorder.stop()
                try:
                    new_model = load_model(
                        size=model_name,
                        device=device,
                        compute_type=compute_type,
                        backend=backend,
                    )
                except Exception as exc:
                    tray.showMessage(
                        "Modellfehler",
                        f"Modell konnte nicht geladen werden: {model_name}",
                        QSystemTrayIcon.Warning,
                        3000,
                    )
                    print(f"Modellwechsel fehlgeschlagen fuer '{model_name}': {exc}")
                    if was_running:
                        recorder.start()
                    return

                recorder.model = new_model
                config["model_size"] = model_name
                save_config(config)
                tray.showMessage(
                    "Modell geaendert",
                    f"Neues Modell: {model_name}",
                    QSystemTrayIcon.Information,
                    1500,
                )

                if was_running:
                    recorder.start()

            return slot

        action.triggered.connect(make_model_slot(m))
        model_group.addAction(action)
        model_menu.addAction(action)

    language_menu = menu.addMenu("Erkennungssprache")
    lang_group = QActionGroup(menu)
    lang_group.setExclusive(True)

    for code, label in LANGUAGE_CODES:
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
                    "Erkennungssprache geaendert",
                    f"Neue Erkennungssprache: {l}",
                    QSystemTrayIcon.Information,
                    1500,
                )

            return slot

        action.triggered.connect(make_lang_slot(code, label))
        lang_group.addAction(action)
        language_menu.addAction(action)

    menu.addSeparator()

    act_exit = QAction("Beenden")
    act_exit.triggered.connect(lambda: (recorder.stop(), hotkey.stop(), app.quit()))
    menu.addAction(act_exit)

    tray.setContextMenu(menu)
    tray.show()

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    print("📥 Tray-Icon verfuegbar." if tray_available else "❌ Fehler: Tray-Icon nicht verfuegbar.")
    print("🎤 Live-Diktat bereit (Alt+R oder ueber das Tray-Menue starten).")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

