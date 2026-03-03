import itertools
import os
import shutil
import sys
import threading
import time
from getpass import getpass
from pathlib import Path

from faster_whisper import WhisperModel, download_model
from huggingface_hub import login as hf_login
from huggingface_hub.errors import GatedRepoError, LocalEntryNotFoundError
from huggingface_hub.utils import HfHubHTTPError

from hotkey_transcriber.keyboard_controller import KeyboardController
from hotkey_transcriber.speech_recorder import SpeechRecorder
from hotkey_transcriber.keyboard_listener import KeyBoardListener
from hotkey_transcriber.wsl_backend import WslWhisperModel


def _spinner(message, stop_event):
    for char in itertools.cycle(["|", "/", "-", "\\"]):
        if stop_event.is_set():
            break
        print(f"{char} {message}", end="\r", flush=True)
        time.sleep(0.1)
    print(" " * (len(message) + 2), end="\r", flush=True)


def _snapshot_has_model_bin(model_path):
    return os.path.isfile(os.path.join(model_path, "model.bin"))


def _cleanup_stale_hf_state(model_path):
    """Remove stale partially-downloaded files and stale lock files."""
    try:
        model_dir = Path(model_path).resolve().parent.parent
    except Exception:
        return

    if not model_dir.exists():
        return

    blobs_dir = model_dir / "blobs"
    if blobs_dir.is_dir():
        for incomplete_file in blobs_dir.glob("*.incomplete"):
            try:
                incomplete_file.unlink(missing_ok=True)
            except Exception:
                pass

    locks_dir = model_dir / ".locks"
    if locks_dir.is_dir():
        shutil.rmtree(locks_dir, ignore_errors=True)


def _repair_and_download(size, model_path, cache_dir=None):
    _cleanup_stale_hf_state(model_path)
    try:
        if os.path.isdir(model_path):
            shutil.rmtree(model_path, ignore_errors=True)
    except Exception:
        pass

    return _download_model_online(
        size_or_id=size,
        cache_dir=cache_dir,
    )


def _download_model_online(size_or_id, cache_dir=None):
    try:
        return download_model(
            size_or_id=size_or_id,
            local_files_only=False,
            cache_dir=cache_dir,
        )
    except GatedRepoError:
        if not _prompt_and_set_hf_token(size_or_id):
            raise
        return download_model(
            size_or_id=size_or_id,
            local_files_only=False,
            cache_dir=cache_dir,
        )


def _prompt_and_set_hf_token(repo_id: str) -> bool:
    existing = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_HUB_TOKEN")
        or os.getenv("HF_HUB_TOKEN")
    )
    if existing:
        return True

    if not sys.stdin or not sys.stdin.isatty():
        print(
            f"Modell '{repo_id}' ist gated. Setze HF_TOKEN/HUGGINGFACE_HUB_TOKEN "
            "vor dem Start, da kein interaktiver Prompt verfuegbar ist."
        )
        return False

    print(f"Modell '{repo_id}' ist gated (Hugging Face).")
    token = getpass("Bitte HF_TOKEN eingeben (leer = abbrechen): ").strip()
    if not token:
        return False

    os.environ["HF_TOKEN"] = token
    os.environ["HUGGINGFACE_HUB_TOKEN"] = token
    os.environ["HF_HUB_TOKEN"] = token
    try:
        hf_login(token=token, add_to_git_credential=False)
    except Exception:
        # Env vars are often sufficient for the current process.
        pass
    return True


def load_model(size, device, compute_type, cache_dir=None, backend="native"):
    if backend == "wsl_amd":
        try:
            return WslWhisperModel(model_name=size)
        except Exception as exc:
            print(f"WSL-Backend fehlgeschlagen ({exc}). Fallback auf CPU-Backend.")
            device = "cpu"
            compute_type = "float32"

    try:
        model_path = download_model(
            size_or_id=size,
            local_files_only=True,
            cache_dir=cache_dir,
        )
    except (ValueError, HfHubHTTPError, LocalEntryNotFoundError):
        print(f"⏬ Download Whisper-Modell '{size}'…")
        model_path = _download_model_online(
            size_or_id=size,
            cache_dir=cache_dir,
        )
        print(f"✅ Modell '{size}' heruntergeladen.")

    if not _snapshot_has_model_bin(model_path):
        print(f"⚠️ Modell-Snapshot fuer '{size}' ist unvollstaendig, lade neu…")
        model_path = _repair_and_download(size=size, model_path=model_path, cache_dir=cache_dir)
        if not _snapshot_has_model_bin(model_path):
            raise RuntimeError(
                f"Model '{size}' enthaelt kein model.bin und ist nicht als faster-whisper/ctranslate2 Modell verfuegbar."
            )

    stop_event = threading.Event()
    message = f"Lade Whisper-Modell '{size}' auf '{device}'…"
    spinner_thread = threading.Thread(target=_spinner, args=(message, stop_event), daemon=True)
    spinner_thread.start()

    try:
        model = WhisperModel(
            model_size_or_path=model_path,
            device=device,
            compute_type=compute_type,
            download_root=cache_dir,
            local_files_only=True,
        )
    except RuntimeError:
        model_path = _repair_and_download(size=size, model_path=model_path, cache_dir=cache_dir)
        if not _snapshot_has_model_bin(model_path):
            raise RuntimeError(
                f"Model '{size}' enthaelt kein model.bin und ist nicht als faster-whisper/ctranslate2 Modell verfuegbar."
            )
        model = WhisperModel(
            model_size_or_path=model_path,
            device=device,
            compute_type=compute_type,
            download_root=cache_dir,
            local_files_only=True,
        )

    stop_event.set()
    spinner_thread.join()
    print(f"✅ Whisper-Modell '{size}' auf '{device}' bereit.", flush=True)

    return model


def load_speech_recorder(model, wait_on_keyboard, channels, chunk_ms, language, rec_mark):
    message = "Lade SpeechRecorder…"
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=_spinner, args=(message, stop_event), daemon=True)
    spinner_thread.start()

    keyboard_controller = KeyboardController(wait=wait_on_keyboard)
    recorder = SpeechRecorder(
        model=model,
        keyboard_controller=keyboard_controller,
        channels=channels,
        chunk_ms=chunk_ms,
        language=language,
        rec_mark=rec_mark,
    )

    stop_event.set()
    spinner_thread.join()
    print("✅ SpeechRecorder bereit.", flush=True)
    return recorder


def load_keyboard_listener(recorder, hotkey_config: dict = None):
    message = "Lade KeyBoardListener…"
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=_spinner, args=(message, stop_event), daemon=True)
    spinner_thread.start()

    cfg = hotkey_config or {}
    hotkey = KeyBoardListener(
        start_callback=recorder.start,
        stop_callback=recorder.stop,
        modifier=cfg.get("modifier", "alt"),
        key=cfg.get("key", "r"),
    )
    hotkey.start()

    stop_event.set()
    spinner_thread.join()
    print("✅ KeyBoardListener bereit.", flush=True)
    return hotkey


