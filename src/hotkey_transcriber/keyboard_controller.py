import sys
import types

# -----------------------------------------------------------
# Inject MouseInfo stub before pyautogui import.
mouseinfo_stub = types.ModuleType("mouseinfo")
mouseinfo_stub.MouseInfoWindow = lambda *args, **kw: None
sys.modules["mouseinfo"] = mouseinfo_stub
# -----------------------------------------------------------

import os

os.environ["PYAUTOGUI_FAILSAFE"] = "True"

import pyautogui
import pyperclip
import threading
import time


def _safe_print(text="", end="\n", flush=False):
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe = str(text).encode(enc, errors="replace").decode(enc, errors="replace")
    print(safe, end=end, flush=flush)


class KeyboardController:
    """
    Wraps undo/paste logic with clipboard restore and internal lock.
    """

    def __init__(self, wait: float = 0.02):
        self.wait = wait
        self.clipboard_content = None
        self.lock = threading.Lock()

    def undo(self):
        """Send Ctrl+Z."""
        with self.lock:
            pyautogui.hotkey("ctrl", "z")
            time.sleep(self.wait)

    def backspace(self, n_times=1):
        """Send Backspace n times."""
        with self.lock:
            pyautogui.press("backspace", presses=n_times, interval=0)

    def paste(self, text: str, end="\n"):
        """
        Put text into clipboard, press Ctrl+V, then keep clipboard behavior stable.
        """
        with self.lock:
            _safe_print(text, end=end, flush=True)
            pyperclip.copy(text)
            time.sleep(self.wait)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(self.wait)

    def write(self, text: str, end="\n", interval=None):
        if interval is None:
            interval = self.wait
        with self.lock:
            _safe_print(text, end=end, flush=True)
            pyautogui.write(text, interval=interval)

    def save_clipboard(self):
        """Store current clipboard content."""
        with self.lock:
            self.clipboard_content = pyperclip.paste()
            time.sleep(self.wait)
            _safe_print("💾 Clipboard gespeichert.")

    def load_clipboard(self):
        """Restore previous clipboard content."""
        with self.lock:
            pyperclip.copy(self.clipboard_content)
            _safe_print("📤 Clipboard wieder geladen.")
