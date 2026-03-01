import threading
import keyboard


class KeyBoardListener:
    """
    Fangt Alt+R ab und ruft start_callback() beim Drücken
    und stop_callback() beim Loslassen auf.
    Alt+R-Events werden auf OS-Ebene unterdrückt (kein 'r' im Textfeld).
    """

    def __init__(self, start_callback, stop_callback):
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.recording = False
        self._hook = None

    def _on_event(self, event):
        if event.name != 'r':
            return
        if not (keyboard.is_pressed('alt') or keyboard.is_pressed('right alt')):
            return

        if event.event_type == keyboard.KEY_DOWN and not self.recording:
            self.recording = True
            threading.Thread(target=self.start_callback, daemon=True).start()
        elif event.event_type == keyboard.KEY_UP and self.recording:
            self.recording = False
            threading.Thread(target=self.stop_callback, daemon=True).start()

        # False → Event wird NICHT ans aktive Fenster weitergeleitet
        return False

    def start(self):
        self._hook = keyboard.hook(self._on_event)

    def stop(self):
        if self._hook:
            keyboard.unhook(self._hook)
            self._hook = None
