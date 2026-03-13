import io
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path

from hotkey_transcriber import autostart
from hotkey_transcriber.backend_manager import resolve_backend
from hotkey_transcriber.config.config_manger import load_config, save_config
from hotkey_transcriber.object_loader import (
    load_keyboard_listener,
    load_model,
    load_speech_recorder,
)
from hotkey_transcriber.resources_manger import get_microphone_icon_path
from hotkey_transcriber.speech_recorder import normalize_language
from hotkey_transcriber.wake_word import (
    WakeWordListener,
    list_available_wake_word_models,
)


config = load_config()

MODEL_SIZE = config.get("model_size", "large-v3-turbo")
MODEL_INFOS = config.get("model_infos", {})
LANGUAGE_CODES = config.get("language_codes", [["de", "Deutsch"], ["en", "English"]])
WAIT_ON_KEYBOARD = config.get("wait_on_keyboard", 0.02)
LANGUAGE_AUTO_CODE = "auto"
LANGUAGE_AUTO_LABEL = "Auto"
REC_MARK = config.get("rec_mark", "🔴 REC")
CHANNELS = config.get("channels", 1)
CHUNK_MS = config.get("chunk_ms", 30)
SILENCE_TIMEOUT_MS = config.get("silence_timeout_ms", 1500)
MAX_INITIAL_WAIT_MS = config.get("max_initial_wait_ms", 5000)
NOTIFY_TIMEOUT_MS = config.get("notify_timeout_ms", 1500)
WAKE_WORD_RESUME_DELAY_MS = config.get("wake_word_resume_delay_ms", 1000)
WAKE_WORD_ENABLED = config.get("wake_word_enabled", False)
WAKE_WORD_MODEL = config.get("wake_word_model", "hey jarvis")
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

_LOG_FILE_HANDLE = None


def _language_config_value(value):
    normalized = normalize_language(value)
    if normalized is None:
        return LANGUAGE_AUTO_CODE
    return normalized


def _language_menu_options():
    options = [(LANGUAGE_AUTO_CODE, LANGUAGE_AUTO_LABEL)]
    options.extend(
        (code, label)
        for code, label in LANGUAGE_CODES
        if code != LANGUAGE_AUTO_CODE
    )
    return options


LANGUAGE = normalize_language(config.get("language", "de"))


class _TeeStream(io.TextIOBase):
    def __init__(self, original, logfile):
        self._original = original
        self._logfile = logfile

    def write(self, text):
        if not isinstance(text, str):
            text = str(text)
        self._logfile.write(text)
        self._logfile.flush()
        if self._original and hasattr(self._original, "write"):
            try:
                self._original.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self):
        self._logfile.flush()
        if self._original and hasattr(self._original, "flush"):
            try:
                self._original.flush()
            except Exception:
                pass


def _runtime_log_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA", str(Path.home())))
    else:
        base = Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    log_dir = base / "hotkey-transcriber" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "hotkey-transcriber.log"


def _setup_log_capture() -> Path:
    global _LOG_FILE_HANDLE
    log_path = _runtime_log_path()
    _LOG_FILE_HANDLE = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _TeeStream(getattr(sys, "stdout", None), _LOG_FILE_HANDLE)
    sys.stderr = _TeeStream(getattr(sys, "stderr", None), _LOG_FILE_HANDLE)
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Hotkey Transcriber started")
    return log_path


def _read_log_tail(path: Path, max_bytes: int = 200_000) -> str:
    if not path.exists():
        return "Noch keine Logs vorhanden."
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        start = max(0, size - max_bytes)
        f.seek(start)
        data = f.read()
    return data.decode("utf-8", errors="replace")


