"""
Tray Notifications - Cross-platform desktop notification backend.

On Linux: uses gdbus (freedesktop.org Notifications) with notify-send fallback.
On Windows/macOS: uses QSystemTrayIcon.showMessage via a thread-safe Qt signal.

Usage:
    from hotkey_transcriber.gui.tray_notifications import TrayNotifier

    notifier = TrayNotifier(tray, timeout_ms=1500, icon_path="/path/to/icon.png")
    notifier.notify("Title", "Message")
"""

import sys
import threading

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QSystemTrayIcon


class TrayNotifier:
    """Send desktop notifications from any thread, on Linux and Windows."""

    def __init__(self, tray: QSystemTrayIcon, timeout_ms: int, icon_path: str) -> None:
        self.timeout_ms = timeout_ms
        self._tray = tray
        self._icon_path = icon_path
        if sys.platform == "linux":
            self._last_notify_id: list[int] = [0]
            self._notify_impl = self._notify_linux
        else:
            self._signals = _TraySignals()
            self._signals.show_message.connect(
                lambda title, msg, icon_type, ms: tray.showMessage(title, msg, icon_type, ms)
            )
            self._notify_impl = self._notify_qt

    def notify(
        self,
        title: str,
        msg: str,
        icon_type: int = QSystemTrayIcon.Information,
        ms: int = 0,
    ) -> None:
        """Show a desktop notification. Uses timeout_ms if ms is 0."""
        if ms <= 0:
            ms = self.timeout_ms
        self._notify_impl(title, msg, icon_type, ms)

    def _notify_linux(self, title: str, msg: str, icon_type: int, ms: int) -> None:
        import subprocess as sp

        try:
            proc = sp.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.freedesktop.Notifications",
                    "--object-path", "/org/freedesktop/Notifications",
                    "--method", "org.freedesktop.Notifications.Notify",
                    "Hotkey Transcriber",
                    str(self._last_notify_id[0]),
                    self._icon_path,
                    title, msg,
                    "[]", "{}",
                    str(ms),
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            out = proc.stdout.strip()
            if out.startswith("(uint32 "):
                nid = int(out.split()[1].rstrip(",)"))
                self._last_notify_id[0] = nid
                threading.Timer(ms / 1000.0, self._close_linux_notification, args=(nid,)).start()
        except (FileNotFoundError, sp.TimeoutExpired):
            self._notify_linux_fallback(title, msg, ms)

    def _close_linux_notification(self, nid: int) -> None:
        import subprocess as sp

        try:
            sp.Popen(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.freedesktop.Notifications",
                    "--object-path", "/org/freedesktop/Notifications",
                    "--method", "org.freedesktop.Notifications.CloseNotification",
                    str(nid),
                ],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )
        except FileNotFoundError:
            pass

    def _notify_linux_fallback(self, title: str, msg: str, ms: int) -> None:
        import subprocess as sp

        try:
            sp.Popen(
                [
                    "notify-send", "-t", str(ms), "-i", self._icon_path,
                    "--app-name", "Hotkey Transcriber",
                    title, msg,
                ],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )
        except FileNotFoundError:
            pass

    def _notify_qt(self, title: str, msg: str, icon_type: int, ms: int) -> None:
        self._signals.show_message.emit(title, msg, icon_type, ms)


class _TraySignals(QObject):
    show_message = pyqtSignal(str, str, int, int)
