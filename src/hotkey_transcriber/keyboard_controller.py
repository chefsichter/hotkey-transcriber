import sys, types
# -----------------------------------------------------------
#  MouseInfo-Stub einspritzen, **bevor** pyautogui importiert wird
mouseinfo_stub = types.ModuleType("mouseinfo")
mouseinfo_stub.MouseInfoWindow = lambda *args, **kw: None
sys.modules["mouseinfo"] = mouseinfo_stub
# -----------------------------------------------------------

import os
os.environ["PYAUTOGUI_FAILSAFE"] = "True"     # was du sonst noch brauchst
import pyautogui
import pyperclip, threading, time


class KeyboardController:
    """
    Kapselt Undo- (Ctrl+Z) und Paste-Logik inklusive Clipboard-Restore
    und Thread-Safety per internem Lock.
    """
    def __init__(self, wait: float = 0.02):
        self.wait = wait
        self.clipboard_content = None
        self.lock = threading.Lock()

    def undo(self):
        """Sendet Ctrl+Z (mit Alt-Up davor), um den REC-Marker o.ä. zu entfernen."""
        with self.lock:
            pyautogui.keyUp("altleft")
            time.sleep(self.wait)
            pyautogui.hotkey("ctrl", "z")
            time.sleep(self.wait)

    def backspace(self, n_times=1):
        """Sendet Backspace (mit Alt-Up davor), um den REC-Marker o.ä. zu entfernen."""
        with self.lock:
            pyautogui.press('backspace', presses=n_times, interval=0)

    def paste(self, text: str, end="\n"):
        """
        Kopiert `text` in die Zwischenablage, führt Ctrl+V (mit Alt-Up) aus
        und stellt danach die alte Zwischenablage wieder her.
        """
        with self.lock:
            print(text, end=end, flush=True)
            pyperclip.copy(text)
            time.sleep(self.wait)
            pyautogui.keyUp("altleft")
            time.sleep(self.wait)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(self.wait)
    
    def write(self, text: str, end="\n", interval=None):
        if interval is None:
            interval = self.wait
        with self.lock:
            print(text, end=end, flush=True)
            pyautogui.write(text, interval=interval)

    def save_clipboard(self):
        """Speichert den Inhalt der Zwischenablage."""
        with self.lock:
            self.clipboard_content = pyperclip.paste()
            time.sleep(self.wait)
            print(f"💾 Clipboard gespeichert.")

    def load_clipboard(self):
        """Lädt den Inhalt der Zwischenablage."""
        with self.lock:
            pyperclip.copy(self.clipboard_content)
            print("📤 Clipboard wieder geladen.")