def _init_runtime():
    runtime = resolve_backend(config)
    backend = runtime["backend"]
    device = runtime["device"]
    compute_type = runtime["compute_type"]
    use_torch_whisper = runtime.get("use_torch_whisper", False)

    model = load_model(
        size=MODEL_SIZE,
        device=device,
        compute_type=compute_type,
        backend=backend,
        use_torch_whisper=use_torch_whisper,
    )

    recorder = load_speech_recorder(
        model=model,
        wait_on_keyboard=WAIT_ON_KEYBOARD,
        channels=CHANNELS,
        chunk_ms=CHUNK_MS,
        language=LANGUAGE,
        rec_mark=REC_MARK,
        silence_timeout_ms=SILENCE_TIMEOUT_MS,
        max_initial_wait_ms=MAX_INITIAL_WAIT_MS,
    )
    hotkey_config = config.get("hotkey", _DEFAULT_HOTKEY)
    hotkey = load_keyboard_listener(recorder, hotkey_config=hotkey_config)

    # Callback activated by wake word detection
    def on_wake_word_detected():
        if not recorder.running:
            ww_listener.pause()
            recorder.start(
                auto_stop=True,
                silence_timeout_ms=SILENCE_TIMEOUT_MS,
                max_initial_wait_ms=MAX_INITIAL_WAIT_MS,
            )

    ww_listener = WakeWordListener(callback=on_wake_word_detected, model_name=WAKE_WORD_MODEL)
    if WAKE_WORD_ENABLED:
        ww_listener.start()

    return backend, device, compute_type, use_torch_whisper, recorder, hotkey, ww_listener, on_wake_word_detected


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
    # Cast modifier flags to int first - PyQt5 returns KeyboardModifiers objects,
    # which don't support bitwise NOT (~) mixed with plain ints.
    combo = seq[0]
    _ALL_MODS = int(Qt.ShiftModifier) | int(Qt.ControlModifier) | int(Qt.AltModifier) | int(Qt.MetaModifier)
    key_int = combo & ~_ALL_MODS
    mod_int = combo & (int(Qt.ShiftModifier) | int(Qt.ControlModifier) | int(Qt.AltModifier))

    if not mod_int:
        return None  # no modifier - reject

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
    log_path = _setup_log_capture()

    backend, device, compute_type, use_torch_whisper, recorder, hotkey, ww_listener, _on_wake_word = _init_runtime()
    hotkey_ref = [hotkey]  # mutable container so the exit lambda always sees the current listener

    from PyQt5.QtCore import QMetaObject, Qt, pyqtSignal, QObject
    from PyQt5.QtGui import QIcon, QTextCursor
    from PyQt5.QtWidgets import (
        QAction,
        QActionGroup,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,

        QFormLayout,
        QLabel,
        QMenu,
        QPlainTextEdit,
        QPushButton,
        QSpinBox,
        QSystemTrayIcon,
        QVBoxLayout,
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon = QIcon(get_microphone_icon_path())
    tray = QSystemTrayIcon(icon, parent=app)

    # Helper: thread-safe desktop notification
    # On Linux QSystemTrayIcon.showMessage() is unreliable (depends on
    # desktop notification daemon).  Use notify-send which works everywhere.
    # notify-send -t is ignored by most DEs, so we close the previous
    # notification via --replace-id and gdbus after the configured timeout.
    _notify_timeout_ms = NOTIFY_TIMEOUT_MS

    if sys.platform == "linux":
        import subprocess as _sp

        _notify_icon_path = get_microphone_icon_path()
        _last_notify_id = [0]  # mutable container for replace-id

        def _close_notification(nid: int):
            """Close a notification by its id via the freedesktop DBus interface."""
            try:
                _sp.Popen(
                    ["gdbus", "call", "--session",
                     "--dest", "org.freedesktop.Notifications",
                     "--object-path", "/org/freedesktop/Notifications",
                     "--method", "org.freedesktop.Notifications.CloseNotification",
                     str(nid)],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                )
            except FileNotFoundError:
                pass

        def _tray_notify(title: str, msg: str, icon_type=QSystemTrayIcon.Information, ms: int = 0):
            if ms <= 0:
                ms = _notify_timeout_ms
            try:
                proc = _sp.run(
                    ["gdbus", "call", "--session",
                     "--dest", "org.freedesktop.Notifications",
                     "--object-path", "/org/freedesktop/Notifications",
                     "--method", "org.freedesktop.Notifications.Notify",
                     "Hotkey Transcriber",               # app_name
                     str(_last_notify_id[0]),             # replaces_id
                     _notify_icon_path,                   # icon
                     title, msg,
                     "[]",                                # actions
                     "{}",                                # hints
                     str(ms)],                            # expire_timeout
                    capture_output=True, text=True, timeout=3,
                )
                # gdbus returns e.g. "(uint32 42,)\n" — extract the id
                out = proc.stdout.strip()
                if out.startswith("(uint32 "):
                    nid = int(out.split()[1].rstrip(",)"))
                    _last_notify_id[0] = nid
                    # Schedule close after timeout (DEs often ignore expire_timeout)
                    threading.Timer(ms / 1000.0, _close_notification, args=(nid,)).start()
            except (FileNotFoundError, _sp.TimeoutExpired):
                # Fallback: plain notify-send without auto-close
                try:
                    _sp.Popen(
                        ["notify-send", "-t", str(ms), "-i", _notify_icon_path,
                         "--app-name", "Hotkey Transcriber", title, msg],
                        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                    )
                except FileNotFoundError:
                    pass
    else:
        class _TraySignals(QObject):
            show_message = pyqtSignal(str, str, int, int)

        _tray_signals = _TraySignals()
        _tray_signals.show_message.connect(
            lambda title, msg, icon_type, ms: tray.showMessage(title, msg, icon_type, ms)
        )

        def _tray_notify(title: str, msg: str, icon_type=QSystemTrayIcon.Information, ms: int = 0):
            if ms <= 0:
                ms = _notify_timeout_ms
            _tray_signals.show_message.emit(title, msg, icon_type, ms)
    tray.setToolTip(_build_tray_tooltip(config.get("hotkey", _DEFAULT_HOTKEY)))

    menu = QMenu()

    act_start = QAction("Aufnahme starten")
    act_stop = QAction("Aufnahme stoppen")

    def _resume_wake_word_if_idle():
        import time as _time
        # Short delay so the wake word model doesn't immediately
        # re-trigger from residual audio/scores.
        _time.sleep(WAKE_WORD_RESUME_DELAY_MS / 1000.0)
        # Only resume if recorder is idle — if a new recording started in the
        # meantime, the wake word stream must not open alongside the recorder.
        if ww_listener.running and not recorder.running:
            ww_listener.resume()

    # Patch the wake word callback to show tray notifications
    def _notifying_wake_word_callback():
        if not recorder.running:
            ww_listener.pause()
            _tray_notify("Aufnahme gestartet", "Wake Word erkannt – Aufnahme läuft…")
            recorder.start(
                auto_stop=True,
                silence_timeout_ms=SILENCE_TIMEOUT_MS,
                max_initial_wait_ms=MAX_INITIAL_WAIT_MS,
            )
    ww_listener.callback = _notifying_wake_word_callback

    def _start_recording_wrapper(*args, auto_stop=False, **kwargs):
        if ww_listener.running:
            ww_listener.pause()
        recorder.start(auto_stop=auto_stop)

    original_recorder_stop = recorder.stop
    def _patched_recorder_stop(*args, **kwargs):
        was_running = recorder.running
        original_recorder_stop()
        if was_running and ww_listener.running:
            _tray_notify("Aufnahme beendet", "Transkription läuft…")
            # Resume in a background thread so calling code isn't blocked
            threading.Thread(target=_resume_wake_word_if_idle, daemon=True).start()
    recorder.stop = _patched_recorder_stop

    hotkey_ref[0].start_callback = _start_recording_wrapper
    hotkey_ref[0].stop_callback = recorder.stop

    act_start.triggered.connect(_start_recording_wrapper)
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
                _tray_notify("Modell-Info", info)

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
                        use_torch_whisper=use_torch_whisper,
                    )
                except Exception as exc:
                    _tray_notify(
                        "Modellfehler",
                        f"Modell konnte nicht geladen werden: {model_name}",
                    )
                    print(f"Modellwechsel fehlgeschlagen fuer '{model_name}': {exc}")
                    if was_running:
                        _start_recording_wrapper()
                    return

                recorder.model = new_model
                config["model_size"] = model_name
                save_config(config)
                _tray_notify(
                    "Modell geaendert",
                    f"Neues Modell: {model_name}",
                )

                if was_running:
                    _start_recording_wrapper()

            return slot

        action.triggered.connect(make_model_slot(m))
        model_group.addAction(action)
        model_menu.addAction(action)

    language_menu = menu.addMenu("Erkennungssprache")
    lang_group = QActionGroup(menu)
    lang_group.setExclusive(True)

    current_language = _language_config_value(recorder.language)

    for code, label in _language_menu_options():
        action = QAction(label)
        action.setCheckable(True)
        if current_language == code:
            action.setChecked(True)

        def make_lang_slot(c, l):
            def slot():
                recorder.set_language(c)
                config["language"] = _language_config_value(c)
                save_config(config)
                _tray_notify(
                    "Erkennungssprache geaendert",
                    f"Neue Erkennungssprache: {l}",
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
            new_hotkey.start_callback = _start_recording_wrapper
            new_hotkey.stop_callback = recorder.stop
            hotkey_ref[0] = new_hotkey
            config["hotkey"] = result
            save_config(config)
            _refresh_hotkey_ui(result)
            _tray_notify(
                "Tastenkombination geändert",
                f"Neue Tastenkombination: {_hotkey_label(result)}",
            )
        else:
            # Restart with the existing config
            old_cfg = config.get("hotkey", _DEFAULT_HOTKEY)
            restored = load_keyboard_listener(recorder, hotkey_config=old_cfg)
            restored.start_callback = _start_recording_wrapper
            restored.stop_callback = recorder.stop
            hotkey_ref[0] = restored
            _refresh_hotkey_ui(old_cfg)

    act_hotkey.triggered.connect(_on_change_hotkey)
    menu.addAction(act_hotkey)
    
    # --- Wake Word ---
    menu.addSeparator()
    wake_word_menu = menu.addMenu("Wake Word")
    act_ww_toggle = QAction()
    act_ww_toggle.setCheckable(True)

    def _refresh_wake_word_ui(model_name: str):
        act_ww_toggle.setText(f"Aktivieren ('{model_name.title()}')")

    _refresh_wake_word_ui(ww_listener.model_name)
    
    if not ww_listener.is_supported:
        act_ww_toggle.setEnabled(False)
        act_ww_toggle.setToolTip("openwakeword ist nicht installiert.")
    else:
        act_ww_toggle.setChecked(WAKE_WORD_ENABLED)
        
        def _on_toggle_ww(checked):
            config["wake_word_enabled"] = checked
            save_config(config)
            if checked:
                ww_listener.model_name = config.get("wake_word_model", ww_listener.model_name)
                _refresh_wake_word_ui(ww_listener.model_name)
                ww_listener.start()
                _tray_notify(
                    "Wake Word aktiviert",
                    f"Lauscht nach: '{ww_listener.model_name}'",
                )
            else:
                ww_listener.stop()
                _tray_notify(
                    "Wake Word deaktiviert",
                    "Wake Word Erkennung gestoppt.",
                )
                
        act_ww_toggle.toggled.connect(_on_toggle_ww)
    
    wake_word_menu.addAction(act_ww_toggle)
    # -----------------

    # --- Einstellungen ---
    act_settings = QAction("Einstellungen…")

    # Available wake word models for the combo box
    _WW_MODELS = list_available_wake_word_models()

    def _on_show_settings():
        global SILENCE_TIMEOUT_MS, MAX_INITIAL_WAIT_MS, NOTIFY_TIMEOUT_MS, WAKE_WORD_RESUME_DELAY_MS

        dlg = QDialog()
        dlg.setWindowTitle("Einstellungen")
        form = QFormLayout(dlg)

        sp_silence = QSpinBox(dlg)
        sp_silence.setRange(500, 10000)
        sp_silence.setSuffix(" ms")
        sp_silence.setSingleStep(100)
        sp_silence.setValue(SILENCE_TIMEOUT_MS)
        form.addRow("Stille bis Auto-Stop:", sp_silence)

        sp_initial_wait = QSpinBox(dlg)
        sp_initial_wait.setRange(0, 10000)
        sp_initial_wait.setSuffix(" ms")
        sp_initial_wait.setSingleStep(100)
        sp_initial_wait.setSpecialValueText("deaktiviert")
        sp_initial_wait.setValue(MAX_INITIAL_WAIT_MS)
        form.addRow("Max. Anfangswarten:", sp_initial_wait)

        sp_notify = QSpinBox(dlg)
        sp_notify.setRange(200, 10000)
        sp_notify.setSuffix(" ms")
        sp_notify.setSingleStep(100)
        sp_notify.setValue(NOTIFY_TIMEOUT_MS)
        form.addRow("Benachrichtigungsdauer:", sp_notify)

        sp_resume = QSpinBox(dlg)
        sp_resume.setRange(100, 10000)
        sp_resume.setSuffix(" ms")
        sp_resume.setSingleStep(100)
        sp_resume.setValue(WAKE_WORD_RESUME_DELAY_MS)
        form.addRow("Wake-Word Resume-Delay:", sp_resume)

        cb_ww = QCheckBox("Aktiviert", dlg)
        cb_ww.setChecked(config.get("wake_word_enabled", False))
        form.addRow("Wake Word:", cb_ww)

        combo_ww = QComboBox(dlg)
        combo_ww.addItems(_WW_MODELS)
        current_model = config.get("wake_word_model", "hey jarvis")
        idx = combo_ww.findText(current_model)
        if idx >= 0:
            combo_ww.setCurrentIndex(idx)
        else:
            combo_ww.addItem(current_model)
            combo_ww.setCurrentText(current_model)
        form.addRow("Wake-Word Modell:", combo_ww)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg
        )
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec_() != QDialog.Accepted:
            return

        # Apply values
        SILENCE_TIMEOUT_MS = sp_silence.value()
        MAX_INITIAL_WAIT_MS = sp_initial_wait.value()
        NOTIFY_TIMEOUT_MS = sp_notify.value()
        WAKE_WORD_RESUME_DELAY_MS = sp_resume.value()

        config["silence_timeout_ms"] = SILENCE_TIMEOUT_MS
        config["max_initial_wait_ms"] = MAX_INITIAL_WAIT_MS
        config["notify_timeout_ms"] = NOTIFY_TIMEOUT_MS
        config["wake_word_resume_delay_ms"] = WAKE_WORD_RESUME_DELAY_MS

        new_ww_enabled = cb_ww.isChecked()
        new_ww_model = combo_ww.currentText()
        previous_ww_model = ww_listener.model_name
        config["wake_word_enabled"] = new_ww_enabled
        config["wake_word_model"] = new_ww_model
        save_config(config)
        ww_listener.model_name = new_ww_model
        _refresh_wake_word_ui(new_ww_model)

        # Update _notify_timeout_ms used by _tray_notify
        nonlocal _notify_timeout_ms
        _notify_timeout_ms = NOTIFY_TIMEOUT_MS

        # Sync wake word toggle checkbox
        act_ww_toggle.blockSignals(True)
        act_ww_toggle.setChecked(new_ww_enabled)
        act_ww_toggle.blockSignals(False)

        # Apply wake word changes
        if new_ww_enabled and not ww_listener.running:
            ww_listener.start()
        elif not new_ww_enabled and ww_listener.running:
            ww_listener.stop()
        elif ww_listener.running and new_ww_model != previous_ww_model:
            ww_listener.stop()
            ww_listener.start()

        _tray_notify("Einstellungen", "Einstellungen gespeichert.")

    act_settings.triggered.connect(_on_show_settings)
    menu.addAction(act_settings)
    menu.addSeparator()
    # ---------------------

    if autostart.is_supported():
        act_autostart = QAction("Beim Anmelden starten")
        act_autostart.setCheckable(True)
        act_autostart.setChecked(autostart.is_enabled())

        def _on_toggle_autostart(checked):
            try:
                autostart.set_enabled(checked)
                state_label = "aktiviert" if checked else "deaktiviert"
                _tray_notify(
                    "Autostart",
                    f"Autostart {state_label}.",
                )
            except Exception as exc:
                act_autostart.blockSignals(True)
                act_autostart.setChecked(not checked)
                act_autostart.blockSignals(False)
                _tray_notify(
                    "Autostart-Fehler",
                    "Autostart konnte nicht geaendert werden.",
                )
                print(f"Autostart konnte nicht geaendert werden: {exc}")

        act_autostart.toggled.connect(_on_toggle_autostart)
        menu.addAction(act_autostart)

    act_logs = QAction("Logs anzeigen…")

    def _on_show_logs():
        dialog = QDialog()
        dialog.setWindowTitle("Hotkey Transcriber Logs")
        dialog.resize(820, 520)

        layout = QVBoxLayout(dialog)
        editor = QPlainTextEdit(dialog)
        editor.setReadOnly(True)
        layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=dialog)
        refresh_btn = QPushButton("Aktualisieren", dialog)
        buttons.addButton(refresh_btn, QDialogButtonBox.ActionRole)
        layout.addWidget(buttons)

        def _reload():
            editor.setPlainText(_read_log_tail(log_path))
            editor.moveCursor(QTextCursor.End)

        refresh_btn.clicked.connect(_reload)
        buttons.rejected.connect(dialog.reject)
        _reload()
        dialog.exec_()

    act_logs.triggered.connect(_on_show_logs)
    menu.addAction(act_logs)

    menu.addSeparator()

    act_exit = QAction("Beenden")
    act_exit.triggered.connect(lambda: (recorder.stop(), ww_listener.stop(), hotkey_ref[0].stop(), app.quit()))
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
