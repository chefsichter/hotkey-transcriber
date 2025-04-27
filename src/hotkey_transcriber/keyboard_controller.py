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
        self.lock = threading.Lock()

    def undo(self):
        """Sendet Ctrl+Z (mit Alt-Up davor), um den REC-Marker o.ä. zu entfernen."""
        with self.lock:
            pyautogui.keyUp("altleft")
            time.sleep(self.wait)
            pyautogui.hotkey("ctrl", "z")
            time.sleep(self.wait)

    def paste(self, text: str):
        """
        Kopiert `text` in die Zwischenablage, führt Ctrl+V (mit Alt-Up) aus
        und stellt danach die alte Zwischenablage wieder her.
        """
        with self.lock:
            old_clip = pyperclip.paste()
            pyperclip.copy(text)
            time.sleep(self.wait)
            pyautogui.keyUp("altleft")
            time.sleep(self.wait)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(self.wait)
            pyperclip.copy(old_clip)
            time.sleep(self.wait)

