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
    QFormLayout,
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
    form = QFormLayout(dlg)

    sp_silence = QSpinBox(dlg)
    sp_silence.setRange(500, 10000)
    sp_silence.setSuffix(" ms")
    sp_silence.setSingleStep(100)
    sp_silence.setValue(silence_timeout_ms)
    form.addRow("Stille bis Auto-Stop:", sp_silence)

    sp_initial_wait = QSpinBox(dlg)
    sp_initial_wait.setRange(0, 10000)
    sp_initial_wait.setSuffix(" ms")
    sp_initial_wait.setSingleStep(100)
    sp_initial_wait.setSpecialValueText("deaktiviert")
    sp_initial_wait.setValue(max_initial_wait_ms)
    form.addRow("Max. Anfangswarten:", sp_initial_wait)

    sp_notify = QSpinBox(dlg)
    sp_notify.setRange(200, 10000)
    sp_notify.setSuffix(" ms")
    sp_notify.setSingleStep(100)
    sp_notify.setValue(notify_timeout_ms)
    form.addRow("Benachrichtigungsdauer:", sp_notify)

    cb_ww = QCheckBox("Aktiviert", dlg)
    cb_ww.setChecked(config.get("wake_word_enabled", False))
    form.addRow("Wake Word:", cb_ww)

    combo_ww = QComboBox(dlg)
    combo_ww.addItems(ww_models)
    current_model = config.get("wake_word_model", "hey jarvis")
    idx = combo_ww.findText(current_model)
    if idx >= 0:
        combo_ww.setCurrentIndex(idx)
    else:
        combo_ww.addItem(current_model)
        combo_ww.setCurrentText(current_model)
    form.addRow("Wake-Word Modell:", combo_ww)

    builtin_scripts = list_builtin_scripts()
    spoken_text_script_rows, spoken_text_scripts_widget = _build_script_rows_widget(
        dlg, spoken_text_actions, _add_spoken_text_row_fn=lambda w, rows, layout: (
            lambda initial=None: _append_spoken_text_row(w, rows, layout, builtin_scripts, initial)
        )
    )
    form.addRow("Text-Skripte:", spoken_text_scripts_widget)

    wake_word_script_rows, wake_word_scripts_widget = _build_ww_rows_widget(
        dlg, wake_word_script_actions, ww_models, builtin_scripts
    )
    form.addRow("Wake-Word-Skripte:", wake_word_scripts_widget)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg)
    form.addRow(buttons)

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
