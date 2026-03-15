"""
Wake Word Listener - Stream microphone audio and trigger a callback when a wake word is detected.

Architecture:
    ┌─────────────────────────────────────────┐
    │  WakeWordListener                       │
    │  ┌───────────────────────────────────┐  │
    │  │  Audio stream (sounddevice)       │  │
    │  │  → 16kHz float32 blocks → queue   │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  _listen_loop (background thread) │  │
    │  │  → openwakeword Model.predict()   │  │
    │  │  → threshold check + cooldown     │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  callback(detected_name)          │  │
    │  │  → caller handles action          │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.wake_word.wake_word_listener import WakeWordListener, list_available_wake_word_models

    listener = WakeWordListener(callback=my_fn, model_name="hey jarvis")
    listener.start()
    # ... later ...
    listener.stop()
"""

import queue
import threading
import time
from pathlib import Path

import numpy as np

from hotkey_transcriber.speech_recorder import _import_sounddevice

sd = _import_sounddevice()

try:
    import openwakeword
    from openwakeword.model import Model

    _HAVE_WAKE_WORD = True
except ImportError:
    _HAVE_WAKE_WORD = False

_CUSTOM_WAKEWORD_DIRS = [
    Path(__file__).resolve().parent.parent / "resources" / "wakewords",
]
_WAKE_WORD_COOLDOWN_SECONDS = 1.0


def _normalize_model_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def list_available_wake_word_models() -> list[str]:
    """Return a sorted list of all available wake word model names."""
    models: set[str] = set()
    if _HAVE_WAKE_WORD:
        models.update(key.replace("_", " ") for key in openwakeword.MODELS)

    for directory in _CUSTOM_WAKEWORD_DIRS:
        if not directory.exists():
            continue
        for model_path in directory.glob("*.onnx"):
            models.add(model_path.stem.replace("_", " "))

    return sorted(models)


class WakeWordListener:
    """Stream microphone audio and fire a callback when a wake word is detected."""

    def __init__(
        self, callback, model_name: str = "hey jarvis", threshold: float = 0.5, model_names=None
    ):
        self.callback = callback
        self.model_name = model_name
        self.model_names = list(model_names or [model_name])
        self.threshold = threshold

        self._lock = threading.Lock()
        self._running = False
        self._paused = False
        self._audio_q: queue.Queue = queue.Queue()
        self._stream = None
        self._listen_thread: threading.Thread | None = None
        self._model = None
        self._cooldown_until = 0.0

    def _resolve_models(self) -> list[tuple[str, str]]:
        resolved = []
        for model_name in self.model_names:
            normalized_name = _normalize_model_name(model_name)

            if _HAVE_WAKE_WORD:
                model_info = openwakeword.MODELS.get(normalized_name)
                if model_info:
                    resolved.append((normalized_name, model_info["model_path"]))
                    continue

            for directory in _CUSTOM_WAKEWORD_DIRS:
                model_path = directory / f"{normalized_name}.onnx"
                if model_path.exists():
                    resolved.append((normalized_name, str(model_path)))
                    break
            else:
                available = ", ".join(list_available_wake_word_models())
                raise ValueError(
                    f"Unknown wake word model '{model_name}'. Available models: {available}"
                )
        return resolved

    @property
    def is_supported(self) -> bool:
        return _HAVE_WAKE_WORD

    @property
    def running(self) -> bool:
        return self._running

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if self._running and not self._paused:
            self._audio_q.put(indata.copy())

    def _flush_queue(self) -> None:
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def _listen_loop(self) -> None:
        print(f"Loading openwakeword model(s) {self.model_names}...")
        try:
            resolved_models = self._resolve_models()
            self._model = Model(
                wakeword_models=[model_path for _, model_path in resolved_models]
            )
            key_to_name: dict[str, str] = {}
            for normalized_name, model_path in resolved_models:
                key_to_name[Path(model_path).stem.lower()] = normalized_name.replace("_", " ")
            for model_key in self._model.models:
                key_to_name.setdefault(model_key.lower(), model_key.replace("_", " "))
        except Exception as e:
            print(f"Failed to load openwakeword model: {e}")
            self._running = False
            return

        print("Wake word listener active.")

        while self._running:
            if self._paused:
                time.sleep(0.1)
                self._flush_queue()
                continue

            try:
                audio_chunk = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue

            if not self._running:
                break

            audio_data_int16 = (audio_chunk[:, 0] * 32767).astype(np.int16)
            prediction = self._model.predict(audio_data_int16)

            detected_key = None
            detected_score = 0.0
            for model_key, score in prediction.items():
                if score > detected_score:
                    detected_key = model_key
                    detected_score = score

            if detected_key is not None and detected_score > self.threshold:
                if time.time() < self._cooldown_until:
                    continue

                detected_name = key_to_name.get(
                    detected_key.lower(), detected_key.replace("_", " ")
                )
                print(f"\nWake word detected: {detected_name}! (score: {detected_score:.2f})")
                self._flush_queue()
                self._model.reset()
                self._cooldown_until = time.time() + _WAKE_WORD_COOLDOWN_SECONDS
                try:
                    self.callback(detected_name)
                except Exception as e:
                    print(f"Error in wake word callback: {e}")

    def start(self) -> None:
        if not self.is_supported:
            print("openwakeword not installed. Cannot start wake word listener.")
            return

        with self._lock:
            if self._running:
                return

            self._running = True
            self._paused = False
            self._flush_queue()

            try:
                self._open_stream()
            except Exception as e:
                print(f"Failed to start audio stream for wake word: {e}")
                self._running = False
                return

        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()

    def _open_stream(self) -> None:
        self._stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="float32",
            blocksize=1280,
            callback=self._audio_callback,
        )
        self._stream.start()

    def _close_stream(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._close_stream()

        if (
            self._listen_thread
            and self._listen_thread.is_alive()
            and self._listen_thread is not threading.current_thread()
        ):
            self._listen_thread.join(timeout=2.0)

    def pause(self) -> None:
        """Pause listening and release the microphone."""
        self._paused = True
        self._close_stream()

    def resume(self) -> None:
        """Resume listening and re-open the microphone stream."""
        self._flush_queue()
        if self._model is not None:
            self._model.reset()
        try:
            self._open_stream()
        except Exception as e:
            print(f"Failed to reopen audio stream for wake word: {e}")
        self._paused = False
