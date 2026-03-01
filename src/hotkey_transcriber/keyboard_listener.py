import threading
import keyboard


class KeyBoardListener:
    """
    Fangt Alt+R ab und ruft start_callback() beim Drücken
    und stop_callback() beim Loslassen auf.
    'r'-Events werden während der Aufnahme auf OS-Ebene unterdrückt.
    """

    def __init__(self, start_callback, stop_callback):
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.recording = False
        self._alt_held = False
        self._hook = None

    def _on_event(self, event):
        # Alt-Zustand selbst tracken – zuverlässiger als keyboard.is_pressed() im Callback
        if 'alt' in event.name:
            self._alt_held = (event.event_type == keyboard.KEY_DOWN)
            return

        if event.name != 'r':
            return

        if event.event_type == keyboard.KEY_DOWN:
            if self._alt_held and not self.recording:
                self.recording = True
                threading.Thread(target=self.start_callback, daemon=True).start()
            # Während Aufnahme: 'r' (inkl. Auto-Repeat) NICHT ans Textfeld weiterleiten
            if self.recording:
                return False

        elif event.event_type == keyboard.KEY_UP and self.recording:
            self.recording = False
            threading.Thread(target=self.stop_callback, daemon=True).start()
            return False

    def start(self):
        self._hook = keyboard.hook(self._on_event)

    def stop(self):
        if self._hook:
            keyboard.unhook(self._hook)
            self._hook = None
