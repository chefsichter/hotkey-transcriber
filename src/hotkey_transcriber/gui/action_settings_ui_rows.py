"""
Action Settings UI Rows - Build and serialize PyQt5 row widgets for configuring
text/wake-word script actions.

Architecture:
    ┌─────────────────────────────────────────┐
    │  ActionSettingsUIRows                   │
    │  ┌───────────────────────────────────┐  │
    │  │  create_wake_word_script_row()    │  │
    │  │  → QWidget row: model/mode/cmd    │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  create_spoken_text_script_row()  │  │
    │  │  → QWidget row: trigger/mode/cmd  │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  serialize_*_rows()               │  │
    │  │  → list of dicts for config.json  │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.gui.action_settings_ui_rows import (
        create_spoken_text_script_row,
        create_wake_word_script_row,
        serialize_spoken_text_script_rows,
        serialize_wake_word_script_rows,
    )
"""

from pathlib import Path


def _browse_script_path(parent) -> str:
    from PyQt5.QtWidgets import QFileDialog

    path, _ = QFileDialog.getOpenFileName(
        parent,
        "Shell-Skript auswählen",
        str(Path.home()),
        "Shell-Skripte (*.sh);;Alle Dateien (*)",
    )
    return path


def _sync_mode_widgets(mode, builtin, command, browse) -> None:
    is_builtin = mode.currentText() == "Built-in"
    builtin.setEnabled(is_builtin)
    command.setEnabled(not is_builtin)
    browse.setEnabled(not is_builtin)


def create_wake_word_script_row(
    parent, wake_word_models: list[str], builtin_scripts: list[str], initial=None
) -> dict:
    """Create a Qt5 row widget for configuring a wake-word-triggered script action."""
    from PyQt5.QtWidgets import (
        QCheckBox,
        QComboBox,
        QHBoxLayout,
        QLineEdit,
        QPushButton,
        QWidget,
    )

    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    wake_word = QComboBox(row)
    wake_word.setEditable(True)
    wake_word.addItems(wake_word_models)
    wake_word.setMinimumWidth(150)

    mode = QComboBox(row)
    mode.addItems(["Built-in", "Shell-Skript"])

    builtin = QComboBox(row)
    builtin.addItems(builtin_scripts)
    builtin.setMinimumWidth(180)

    command = QLineEdit(row)
    command.setPlaceholderText("/pfad/zum/script.sh")
    browse = QPushButton("…", row)
    browse.setFixedWidth(32)
    start_recording = QCheckBox("Aufnahme danach", row)
    start_recording.setChecked(True)
    remove = QPushButton("Entfernen", row)

    for widget in (wake_word, mode, builtin, command, browse, start_recording, remove):
        layout.addWidget(widget)

    mode.currentTextChanged.connect(
        lambda _text: _sync_mode_widgets(mode, builtin, command, browse)
    )
    browse.clicked.connect(lambda: command.setText(_browse_script_path(row) or command.text()))

    initial = initial or {}
    wake_word.setCurrentText(str(initial.get("wake_word_model", "")))
    builtin_name = str(initial.get("builtin", "")).strip()
    command_text = str(initial.get("command", "")).strip()
    mode.setCurrentText("Shell-Skript" if command_text and not builtin_name else "Built-in")
    if builtin_name:
        builtin.setCurrentText(builtin_name)
    command.setText(command_text)
    start_recording.setChecked(bool(initial.get("start_recording_after", True)))
    _sync_mode_widgets(mode, builtin, command, browse)

    return {
        "widget": row,
        "wake_word": wake_word,
        "mode": mode,
        "builtin": builtin,
        "command": command,
        "browse": browse,
        "start_recording": start_recording,
        "remove": remove,
    }


