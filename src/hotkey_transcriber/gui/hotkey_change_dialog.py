"""
Hotkey Change Dialog - Qt5 dialog for capturing a new keyboard shortcut from the user.

Architecture:
    ┌─────────────────────────────────────────┐
    │  HotkeyChangeDialog                     │
    │  ┌───────────────────────────────────┐  │
    │  │  show_hotkey_dialog()             │  │
    │  │  → QKeySequenceEdit input         │  │
    │  │  → validates modifier presence    │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  hotkey_label() / tray_tooltip()  │  │
    │  │  → formats dict → display string  │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.gui.hotkey_change_dialog import show_hotkey_dialog, hotkey_label

    result = show_hotkey_dialog()  # returns {"modifier": "alt", "key": "r"} or None
    label = hotkey_label(result)   # returns "Alt+R"
"""


def show_hotkey_dialog(parent=None) -> dict | None:
    """Open a dialog to capture a new hotkey combination.

    Returns a dict {"modifier": ..., "key": ...} on OK, or None on cancel.
    Only accepts combinations that include at least one of Alt/Ctrl/Shift
    (rejects naked keys to avoid clobbering normal typing).
    """
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeySequence
    from PyQt5.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QKeySequenceEdit,
        QLabel,
        QVBoxLayout,
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
    _ALL_MODS = (
        int(Qt.ShiftModifier) | int(Qt.ControlModifier) | int(Qt.AltModifier) | int(Qt.MetaModifier)
    )
    key_int = combo & ~_ALL_MODS
    mod_int = combo & (int(Qt.ShiftModifier) | int(Qt.ControlModifier) | int(Qt.AltModifier))

    if not mod_int:
        return None  # no modifier - reject

    parts = []
    for qt_mod, name in [
        (int(Qt.ShiftModifier), "shift"),
        (int(Qt.ControlModifier), "ctrl"),
        (int(Qt.AltModifier), "alt"),
    ]:
        if mod_int & qt_mod:
            parts.append(name)
    modifier_str = "+".join(parts)

    key_str = QKeySequence(key_int).toString().lower()
    if not key_str:
        return None

    return {"modifier": modifier_str, "key": key_str}


def hotkey_label(cfg: dict) -> str:
    """Format a hotkey config dict as a human-readable string like 'Alt+R'."""
    mod = cfg.get("modifier", "alt").title()
    key = cfg.get("key", "r").upper()
    return f"{mod}+{key}"


def build_tray_tooltip(hotkey_cfg: dict, app_label: str = "Live-Diktat") -> str:
    """Build the system tray tooltip string including the current hotkey."""
    return f"{app_label} | Hotkey: {hotkey_label(hotkey_cfg)}"
