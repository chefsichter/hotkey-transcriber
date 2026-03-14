"""
Log Dialog - Qt5 dialog for displaying the application log tail.

Usage:
    from hotkey_transcriber.gui.log_dialog import show_log_dialog

    show_log_dialog(log_path)
"""

from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from hotkey_transcriber.app_log_capture import read_log_tail


def show_log_dialog(log_path) -> None:
    """Open a read-only dialog showing the current application log tail."""
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

    def _reload() -> None:
        editor.setPlainText(read_log_tail(log_path))
        editor.moveCursor(QTextCursor.End)

    refresh_btn.clicked.connect(_reload)
    buttons.rejected.connect(dialog.reject)
    _reload()
    dialog.exec_()
