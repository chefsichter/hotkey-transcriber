"""
Settings Dialog - Qt5 dialog for configuring timing, wake word, and script actions.

Usage:
    from hotkey_transcriber.gui.settings_dialog import show_settings_dialog

    result = show_settings_dialog(config, ...)
    if result:
        apply_settings(result)
"""

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from hotkey_transcriber.builtin_scripts import list_builtin_scripts
from hotkey_transcriber.gui.action_settings_ui_rows import (
    create_spoken_text_script_row,
    create_wake_word_script_row,
    serialize_spoken_text_script_rows,
    serialize_wake_word_script_rows,
)


def show_settings_dialog(
    config: dict,
    silence_timeout_ms: int,
    max_initial_wait_ms: int,
    notify_timeout_ms: int,
    spoken_text_actions: list,
    wake_word_script_actions: list,
    ww_models: list[str],
    notifier,
) -> dict | None:
    """Show the settings dialog. Returns a dict with updated values on OK, or None if cancelled."""
    dlg = QDialog()
    dlg.setWindowTitle("Einstellungen")
    main_layout = QVBoxLayout(dlg)

    builtin_scripts = list_builtin_scripts()

    # ── Aufnahme ──────────────────────────────────────────────────────────────
    grp_aufnahme = QGroupBox("Aufnahme", dlg)
    aufnahme_form = QFormLayout(grp_aufnahme)

    sp_silence = QSpinBox(grp_aufnahme)
    sp_silence.setRange(500, 10000)
    sp_silence.setSuffix(" ms")
    sp_silence.setSingleStep(100)
    sp_silence.setValue(silence_timeout_ms)
    sp_silence.setToolTip("Wie lange Stille nach erkannter Sprache abgewartet wird, bevor die Aufnahme automatisch stoppt.")
    aufnahme_form.addRow("Stille bis Auto-Stop:", sp_silence)

    sp_initial_wait = QSpinBox(grp_aufnahme)
    sp_initial_wait.setRange(0, 10000)
    sp_initial_wait.setSuffix(" ms")
    sp_initial_wait.setSingleStep(100)
    sp_initial_wait.setSpecialValueText("deaktiviert")
    sp_initial_wait.setValue(max_initial_wait_ms)
    sp_initial_wait.setToolTip("Maximale Wartezeit auf das erste Sprachsignal. Danach stoppt die Aufnahme automatisch.\n0 = deaktiviert.")
    aufnahme_form.addRow("Max. Anfangswarten:", sp_initial_wait)

    sp_notify = QSpinBox(grp_aufnahme)
    sp_notify.setRange(200, 10000)
    sp_notify.setSuffix(" ms")
    sp_notify.setSingleStep(100)
    sp_notify.setValue(notify_timeout_ms)
    sp_notify.setToolTip("Wie lange Tray-Benachrichtigungen eingeblendet bleiben.")
    aufnahme_form.addRow("Benachrichtigungsdauer:", sp_notify)

    main_layout.addWidget(grp_aufnahme)

    # ── Inferenz ──────────────────────────────────────────────────────────────
    grp_inf = QGroupBox("Inferenz", dlg)
    inf_form = QFormLayout(grp_inf)

    preset_widget = QWidget(grp_inf)
    preset_layout = QHBoxLayout(preset_widget)
    preset_layout.setContentsMargins(0, 0, 0, 0)
    btn_schnell    = QPushButton("Schnell",    preset_widget)
    btn_ausgewogen = QPushButton("Ausgewogen", preset_widget)
    btn_genau      = QPushButton("Genau",      preset_widget)
    btn_standard   = QPushButton("Standard",   preset_widget)
    for b in (btn_schnell, btn_ausgewogen, btn_genau, btn_standard):
        preset_layout.addWidget(b)
    inf_form.addRow("Preset:", preset_widget)

    sp_beam = QSpinBox(grp_inf)
    sp_beam.setRange(1, 8)
    sp_beam.setValue(config.get("beam_size", 1))
    sp_beam.setToolTip(
        "Wie viele parallele Kandidaten Whisper verfolgt.\n"
        "1 = greedy (schnellst), 5 = maximale Genauigkeit."
    )
    inf_form.addRow("Beam Size:", sp_beam)

    sp_best_of = QSpinBox(grp_inf)
    sp_best_of.setRange(1, 8)
    sp_best_of.setValue(config.get("best_of", 1))
    sp_best_of.setToolTip(
        "Wie viele zufällige Samples verglichen werden.\n"
        "Nur sinnvoll wenn Temperature > 0."
    )
    inf_form.addRow("Best-of:", sp_best_of)

    sp_temp = QDoubleSpinBox(grp_inf)
    sp_temp.setRange(0.0, 1.0)
    sp_temp.setSingleStep(0.1)
    sp_temp.setDecimals(1)
    sp_temp.setValue(config.get("temperature", 0.0))
    sp_temp.setToolTip(
        "0.0 = deterministisch (empfohlen).\n"
        "> 0 = zufälliges Sampling, kann bei schlechtem Audio helfen,\n"
        "aber auch Halluzinationen erzeugen."
    )
    inf_form.addRow("Temperature:", sp_temp)

    def _update_best_of_state() -> None:
        enabled = sp_temp.value() > 0
        sp_best_of.setEnabled(enabled)
        if not enabled:
            sp_best_of.setValue(1)

    _update_best_of_state()
    sp_temp.valueChanged.connect(lambda _: _update_best_of_state())

    def _apply_inf_preset(beam: int, best: int, temp: float) -> None:
        sp_beam.setValue(beam)
        sp_temp.setValue(temp)
        sp_best_of.setValue(best)
        _update_best_of_state()

    btn_schnell.clicked.connect(   lambda: _apply_inf_preset(1, 1, 0.0))
    btn_ausgewogen.clicked.connect(lambda: _apply_inf_preset(2, 1, 0.0))
    btn_genau.clicked.connect(     lambda: _apply_inf_preset(5, 5, 0.4))
    btn_standard.clicked.connect(  lambda: _apply_inf_preset(1, 1, 0.0))

    main_layout.addWidget(grp_inf)

    # ── Wake Word ─────────────────────────────────────────────────────────────
    grp_ww = QGroupBox("Wake Word", dlg)
    ww_form = QFormLayout(grp_ww)

    cb_ww = QCheckBox("Aktiviert", grp_ww)
    cb_ww.setChecked(config.get("wake_word_enabled", False))
    ww_form.addRow("Wake Word:", cb_ww)

    combo_ww = QComboBox(grp_ww)
    combo_ww.addItems(ww_models)
    current_model = config.get("wake_word_model", "hey jarvis")
    idx = combo_ww.findText(current_model)
    if idx >= 0:
        combo_ww.setCurrentIndex(idx)
    else:
        combo_ww.addItem(current_model)
        combo_ww.setCurrentText(current_model)
    ww_form.addRow("Modell:", combo_ww)

    wake_word_script_rows, wake_word_scripts_widget = _build_ww_rows_widget(
        grp_ww, wake_word_script_actions, ww_models, builtin_scripts
    )
    ww_form.addRow("Skripte:", wake_word_scripts_widget)

    main_layout.addWidget(grp_ww)

    # ── Text-Aktionen ─────────────────────────────────────────────────────────
    grp_text = QGroupBox("Text-Aktionen", dlg)
    text_form = QFormLayout(grp_text)

    spoken_text_script_rows, spoken_text_scripts_widget = _build_script_rows_widget(
        grp_text, spoken_text_actions, _add_spoken_text_row_fn=lambda w, rows, layout: (
            lambda initial=None: _append_spoken_text_row(w, rows, layout, builtin_scripts, initial)
        )
    )
    text_form.addRow("Text-Skripte:", spoken_text_scripts_widget)

    main_layout.addWidget(grp_text)

    # ── Buttons ───────────────────────────────────────────────────────────────
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg)
    main_layout.addWidget(buttons)

    parsed_actions: dict = {}

    def _accept() -> None:
        try:
            parsed_actions["spoken_text_actions"] = serialize_spoken_text_script_rows(
                spoken_text_script_rows
            )
            parsed_actions["wake_word_script_actions"] = serialize_wake_word_script_rows(
                wake_word_script_rows
            )
        except ValueError as exc:
            notifier.notify("Einstellungsfehler", str(exc))
            return
        dlg.accept()

    buttons.accepted.connect(_accept)
    buttons.rejected.connect(dlg.reject)

    if dlg.exec_() != QDialog.Accepted:
        return None

    return {
        "silence_timeout_ms": sp_silence.value(),
        "max_initial_wait_ms": sp_initial_wait.value(),
        "notify_timeout_ms": sp_notify.value(),
        "wake_word_enabled": cb_ww.isChecked(),
        "wake_word_model": combo_ww.currentText(),
        "spoken_text_actions": parsed_actions["spoken_text_actions"],
        "wake_word_script_actions": parsed_actions["wake_word_script_actions"],
        "beam_size": sp_beam.value(),
        "best_of": sp_best_of.value(),
        "temperature": sp_temp.value(),
    }


