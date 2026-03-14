"""
Model and Recorder Factory - Download/initialize Whisper models and assemble the SpeechRecorder with all dependencies.

Architecture:
    ┌─────────────────────────────────────────┐
    │  ModelAndRecorderFactory                │
    │  ┌───────────────────────────────────┐  │
    │  │  load_model(size, device, ...)    │  │
    │  │  → downloads / repairs model      │  │
    │  │  → returns WhisperModel variant   │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  load_speech_recorder(model, ...) │  │
    │  │  → KeyboardController             │  │
    │  │  → SpokenTextActionExecutor       │  │
    │  │  → SpeechRecorder                 │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  load_keyboard_listener(recorder) │  │
    │  │  → KeyBoardListener (started)     │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.model_and_recorder_factory import load_model, load_speech_recorder, load_keyboard_listener

    model = load_model(size="large-v3-turbo", device="cuda", compute_type="float16")
    recorder = load_speech_recorder(model=model, ...)
    hotkey = load_keyboard_listener(recorder, hotkey_config={"modifier": "alt", "key": "r"})
"""

import contextlib
import itertools
import os
import shutil
import threading
import time
from pathlib import Path

from faster_whisper import WhisperModel, download_model
from huggingface_hub.errors import LocalEntryNotFoundError
from huggingface_hub.utils import HfHubHTTPError

from hotkey_transcriber.actions.spoken_text_actions import (
    SpokenTextActionExecutor,
    load_spoken_text_actions,
)
from hotkey_transcriber.keyboard.keyboard_controller import KeyboardController
from hotkey_transcriber.keyboard.keyboard_listener import KeyBoardListener
from hotkey_transcriber.speech_recorder import SpeechRecorder
from hotkey_transcriber.transcription.wsl_whisper_bridge import WslWhisperModel


def _spinner(message: str, stop_event: threading.Event) -> None:
    for char in itertools.cycle(["|", "/", "-", "\\"]):
        if stop_event.is_set():
            break
        print(f"{char} {message}", end="\r", flush=True)
        time.sleep(0.1)
    print(" " * (len(message) + 2), end="\r", flush=True)


def _snapshot_has_model_bin(model_path: str) -> bool:
    return os.path.isfile(os.path.join(model_path, "model.bin"))


def _cleanup_stale_hf_state(model_path: str) -> None:
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
            with contextlib.suppress(Exception):
                incomplete_file.unlink(missing_ok=True)

    locks_dir = model_dir / ".locks"
    if locks_dir.is_dir():
        shutil.rmtree(locks_dir, ignore_errors=True)


def _repair_and_download(size: str, model_path: str, cache_dir=None) -> str:
    _cleanup_stale_hf_state(model_path)
    try:
        if os.path.isdir(model_path):
            shutil.rmtree(model_path, ignore_errors=True)
    except Exception:
        pass

    return download_model(
        size_or_id=size,
        local_files_only=False,
        cache_dir=cache_dir,
    )


def load_model(
    size: str,
    device: str,
    compute_type: str,
    cache_dir=None,
    backend: str = "native",
    use_torch_whisper: bool = False,
):
    """Download (if needed) and load a Whisper model. Returns a model object."""
    if backend == "wsl_amd":
        try:
            return WslWhisperModel(model_name=size)
        except Exception as exc:
            print(f"WSL-Backend fehlgeschlagen ({exc}). Fallback auf CPU-Backend.")
            device = "cpu"
            compute_type = "float32"

    if use_torch_whisper:
        return _load_torch_whisper(size, device, compute_type)

    try:
        model_path = download_model(
            size_or_id=size,
            local_files_only=True,
            cache_dir=cache_dir,
        )
    except (ValueError, HfHubHTTPError, LocalEntryNotFoundError):
        print(f"⏬ Download Whisper-Modell '{size}'…")
        model_path = download_model(
            size_or_id=size,
            local_files_only=False,
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
    except RuntimeError as exc:
        model_path = _repair_and_download(size=size, model_path=model_path, cache_dir=cache_dir)
        if not _snapshot_has_model_bin(model_path):
            raise RuntimeError(
                f"Model '{size}' enthaelt kein model.bin und ist nicht als faster-whisper/ctranslate2 Modell verfuegbar."
            ) from exc
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


def _load_torch_whisper(size: str, device: str, compute_type: str):
    from hotkey_transcriber.transcription.torch_whisper_fallback_backend import TorchWhisperModel

    print(
        "AMD-GPU erkannt – verwende torch-Backend (openai-whisper) "
        "statt CTranslate2, da dessen HIP-Kernel auf diesem Geraet nicht kompatibel sind.",
        flush=True,
    )

    stop_event = threading.Event()
    message = f"Lade Whisper-Modell '{size}' auf '{device}' (torch)…"
    spinner_thread = threading.Thread(target=_spinner, args=(message, stop_event), daemon=True)
    spinner_thread.start()

    model = TorchWhisperModel(model_size=size, device=device, compute_type=compute_type)

    stop_event.set()
    spinner_thread.join()
    print(f"✅ Whisper-Modell '{size}' auf '{device}' bereit (torch-Backend).", flush=True)
    return model


def load_speech_recorder(
    model,
    wait_on_keyboard: float,
    channels: int,
    chunk_ms: int,
    language: str | None,
    rec_mark: str,
    spoken_enter_enabled: bool = False,
    spoken_undo_enabled: bool = False,
    spoken_text_actions_enabled: bool = True,
    spoken_text_actions: list | None = None,
    silence_timeout_ms: int = 1500,
    max_initial_wait_ms: int = 5000,
) -> SpeechRecorder:
    """Build and return a fully configured SpeechRecorder instance."""
    message = "Lade SpeechRecorder…"
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=_spinner, args=(message, stop_event), daemon=True)
    spinner_thread.start()

    keyboard_controller = KeyboardController(wait=wait_on_keyboard)
    spoken_text_action_executor = SpokenTextActionExecutor(
        actions=load_spoken_text_actions(spoken_text_actions),
        enabled=spoken_text_actions_enabled,
    )
    recorder = SpeechRecorder(
        model=model,
        keyboard_controller=keyboard_controller,
        channels=channels,
        chunk_ms=chunk_ms,
        language=language,
        rec_mark=rec_mark,
        spoken_enter_enabled=spoken_enter_enabled,
        spoken_undo_enabled=spoken_undo_enabled,
        spoken_text_action_executor=spoken_text_action_executor,
        silence_timeout_ms=silence_timeout_ms,
        max_initial_wait_ms=max_initial_wait_ms,
    )

    stop_event.set()
    spinner_thread.join()
    print("✅ SpeechRecorder bereit.", flush=True)
    return recorder


def load_keyboard_listener(
    recorder: SpeechRecorder, hotkey_config: dict | None = None
) -> KeyBoardListener:
    """Build, start, and return a KeyBoardListener bound to the given recorder."""
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