def create_spoken_text_script_row(parent, builtin_scripts: list[str], initial=None) -> dict:
    """Create a Qt5 row widget for configuring a spoken-text-triggered script action."""
    from PyQt5.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QHBoxLayout,
        QLineEdit,
        QPushButton,
        QWidget,
    )

    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    trigger = QLineEdit(row)
    trigger.setPlaceholderText("Varianten, getrennt mit Komma")
    trigger.setMinimumWidth(220)

    mode = QComboBox(row)
    mode.addItems(["Built-in", "Shell-Skript"])
    builtin = QComboBox(row)
    builtin.addItems(builtin_scripts)
    builtin.setMinimumWidth(180)

    command = QLineEdit(row)
    command.setPlaceholderText("/pfad/zum/script.sh")
    browse = QPushButton("…", row)
    browse.setFixedWidth(32)
    paste_remainder = QCheckBox("Rest einfügen", row)
    paste_remainder.setChecked(True)

    fuzzy_threshold = QDoubleSpinBox(row)
    fuzzy_threshold.setRange(0.0, 1.0)
    fuzzy_threshold.setSingleStep(0.01)
    fuzzy_threshold.setDecimals(2)
    fuzzy_threshold.setPrefix("Fuzzy ")
    fuzzy_threshold.setValue(0.78)

    remove = QPushButton("Entfernen", row)
    for widget in (trigger, mode, builtin, command, browse, paste_remainder, fuzzy_threshold, remove):
        layout.addWidget(widget)

    mode.currentTextChanged.connect(
        lambda _text: _sync_mode_widgets(mode, builtin, command, browse)
    )
    browse.clicked.connect(lambda: command.setText(_browse_script_path(row) or command.text()))

    initial = initial or {}
    triggers = initial.get("triggers")
    if isinstance(triggers, list):
        trigger.setText(", ".join(str(item).strip() for item in triggers if str(item).strip()))
    else:
        trigger.setText(str(initial.get("trigger", "")))
    builtin_name = str(initial.get("builtin", "")).strip()
    command_text = str(initial.get("command", "")).strip()
    mode.setCurrentText("Shell-Skript" if command_text and not builtin_name else "Built-in")
    if builtin_name:
        builtin.setCurrentText(builtin_name)
    command.setText(command_text)
    paste_remainder.setChecked(bool(initial.get("paste_remainder", True)))
    fuzzy_threshold.setValue(float(initial.get("fuzzy_threshold", 0.78)))
    _sync_mode_widgets(mode, builtin, command, browse)

    return {
        "widget": row,
        "trigger": trigger,
        "mode": mode,
        "builtin": builtin,
        "command": command,
        "browse": browse,
        "paste_remainder": paste_remainder,
        "fuzzy_threshold": fuzzy_threshold,
        "remove": remove,
    }


def serialize_wake_word_script_rows(rows: list[dict]) -> list[dict]:
    """Serialize wake-word-script UI rows to a list of config dicts."""
    entries = []
    for row in rows:
        wake_word_model = row["wake_word"].currentText().strip()
        if not wake_word_model:
            continue
        entry: dict = {
            "wake_word_model": wake_word_model,
            "start_recording_after": row["start_recording"].isChecked(),
            "delay_ms": 1200,
        }
        if row["mode"].currentText() == "Built-in":
            builtin_name = row["builtin"].currentText().strip()
            if not builtin_name:
                raise ValueError("Wake-Word-Skripte: Built-in-Skript fehlt.")
            entry["builtin"] = builtin_name
        else:
            command_text = row["command"].text().strip()
            if not command_text:
                raise ValueError("Wake-Word-Skripte: Shell-Skript/Befehl fehlt.")
            entry["command"] = command_text
        entries.append(entry)
    return entries


def serialize_spoken_text_script_rows(rows: list[dict]) -> list[dict]:
    """Serialize spoken-text-script UI rows to a list of config dicts."""
    entries = []
    for row in rows:
        triggers = [part.strip() for part in row["trigger"].text().split(",") if part.strip()]
        if not triggers:
            continue
        entry: dict = {
            "triggers": triggers,
            "paste_remainder": row["paste_remainder"].isChecked(),
            "delay_ms": 1200,
            "fuzzy_threshold": row["fuzzy_threshold"].value(),
        }
        if row["mode"].currentText() == "Built-in":
            builtin_name = row["builtin"].currentText().strip()
            if not builtin_name:
                raise ValueError("Text-Skripte: Built-in-Skript fehlt.")
            entry["builtin"] = builtin_name
        else:
            command_text = row["command"].text().strip()
            if not command_text:
                raise ValueError("Text-Skripte: Shell-Skript/Befehl fehlt.")
            entry["command"] = command_text
        entries.append(entry)
    return entries