def _append_spoken_text_row(
    parent_widget, rows: list, layout: QVBoxLayout, builtin_scripts: list, initial=None
) -> None:
    row = create_spoken_text_script_row(parent_widget, builtin_scripts, initial=initial)
    rows.append(row)
    layout.addWidget(row["widget"])
    row["remove"].clicked.connect(lambda: _remove_row(rows, row))


def _append_ww_row(
    parent_widget, rows: list, layout: QVBoxLayout, ww_models: list, builtin_scripts: list,
    initial=None,
) -> None:
    row = create_wake_word_script_row(parent_widget, ww_models, builtin_scripts, initial=initial)
    rows.append(row)
    layout.addWidget(row["widget"])
    row["remove"].clicked.connect(lambda: _remove_row(rows, row))


def _remove_row(rows: list, row: dict) -> None:
    rows.remove(row)
    row["widget"].deleteLater()


def _build_script_rows_widget(dlg, initial_entries, **_):
    """Build the spoken-text-script rows widget with add button."""
    builtin_scripts = list_builtin_scripts()
    rows: list = []
    widget = QWidget(dlg)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)

    for entry in initial_entries:
        _append_spoken_text_row(widget, rows, layout, builtin_scripts, entry)

    btn = QPushButton("Text-Skript hinzufügen", dlg)
    btn.clicked.connect(lambda: _append_spoken_text_row(widget, rows, layout, builtin_scripts))
    layout.addWidget(btn)

    return rows, widget


def _build_ww_rows_widget(dlg, initial_entries, ww_models, builtin_scripts):
    """Build the wake-word-script rows widget with add button."""
    rows: list = []
    widget = QWidget(dlg)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)

    for entry in initial_entries:
        _append_ww_row(widget, rows, layout, ww_models, builtin_scripts, entry)

    btn = QPushButton("Wake-Word-Skript hinzufügen", dlg)
    btn.clicked.connect(lambda: _append_ww_row(widget, rows, layout, ww_models, builtin_scripts))
    layout.addWidget(btn)

    return rows, widget
