import itertools
import threading
import time

from faster_whisper import WhisperModel
from .keyboard_controller import KeyboardController
from .speech_recorder import SpeechRecorder
from .keyboard_listener import KeyBoardListener


def _spinner(message, stop_event):
    # Simple CLI spinner for loading feedback
    for char in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set():
            break
        print(f"{char} {message}", end='\r', flush=True)
        time.sleep(0.1)
    # Clear the line after done
    print(' ' * (len(message) + 2), end='\r', flush=True)

def load_model(size, device, compute_type):
    message = f"Lade Whisper-Modell mit Grösse '{size.capitalize()}' auf '{device}'…"
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=_spinner, args=(message, stop_event), daemon=True
    )
    spinner_thread.start()
    model = WhisperModel(size, device=device, compute_type=compute_type)
    stop_event.set()
    spinner_thread.join()
    print(f"✅  Whisper-Modell mit Grösse '{size.capitalize()}' bereit.", flush=True)
    return model
 
def load_speech_recorder(model, wait_on_keyboard, channels, chunk_ms, interval, language, rec_mark):
    """
    Load SpeechRecorder with CLI spinner feedback.
    Returns a SpeechRecorder instance.
    """
    message = "Lade SpeechRecorder…"
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=_spinner, args=(message, stop_event), daemon=True
    )
    spinner_thread.start()
    keyboard_controller = KeyboardController(wait=wait_on_keyboard)
    recorder = SpeechRecorder(
        model=model,
        keyboard_controller=keyboard_controller,
        channels=channels,
        chunk_ms=chunk_ms,
        interval=interval,
        language=language,
        rec_mark=rec_mark
    )
    stop_event.set()
    spinner_thread.join()
    print("✅  SpeechRecorder bereit.", flush=True)
    return recorder

def load_keyboard_listener(recorder):
    """
    Load KeyBoardListener with CLI spinner feedback.
    Returns a KeyBoardListener instance.
    """
    message = "Lade KeyBoardListener…"
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=_spinner, args=(message, stop_event), daemon=True
    )
    spinner_thread.start()
    hotkey = KeyBoardListener(
        start_callback=recorder.start,
        stop_callback=recorder.stop
    )
    hotkey.start()
    stop_event.set()
    spinner_thread.join()
    print("✅  KeyBoardListener bereit.", flush=True)
    return hotkey