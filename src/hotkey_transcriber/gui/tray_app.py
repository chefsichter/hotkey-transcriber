"""
Tray App - PyQt5 system tray application orchestrating recording, wake word, and menus.

Architecture:
    ┌─────────────────────────────────────────┐
    │  TrayApp                                │
    │  ┌───────────────────────────────────┐  │
    │  │  __init__: setup QApp + tray      │  │
    │  │  _patch_recorder_and_wake_word    │  │
    │  │  _build_menu → sub-builders       │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  run() → app.exec_()              │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.gui.tray_app import TrayApp

    app = TrayApp(config, recorder, ...)
    app.run()
"""

import sys

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QActionGroup, QApplication, QMenu, QSystemTrayIcon

from hotkey_transcriber import autostart
from hotkey_transcriber.actions.spoken_text_actions import load_spoken_text_actions
from hotkey_transcriber.config.config_manager import save_config
from hotkey_transcriber.gui.hotkey_change_dialog import (
    build_tray_tooltip,
    hotkey_label,
    show_hotkey_dialog,
)
from hotkey_transcriber.gui.log_dialog import show_log_dialog
from hotkey_transcriber.gui.settings_dialog import show_settings_dialog
from hotkey_transcriber.gui.tray_notifications import TrayNotifier
from hotkey_transcriber.resource_path_resolver import get_microphone_icon_path
from hotkey_transcriber.speech_recorder import normalize_language
from hotkey_transcriber.transcription.model_and_recorder_factory import (
    load_keyboard_listener,
    load_model,
)
from hotkey_transcriber.wake_word.wake_word_listener import list_available_wake_word_models
from hotkey_transcriber.wake_word.wake_word_script_actions import load_wake_word_script_actions

_DEFAULT_HOTKEY = {"modifier": "alt", "key": "r"}

COMMON_MODEL_CHOICES = [
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "large-v3-turbo",
]

WHISPER_CPP_MODEL_CHOICES = COMMON_MODEL_CHOICES + [
    "large-v3-turbo-q8_0",
    "large-v3-turbo-q5_0",
    "large-v3-q8_0",
    "large-v3-q5_0",
    "cstr/whisper-large-v3-turbo-german-ggml",
]

FASTER_WHISPER_MODEL_CHOICES = COMMON_MODEL_CHOICES + [
    "TheChola/whisper-large-v3-turbo-german-faster-whisper",
]


