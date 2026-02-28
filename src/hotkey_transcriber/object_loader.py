import itertools
import threading
import time

from faster_whisper import WhisperModel, download_model
from huggingface_hub.errors import LocalEntryNotFoundError
from huggingface_hub.utils import HfHubHTTPError

from hotkey_transcriber.keyboard_controller import KeyboardController
from hotkey_transcriber.speech_recorder import SpeechRecorder
from hotkey_transcriber.keyboard_listener import KeyBoardListener
from hotkey_transcriber.wsl_backend import WslWhisperModel


def _spinner(message, stop_event):
    # Simple CLI spinner for loading feedback
    for char in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set():
            break
        print(f"{char} {message}", end='\r', flush=True)
        time.sleep(0.1)
    # Clear the line after done
    print(' ' * (len(message) + 2), end='\r', flush=True)

def load_model(size, device, compute_type, cache_dir=None, backend="native"):
    if backend == "wsl_amd":
        try:
            return WslWhisperModel(model_name=size)
        except Exception as exc:
            print(f"WSL-Backend fehlgeschlagen ({exc}). Fallback auf CPU-Backend.")
            device = "cpu"
            compute_type = "float32"

    # 1) Versuch, nur aus dem Cache zu laden
    try:
        model_path = download_model(
            size_or_id=size,
            local_files_only=True,
            cache_dir=cache_dir
        )
        cached = True
    except (ValueError, HfHubHTTPError, LocalEntryNotFoundError):
        # 2) Noch nicht da → Download
        print(f"Download Whisper-Modell '{size}'...")
        model_path = download_model(
            size_or_id=size,
            local_files_only=False,
            cache_dir=cache_dir
        )
        print(f"Modell '{size}' heruntergeladen.")
        cached = False

    # 3) Spinner nur fürs lokale Laden
    stop_event = threading.Event()
    message = f"Lade Whisper-Modell '{size}' auf '{device}'…"
    spinner_thread = threading.Thread(
        target=_spinner, args=(message, stop_event), daemon=True
    )
    spinner_thread.start()

    model = WhisperModel(
        model_size_or_path=model_path,
        device=device,
        compute_type=compute_type,
        download_root=cache_dir,
        local_files_only=True
    )

    stop_event.set()
    spinner_thread.join()
    print(f"Whisper-Modell '{size}' auf '{device}' bereit.", flush=True)

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
    print("SpeechRecorder bereit.", flush=True)
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
    print("KeyBoardListener bereit.", flush=True)
    return hotkey
