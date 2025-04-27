# keyboard_listener.py
from pynput import keyboard

class KeyBoardListener:
    """
    Fangt Alt+R ab und ruft start_callback() beim Drücken
    und stop_callback() beim Loslassen von 'r' auf.
    """
    ALT_KEYS = {
        keyboard.Key.alt,
        keyboard.Key.alt_l,
        keyboard.Key.alt_r,
        keyboard.Key.alt_gr,
    }

    def __init__(self, start_callback, stop_callback):
        self.start_callback = start_callback
        self.stop_callback  = stop_callback
        self.alt_pressed    = False
        self.r_pressed      = False
        self.alt_down = False
        self.recording = False

        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            daemon=True,
        )

    def _on_press(self, key):
        if key in self.ALT_KEYS:
            self.alt_down = True
            return

        if getattr(key, "char", None) == "r" and self.alt_down and not self.recording:
            self.start_callback()
            self.recording = True

    def _on_release(self, key):
        if getattr(key, "char", None) == "r":
            if self.recording:
                self.stop_callback()
                self.recording = False

        if key in self.ALT_KEYS:
            self.alt_down = False

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()
