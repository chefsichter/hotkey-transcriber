import signal
import sys

from hotkey_transcriber import autostart
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
DEFAULT_TRAY_TIP = "Live-Diktat"

_DEFAULT_HOTKEY = {"modifier": "alt", "key": "r"}
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
    hotkey_config = config.get("hotkey", _DEFAULT_HOTKEY)
    hotkey = load_keyboard_listener(recorder, hotkey_config=hotkey_config)

    return backend, device, compute_type, recorder, hotkey


def _show_hotkey_dialog(parent=None):
    """Open a dialog to capture a new hotkey combination.

    Returns a dict {"modifier": ..., "key": ...} on OK, or None on cancel.
    Only accepts combinations that include at least one of Alt/Ctrl/Shift
    (rejects naked keys to avoid clobbering normal typing).
    """
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeySequence
    from PyQt5.QtWidgets import (
        QDialog, QDialogButtonBox, QKeySequenceEdit, QLabel, QVBoxLayout,
    )

    dialog = QDialog(parent)
    dialog.setWindowTitle("Tastenkombination ändern")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Neue Tastenkombination eingeben:"))
    seq_edit = QKeySequenceEdit(dialog)
    layout.addWidget(seq_edit)
    hint = QLabel("<small>Erlaubt: Alt, Ctrl, Shift und Kombinationen davon + eine Taste</small>")
    hint.setTextFormat(Qt.RichText)
    layout.addWidget(hint)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    if dialog.exec_() != QDialog.Accepted:
        return None

    seq = seq_edit.keySequence()
    if seq.isEmpty():
        return None

    # QKeySequence stores the combo as an int; decode it.
    # Cast modifier flags to int first — PyQt5 returns KeyboardModifiers objects,
    # which don't support bitwise NOT (~) mixed with plain ints.
    combo = seq[0]
    _ALL_MODS = int(Qt.ShiftModifier) | int(Qt.ControlModifier) | int(Qt.AltModifier) | int(Qt.MetaModifier)
    key_int = combo & ~_ALL_MODS
    mod_int = combo & (int(Qt.ShiftModifier) | int(Qt.ControlModifier) | int(Qt.AltModifier))

    if not mod_int:
        return None  # no modifier – reject

    # Build modifier string
    parts = []
    for qt_mod, name in [
        (int(Qt.ShiftModifier), "shift"),
        (int(Qt.ControlModifier), "ctrl"),
        (int(Qt.AltModifier), "alt"),
    ]:
        if mod_int & qt_mod:
            parts.append(name)
    modifier_str = "+".join(parts)

    # Resolve key name
    key_str = QKeySequence(key_int).toString().lower()
    if not key_str:
        return None

    return {"modifier": modifier_str, "key": key_str}


def _hotkey_label(cfg: dict) -> str:
    mod = cfg.get("modifier", "alt").replace("+", "+").title()
    key = cfg.get("key", "r").upper()
    return f"{mod}+{key}"


def _build_tray_tooltip(hotkey_cfg: dict) -> str:
    return f"{DEFAULT_TRAY_TIP} | Hotkey: {_hotkey_label(hotkey_cfg)}"


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    backend, device, compute_type, recorder, hotkey = _init_runtime()
    hotkey_ref = [hotkey]  # mutable container so the exit lambda always sees the current listener

    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QAction, QActionGroup, QApplication, QMenu, QSystemTrayIcon

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon = QIcon(get_microphone_icon_path())
    tray = QSystemTrayIcon(icon, parent=app)
    tray.setToolTip(_build_tray_tooltip(config.get("hotkey", _DEFAULT_HOTKEY)))

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

    current_hotkey_cfg = config.get("hotkey", _DEFAULT_HOTKEY)
    act_hotkey_info = QAction(f"Aktueller Hotkey: {_hotkey_label(current_hotkey_cfg)}")
    act_hotkey_info.setEnabled(False)
    menu.addAction(act_hotkey_info)

    act_hotkey = QAction("Tastenkombination ändern…")

    def _refresh_hotkey_ui(cfg: dict):
        act_hotkey_info.setText(f"Aktueller Hotkey: {_hotkey_label(cfg)}")
        tray.setToolTip(_build_tray_tooltip(cfg))

    def _on_change_hotkey():
        hotkey_ref[0].stop()
        result = _show_hotkey_dialog()
        if result:
            new_hotkey = load_keyboard_listener(recorder, hotkey_config=result)
            hotkey_ref[0] = new_hotkey
            config["hotkey"] = result
            save_config(config)
            _refresh_hotkey_ui(result)
            tray.showMessage(
                "Tastenkombination geändert",
                f"Neue Tastenkombination: {_hotkey_label(result)}",
                QSystemTrayIcon.Information,
                2000,
            )
        else:
            # Restart with the existing config
            old_cfg = config.get("hotkey", _DEFAULT_HOTKEY)
            restored = load_keyboard_listener(recorder, hotkey_config=old_cfg)
            hotkey_ref[0] = restored
            _refresh_hotkey_ui(old_cfg)

    act_hotkey.triggered.connect(_on_change_hotkey)
    menu.addAction(act_hotkey)

    if autostart.is_supported():
        act_autostart = QAction("Beim Anmelden starten")
        act_autostart.setCheckable(True)
        act_autostart.setChecked(autostart.is_enabled())

        def _on_toggle_autostart(checked):
            try:
                autostart.set_enabled(checked)
                state_label = "aktiviert" if checked else "deaktiviert"
                tray.showMessage(
                    "Autostart",
                    f"Autostart {state_label}.",
                    QSystemTrayIcon.Information,
                    2000,
                )
            except Exception as exc:
                act_autostart.blockSignals(True)
                act_autostart.setChecked(not checked)
                act_autostart.blockSignals(False)
                tray.showMessage(
                    "Autostart-Fehler",
                    "Autostart konnte nicht geaendert werden.",
                    QSystemTrayIcon.Warning,
                    3000,
                )
                print(f"Autostart konnte nicht geaendert werden: {exc}")

        act_autostart.toggled.connect(_on_toggle_autostart)
        menu.addAction(act_autostart)

    menu.addSeparator()

    act_exit = QAction("Beenden")
    act_exit.triggered.connect(lambda: (recorder.stop(), hotkey_ref[0].stop(), app.quit()))
    menu.addAction(act_exit)

    tray.setContextMenu(menu)
    tray.show()

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    print("📥 Tray-Icon verfuegbar." if tray_available else "❌ Fehler: Tray-Icon nicht verfuegbar.")
    _current_label = _hotkey_label(config.get("hotkey", _DEFAULT_HOTKEY))
    print(f"🎤 Live-Diktat bereit ({_current_label} oder ueber das Tray-Menue starten).")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