class TrayApp:
    """PyQt5 tray application: builds menus, wires callbacks, runs the Qt event loop."""

    def __init__(
        self,
        config: dict,
        recorder,
        hotkey,
        ww_listener,
        wake_word_script_action_map: dict,
        wake_word_script_action_executor,
        backend: str,
        device: str,
        compute_type: str,
        engine: str,
        log_path,
    ) -> None:
        self.config = config
        self.recorder = recorder
        self.hotkey_ref = [hotkey]
        self.ww_listener = ww_listener
        self.wake_word_script_action_map = wake_word_script_action_map
        self.wake_word_script_action_executor = wake_word_script_action_executor
        self.backend = backend
        self.device = device
        self.compute_type = compute_type
        self.engine = engine
        self.log_path = log_path

        self.silence_timeout_ms: int = config.get("silence_timeout_ms", 1500)
        self.max_initial_wait_ms: int = config.get("max_initial_wait_ms", 5000)
        self.notify_timeout_ms: int = config.get("notify_timeout_ms", 1500)
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        icon_path = get_microphone_icon_path()
        self.tray = QSystemTrayIcon(QIcon(icon_path), parent=self.app)
        self.notifier = TrayNotifier(self.tray, self.notify_timeout_ms, icon_path)
        self._qt_refs: list[object] = []

        self._ww_models = list_available_wake_word_models()
        self._patch_recorder_and_wake_word()
        self._build_menu()

    def _model_choices(self) -> list[str]:
        if self.engine == "whisper_cpp":
            return WHISPER_CPP_MODEL_CHOICES
        return FASTER_WHISPER_MODEL_CHOICES

    # ------------------------------------------------------------------
    # Recording & wake word wiring
    # ------------------------------------------------------------------

    def _start_recording(self, *_args, auto_stop: bool = False, **_kwargs) -> None:
        if self.ww_listener.running:
            self.ww_listener.pause()
        self.recorder.start(auto_stop=auto_stop)

    def _configured_wake_word_models(self) -> list[str]:
        available = set(list_available_wake_word_models())
        models: list[str] = []
        primary = str(self.config.get("wake_word_model", "hey jarvis")).strip()
        if primary:
            models.append(primary)
        if self.wake_word_script_action_executor.enabled:
            for action in self.config.get("wake_word_script_actions", []):
                m = str(action.get("wake_word_model", "")).strip()
                if m and m in available and m not in models:
                    models.append(m)
        return models

    def _patch_recorder_and_wake_word(self) -> None:
        """Patch recorder.stop and set wake word callback before building the menu."""
        recorder = self.recorder
        ww = self.ww_listener

        def _resume_wake_word_if_idle() -> None:
            if ww.running and not recorder.running:
                ww.resume()

        recorder.on_transcription_finished = _resume_wake_word_if_idle

        def _wake_word_callback(detected_name=None) -> None:
            if recorder.running:
                return
            ww.pause()
            print(f"[wakeword] detected='{detected_name}'", flush=True)
            action = None
            if detected_name:
                action = self.wake_word_script_action_executor.action_for_wake_word(detected_name)
            if action is not None:
                self.notifier.notify("Wake-Word-Skript", f"Wake Word '{detected_name}' erkannt…")
                print(
                    f"[wakeword] action trigger='{detected_name}' builtin='{action.builtin}' "
                    f"command='{action.command}' start_recording_after={action.start_recording_after}",
                    flush=True,
                )
                self.wake_word_script_action_executor.execute(action)
                if action.start_recording_after:
                    print(f"[wakeword] start recording after action '{detected_name}'", flush=True)
                    recorder.start(
                        auto_stop=True,
                        silence_timeout_ms=self.silence_timeout_ms,
                        max_initial_wait_ms=self.max_initial_wait_ms,
                    )
                return
            if (
                detected_name
                and detected_name.strip().lower() in self.wake_word_script_action_map
                and not self.wake_word_script_action_executor.enabled
            ):
                print(
                    f"[wakeword] ignored script wake word '{detected_name}' "
                    "because wake-word scripts are disabled",
                    flush=True,
                )
                _resume_wake_word_if_idle()
                return
            if detected_name:
                print(
                    f"[wakeword] no action mapping for '{detected_name}', using normal recording",
                    flush=True,
                )
            self.notifier.notify("Aufnahme gestartet", "Wake Word erkannt – Aufnahme läuft…")
            print(f"[wakeword] start recording from wake word '{detected_name}'", flush=True)
            recorder.start(
                auto_stop=True,
                silence_timeout_ms=self.silence_timeout_ms,
                max_initial_wait_ms=self.max_initial_wait_ms,
            )

        ww.callback = _wake_word_callback

        original_stop = recorder.stop

        def _patched_stop() -> None:
            was_running = recorder.running
            original_stop()
            if was_running and ww.running:
                self.notifier.notify("Aufnahme beendet", "Transkription läuft…")

        recorder.stop = _patched_stop
        self.hotkey_ref[0].start_callback = self._start_recording
        self.hotkey_ref[0].stop_callback = recorder.stop

    # ------------------------------------------------------------------
    # Menu building
    # ------------------------------------------------------------------

    def _keep_qt_ref(self, obj):
        self._qt_refs.append(obj)
        return obj

    def _build_menu(self) -> None:
        menu = QMenu()
        self._menu = menu

        act_start = self._keep_qt_ref(QAction("Aufnahme starten", menu))
        act_stop = self._keep_qt_ref(QAction("Aufnahme stoppen", menu))
        act_start.triggered.connect(self._start_recording)
        act_stop.triggered.connect(self.recorder.stop)
        menu.addAction(act_start)
        menu.addAction(act_stop)
        menu.addSeparator()

        self._build_model_menu(menu)
        self._build_language_menu(menu)
        menu.addSeparator()
        self._build_wake_word_menu(menu)
        self._build_text_actions_menu(menu)
        menu.addSeparator()
        self._build_hotkey_actions(menu)
        self._build_settings_action(menu)
        menu.addSeparator()
        self._build_autostart_action(menu)
        self._build_log_action(menu)
        menu.addSeparator()

        act_exit = self._keep_qt_ref(QAction("Beenden", menu))
        act_exit.triggered.connect(
            lambda: (
                self.recorder.stop(),
                self.ww_listener.stop(),
                self.hotkey_ref[0].stop(),
                self.app.quit(),
            )
        )
        menu.addAction(act_exit)

        self.tray.setContextMenu(menu)
        self.tray.setToolTip(build_tray_tooltip(self.config.get("hotkey", _DEFAULT_HOTKEY)))

    def _build_model_menu(self, parent_menu: QMenu) -> None:
        model_menu = parent_menu.addMenu("Modell")
        assert model_menu is not None
        model_menu.setToolTipsVisible(True)
        self._keep_qt_ref(model_menu)
        group = self._keep_qt_ref(QActionGroup(parent_menu))
        group.setExclusive(True)
        current = self.config.get("model_size", "large-v3-turbo")
        model_infos = self.config.get("model_infos", {})
        for m in self._model_choices():
            action = self._keep_qt_ref(QAction(m, model_menu))
            action.setToolTip(model_infos.get(m, ""))
            action.setCheckable(True)
            if m == current:
                action.setChecked(True)
            action.triggered.connect(self._make_model_info_slot(action))
            action.triggered.connect(self._make_model_slot(m))
            group.addAction(action)
            model_menu.addAction(action)

    def _make_model_info_slot(self, action: QAction):
        def slot() -> None:
            info = action.toolTip() or action.text()
            self.notifier.notify("Modell-Info", info)

        return slot

    def _make_model_slot(self, model_name: str):
        def slot() -> None:
            was_running = self.recorder.running
            if was_running:
                self.recorder.stop()
            try:
                new_model = load_model(
                    size=model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    backend=self.backend,
                    engine=self.engine,
                )
            except Exception as exc:
                self.notifier.notify(
                    "Modellfehler", f"Modell konnte nicht geladen werden: {model_name}"
                )
                print(f"Modellwechsel fehlgeschlagen fuer '{model_name}': {exc}")
                if was_running:
                    self._start_recording()
                return
            self.recorder.model = new_model
            self.config["model_size"] = model_name
            save_config(self.config)
            self.notifier.notify("Modell geaendert", f"Neues Modell: {model_name}")
            if was_running:
                self._start_recording()

        return slot

    def _build_language_menu(self, parent_menu: QMenu) -> None:
        lang_menu = parent_menu.addMenu("Erkennungssprache")
        assert lang_menu is not None
        self._keep_qt_ref(lang_menu)
        group = self._keep_qt_ref(QActionGroup(parent_menu))
        group.setExclusive(True)
        language_codes = self.config.get("language_codes", [["de", "Deutsch"], ["en", "English"]])
        options = [("auto", "Auto")] + [
            (code, label_name) for code, label_name in language_codes if code != "auto"
        ]
        current = normalize_language(self.recorder.language) or "auto"
        for code, label in options:
            action = self._keep_qt_ref(QAction(label, lang_menu))
            action.setCheckable(True)
            if current == code:
                action.setChecked(True)
            action.triggered.connect(self._make_lang_slot(code, label))
            group.addAction(action)
            lang_menu.addAction(action)

    def _make_lang_slot(self, code: str, label: str):
        def slot() -> None:
            self.recorder.set_language(code)
            self.config["language"] = normalize_language(code) or "auto"
            save_config(self.config)
            self.notifier.notify("Erkennungssprache geaendert", f"Neue Erkennungssprache: {label}")

        return slot

    def _build_hotkey_actions(self, parent_menu: QMenu) -> None:
        cfg = self.config.get("hotkey", _DEFAULT_HOTKEY)
        self._act_hotkey_info = self._keep_qt_ref(
            QAction(f"Aktueller Hotkey: {hotkey_label(cfg)}", parent_menu)
        )
        self._act_hotkey_info.setEnabled(False)
        parent_menu.addAction(self._act_hotkey_info)
        act_hotkey = self._keep_qt_ref(QAction("Tastenkombination ändern…", parent_menu))
        act_hotkey.triggered.connect(self._on_change_hotkey)
        parent_menu.addAction(act_hotkey)

    def _on_change_hotkey(self) -> None:
        self.hotkey_ref[0].stop()
        result = show_hotkey_dialog()
        cfg = result if result else self.config.get("hotkey", _DEFAULT_HOTKEY)
        if result:
            self.config["hotkey"] = result
            save_config(self.config)
            self.notifier.notify(
                "Tastenkombination geändert", f"Neue Tastenkombination: {hotkey_label(result)}"
            )
        new_hotkey = load_keyboard_listener(self.recorder, hotkey_config=cfg)
        new_hotkey.start_callback = self._start_recording
        new_hotkey.stop_callback = self.recorder.stop
        self.hotkey_ref[0] = new_hotkey
        self._act_hotkey_info.setText(f"Aktueller Hotkey: {hotkey_label(cfg)}")
        self.tray.setToolTip(build_tray_tooltip(cfg))

    def _build_wake_word_menu(self, parent_menu: QMenu) -> None:
        wake_word_menu = parent_menu.addMenu("Wake Word")
        assert wake_word_menu is not None
        self._keep_qt_ref(wake_word_menu)
        self._act_ww_toggle = self._keep_qt_ref(QAction(wake_word_menu))
        self._act_ww_toggle.setCheckable(True)
        self._refresh_ww_toggle_label(self.ww_listener.model_name)
        if not self.ww_listener.is_supported:
            self._act_ww_toggle.setEnabled(False)
            self._act_ww_toggle.setToolTip("openwakeword ist nicht installiert.")
        else:
            self._act_ww_toggle.setChecked(self.config.get("wake_word_enabled", False))
            self._act_ww_toggle.toggled.connect(self._on_toggle_ww)
        wake_word_menu.addAction(self._act_ww_toggle)

    def _refresh_ww_toggle_label(self, model_name: str) -> None:
        self._act_ww_toggle.setText(f"Aktivieren ('{model_name.title()}')")

    def _on_toggle_ww(self, checked: bool) -> None:
        self.config["wake_word_enabled"] = checked
        save_config(self.config)
        if checked:
            self.ww_listener.model_name = self.config.get(
                "wake_word_model", self.ww_listener.model_name
            )
            self.ww_listener.model_names = self._configured_wake_word_models()
            self._refresh_ww_toggle_label(self.ww_listener.model_name)
            self.ww_listener.start()
            self.notifier.notify(
                "Wake Word aktiviert",
                f"Lauscht nach: {', '.join(self.ww_listener.model_names)}",
            )
        else:
            self.ww_listener.stop()
            self.notifier.notify("Wake Word deaktiviert", "Wake Word Erkennung gestoppt.")

    def _build_text_actions_menu(self, parent_menu: QMenu) -> None:
        text_actions_menu = parent_menu.addMenu("Text-Sprachaktionen")
        assert text_actions_menu is not None
        self._keep_qt_ref(text_actions_menu)
        act_spoken_enter = self._keep_qt_ref(QAction("Enter", text_actions_menu))
        act_spoken_enter.setCheckable(True)
        act_spoken_enter.setChecked(self.recorder.spoken_enter_enabled)
        act_spoken_enter.toggled.connect(self._on_toggle_spoken_enter)
        text_actions_menu.addAction(act_spoken_enter)

        act_spoken_undo = self._keep_qt_ref(QAction("Undo", text_actions_menu))
        act_spoken_undo.setCheckable(True)
        act_spoken_undo.setChecked(self.recorder.spoken_undo_enabled)
        act_spoken_undo.toggled.connect(self._on_toggle_spoken_undo)
        text_actions_menu.addAction(act_spoken_undo)

        self._act_ww_scripts = self._keep_qt_ref(QAction("Wake-Word-Skripte", parent_menu))
        self._act_ww_scripts.setCheckable(True)
        self._act_ww_scripts.setChecked(self.wake_word_script_action_executor.enabled)
        if not self.wake_word_script_action_executor.has_actions:
            self._act_ww_scripts.setEnabled(False)
        self._act_ww_scripts.toggled.connect(self._on_toggle_ww_scripts)
        parent_menu.addAction(self._act_ww_scripts)

    def _on_toggle_spoken_enter(self, checked: bool) -> None:
        self.recorder.spoken_enter_enabled = checked
        self.config["spoken_enter_enabled"] = checked
        save_config(self.config)
        state = "aktiviert" if checked else "deaktiviert"
        self.notifier.notify("Sprachkommando", f"'Enter' als Taste {state}.")

    def _on_toggle_spoken_undo(self, checked: bool) -> None:
        self.recorder.spoken_undo_enabled = checked
        self.config["spoken_undo_enabled"] = checked
        save_config(self.config)
        state = "aktiviert" if checked else "deaktiviert"
        self.notifier.notify("Sprachkommando", f"'Undo' als Rueckgaengig {state}.")

    def _on_toggle_ww_scripts(self, checked: bool) -> None:
        was_running = self.ww_listener.running
        self.wake_word_script_action_executor.enabled = checked
        self.config["wake_word_script_actions_enabled"] = checked
        self.ww_listener.model_names = self._configured_wake_word_models()
        save_config(self.config)
        if was_running:
            self.ww_listener.stop()
            self.ww_listener.start()
        state = "aktiviert" if checked else "deaktiviert"
        self.notifier.notify("Wake-Word-Skripte", f"Wake-Word-Skripte {state}.")
        print(
            f"[wakeword] wake-word scripts {state}; active_models={self.ww_listener.model_names}",
            flush=True,
        )

    def _build_settings_action(self, parent_menu: QMenu) -> None:
        act_settings = self._keep_qt_ref(QAction("Einstellungen…", parent_menu))
        act_settings.triggered.connect(self._on_show_settings)
        parent_menu.addAction(act_settings)

    def _on_show_settings(self) -> None:
        result = show_settings_dialog(
            config=self.config,
            silence_timeout_ms=self.silence_timeout_ms,
            max_initial_wait_ms=self.max_initial_wait_ms,
            notify_timeout_ms=self.notify_timeout_ms,
            spoken_text_actions=self.config.get("spoken_text_actions", []),
            wake_word_script_actions=self.config.get("wake_word_script_actions", []),
            ww_models=self._ww_models,
            notifier=self.notifier,
        )
        if result is not None:
            self._apply_settings(result)

    def _apply_settings(self, result: dict) -> None:
        self.silence_timeout_ms = result["silence_timeout_ms"]
        self.max_initial_wait_ms = result["max_initial_wait_ms"]
        self.notify_timeout_ms = result["notify_timeout_ms"]
        self.notifier.timeout_ms = self.notify_timeout_ms

        new_ww_enabled = result["wake_word_enabled"]
        new_ww_model = result["wake_word_model"]
        previous_ww_model = self.ww_listener.model_name
        previous_model_names = list(self.ww_listener.model_names)

        self.recorder.beam_size = result["beam_size"]
        self.recorder.best_of = result["best_of"]
        self.recorder.temperature = result["temperature"]

        self.config.update(
            {
                "silence_timeout_ms": self.silence_timeout_ms,
                "max_initial_wait_ms": self.max_initial_wait_ms,
                "notify_timeout_ms": self.notify_timeout_ms,
                "spoken_text_actions": result["spoken_text_actions"],
                "wake_word_script_actions": result["wake_word_script_actions"],
                "wake_word_enabled": new_ww_enabled,
                "wake_word_model": new_ww_model,
                "beam_size": result["beam_size"],
                "best_of": result["best_of"],
                "temperature": result["temperature"],
            }
        )
        save_config(self.config)

        self.ww_listener.model_name = new_ww_model
        self.ww_listener.model_names = self._configured_wake_word_models()
        self._refresh_ww_toggle_label(new_ww_model)

        self.recorder.spoken_text_action_executor.set_actions(
            load_spoken_text_actions(result["spoken_text_actions"])
        )
        self.wake_word_script_action_map.clear()
        self.wake_word_script_action_map.update(
            load_wake_word_script_actions(result["wake_word_script_actions"])
        )
        self.wake_word_script_action_executor.set_actions(self.wake_word_script_action_map)

        self._act_ww_toggle.blockSignals(True)
        self._act_ww_toggle.setChecked(new_ww_enabled)
        self._act_ww_toggle.blockSignals(False)

        self._act_ww_scripts.blockSignals(True)
        self._act_ww_scripts.setEnabled(self.wake_word_script_action_executor.has_actions)
        if self.wake_word_script_action_executor.has_actions:
            self._act_ww_scripts.setChecked(
                self.config.get("wake_word_script_actions_enabled", True)
            )
        else:
            self._act_ww_scripts.setChecked(False)
        self._act_ww_scripts.blockSignals(False)

        if new_ww_enabled and not self.ww_listener.running:
            self.ww_listener.start()
        elif not new_ww_enabled and self.ww_listener.running:
            self.ww_listener.stop()
        elif self.ww_listener.running and (
            new_ww_model != previous_ww_model
            or self.ww_listener.model_names != previous_model_names
        ):
            self.ww_listener.stop()
            self.ww_listener.start()

        self.notifier.notify("Einstellungen", "Einstellungen gespeichert.")

    def _build_autostart_action(self, parent_menu: QMenu) -> None:
        if not autostart.is_supported():
            return
        act_autostart = self._keep_qt_ref(QAction("Beim Anmelden starten", parent_menu))
        act_autostart.setCheckable(True)
        act_autostart.setChecked(autostart.is_enabled())
        act_autostart.toggled.connect(
            lambda checked: self._on_toggle_autostart(act_autostart, checked)
        )
        parent_menu.addAction(act_autostart)

    def _on_toggle_autostart(self, action: QAction, checked: bool) -> None:
        try:
            autostart.set_enabled(checked)
            state = "aktiviert" if checked else "deaktiviert"
            self.notifier.notify("Autostart", f"Autostart {state}.")
        except Exception as exc:
            action.blockSignals(True)
            action.setChecked(not checked)
            action.blockSignals(False)
            self.notifier.notify("Autostart-Fehler", "Autostart konnte nicht geaendert werden.")
            print(f"Autostart konnte nicht geaendert werden: {exc}")

    def _build_log_action(self, parent_menu: QMenu) -> None:
        act_logs = self._keep_qt_ref(QAction("Logs anzeigen…", parent_menu))
        act_logs.triggered.connect(lambda: show_log_dialog(self.log_path))
        parent_menu.addAction(act_logs)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Show the tray icon and start the Qt event loop."""
        self.tray.show()
        tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
        print("Tray-Icon verfuegbar." if tray_ok else "Fehler: Tray-Icon nicht verfuegbar.")
        cfg = self.config.get("hotkey", _DEFAULT_HOTKEY)
        print(f"Live-Diktat bereit ({hotkey_label(cfg)} oder ueber das Tray-Menue starten).")
        sys.exit(self.app.exec_())
