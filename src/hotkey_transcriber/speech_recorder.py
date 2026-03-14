import ctypes.util
import ctypes
import platform
import re
import sys
import time
import threading
import queue
from pathlib import Path

import numpy as np


def _linux_lib_dir() -> Path | None:
    if platform.system().lower() != "linux":
        return None
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        return None

    lib_dir = (
        Path(__file__).resolve().parent
        / "resources"
        / "lib"
        / "linux"
        / "x86_64"
    )
    return lib_dir if lib_dir.is_dir() else None


def _portaudio_fallback_path() -> str | None:
    lib_dir = _linux_lib_dir()
    if not lib_dir:
        return None
    candidate = lib_dir / "libportaudio.so.2.0.0"
    return str(candidate) if candidate.is_file() else None


def _preload_linux_audio_deps() -> None:
    lib_dir = _linux_lib_dir()
    if not lib_dir:
        return

    jack = lib_dir / "libjack.so.0.1.0"
    if jack.is_file():
        try:
            ctypes.CDLL(str(jack), mode=ctypes.RTLD_GLOBAL)
        except OSError:
            pass


def _import_sounddevice():
    try:
        import sounddevice as sd_mod
        return sd_mod
    except OSError as exc:
        if "PortAudio library not found" not in str(exc):
            raise

        fallback = _portaudio_fallback_path()
        if not fallback:
            raise
        _preload_linux_audio_deps()

        original_find_library = ctypes.util.find_library

        def _patched_find_library(name: str):
            if name == "portaudio":
                return fallback
            return original_find_library(name)

        ctypes.util.find_library = _patched_find_library
        try:
            import sounddevice as sd_mod
            return sd_mod
        finally:
            ctypes.util.find_library = original_find_library

sd = _import_sounddevice()


# ---------------------------------------------------------------------------
# Silero VAD (ONNX) — reuses the model bundled with faster-whisper
# ---------------------------------------------------------------------------

class _SileroVAD:
    """Streaming Voice Activity Detection using Silero v6 (ONNX).

    The model is shipped inside faster-whisper (assets/silero_vad_v6.onnx),
    so no extra dependency is needed.  Each call processes 512 new samples
    (~32 ms at 16 kHz) plus 64 context samples from the previous chunk.
    """

    WINDOW_SIZE = 512          # new samples per call
    _CONTEXT_SIZE = 64         # trailing context carried over

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        import importlib.util
        import onnxruntime

        # Locate the ONNX model bundled with faster-whisper without triggering
        # the heavy ctranslate2 import at the package level.
        spec = importlib.util.find_spec("faster_whisper")
        if spec is None or spec.origin is None:
            raise ImportError("faster-whisper is not installed")
        model_path = Path(spec.origin).parent / "assets" / "silero_vad_v6.onnx"
        if not model_path.exists():
            # Fallback for older faster-whisper versions
            model_path = model_path.with_name("silero_vad.onnx")
        if not model_path.exists():
            raise FileNotFoundError(
                f"Silero VAD ONNX model not found in {model_path.parent}"
            )

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 4
        self._session = onnxruntime.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
            sess_options=opts,
        )
        self.reset()

    def reset(self):
        """Clear LSTM hidden state and context (call between recordings)."""
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros(self._CONTEXT_SIZE, dtype=np.float32)

    def is_speech(self, audio_f32: np.ndarray) -> bool:
        """Return True when *audio_f32* (~512 float32 samples, 16 kHz) contains speech."""
        x = np.asarray(audio_f32, dtype=np.float32)
        if len(x) < self.WINDOW_SIZE:
            x = np.pad(x, (0, self.WINDOW_SIZE - len(x)))
        elif len(x) > self.WINDOW_SIZE:
            x = x[: self.WINDOW_SIZE]

        # Prepend context from previous chunk (silero v6 expects 576 = 64 + 512)
        frame = np.concatenate([self._context, x])[np.newaxis, :]   # [1, 576]
        self._context = x[-self._CONTEXT_SIZE:]

        out, self._h, self._c = self._session.run(
            None,
            {"input": frame, "h": self._h, "c": self._c},
        )
        prob = out.item() if out.ndim == 0 else float(out.flat[0])
        return prob > self.threshold


def _load_vad() -> _SileroVAD | None:
    try:
        return _SileroVAD()
    except Exception as exc:
        print(f"Silero VAD nicht verfuegbar ({exc}). Auto-Stop deaktiviert.")
        return None

from hotkey_transcriber.keyboard_controller import KeyboardController, is_terminal_focused
from hotkey_transcriber.spoken_text_actions import SpokenTextActionExecutor, _URL_INSERT_BUILTINS


def normalize_language(language: str | None) -> str | None:
    """Return None for auto-detect, otherwise the language code as-is."""
    if language in (None, "", "auto"):
        return None
    return language


class SpeechRecorder:
    def __init__(self, model, keyboard_controller: KeyboardController,
                 channels: int, chunk_ms: int,
                 language: str | None, rec_mark: str,
                 spoken_enter_enabled: bool = False,
                 spoken_text_action_executor: SpokenTextActionExecutor | None = None,
                 silence_timeout_ms: int = 1500,
                 max_initial_wait_ms: int | None = 5000):
        self.model = model
        self.keyb_c = keyboard_controller
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.language = self._normalize_language(language)
        self.rec_mark = rec_mark
        self.spoken_enter_enabled = spoken_enter_enabled
        self.spoken_text_action_executor = spoken_text_action_executor
        self._active_rec_mark = ""

        self._lock = threading.Lock()
        self._running = False
        self._rec_mark_pasted = False

        self._audio_q = queue.Queue()
        self._stream = None  # opened on demand in start(), closed in stop()

        self._transcribe_thread = None
        self._auto_stop = False
        self._silence_timeout_ms = silence_timeout_ms
        self._max_initial_wait_ms = self._normalize_initial_wait_ms(max_initial_wait_ms)
        self._silence_start_time = None
        self._start_time = None
        self._speech_detected = False
        self._vad = _load_vad()

    @staticmethod
    def _normalize_initial_wait_ms(value):
        if value is None or value <= 0:
            return None
        return value

    @property
    def running(self):
        return self._running

    @staticmethod
    def _normalize_language(language: str | None) -> str | None:
        return normalize_language(language)

    def set_language(self, language: str | None):
        self.language = self._normalize_language(language)

    def _split_trailing_enter_command(self, text: str) -> tuple[str, bool]:
        if not self.spoken_enter_enabled:
            return text, False
        stripped = text.rstrip()
        if not stripped:
            return text, False
        parts = stripped.split()
        if not parts:
            return text, False

        last_token = parts[-1]
        normalized_last_token = re.sub(r"^\W+|\W+$", "", last_token, flags=re.UNICODE).casefold()
        if normalized_last_token != "enter":
            return text, False

        prefix = stripped[:stripped.rfind(last_token)].rstrip()
        return prefix, True

    def _recording_marker_text(self) -> str:
        if sys.platform == "linux":
            return "REC"
        return self.rec_mark

    def _run_spoken_action(self, text: str) -> tuple[str, bool]:
        if self.spoken_text_action_executor is None:
            return text, False
        match = self.spoken_text_action_executor.match(text)
        if match is None:
            return text, False
        action, remainder = match
        processed_remainder = remainder
        should_submit = False
        if action.builtin in _URL_INSERT_BUILTINS:
            processed_remainder, should_submit = self._split_trailing_enter_command(remainder)
        executed, consumed_remainder = self.spoken_text_action_executor.execute(
            action,
            processed_remainder,
            submit_after=should_submit,
        )
        if not executed:
            return text, False
        if not action.paste_remainder:
            return "", True
        if consumed_remainder:
            return "", True
        return processed_remainder, True

    # ------------------------------------------------------------------ #
    # Audio callback (sounddevice internal thread)                         #
    # ------------------------------------------------------------------ #

    def _audio_callback(self, indata, frames, ti, status):
        """Called by sounddevice for each audio chunk."""
        if not self._running:
            return

        audio_chunk = indata.copy()
        self._audio_q.put(audio_chunk)

        # Silero VAD auto-stop: feed 512-sample float32 mono chunks
        if self._auto_stop and self._vad is not None:
            try:
                is_speech = self._vad.is_speech(audio_chunk[:, 0])
            except Exception:
                is_speech = True  # Fallback if VAD fails

            now = time.time()

            if is_speech:
                self._speech_detected = True
                self._silence_start_time = now
            else:
                if not self._speech_detected:
                    if (
                        self._max_initial_wait_ms is not None
                        and self._start_time is not None
                        and (now - self._start_time) * 1000 > self._max_initial_wait_ms
                    ):
                        self._auto_stop = False
                        threading.Thread(target=self.stop, daemon=True).start()
                    return

                if self._silence_start_time is None:
                    self._silence_start_time = now
                elif (now - self._silence_start_time) * 1000 > self._silence_timeout_ms:
                    self._auto_stop = False
                    threading.Thread(target=self.stop, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _flush_audio_queue(self):
        while True:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def _drain_audio_queue(self):
        chunks = []
        while True:
            try:
                chunks.append(self._audio_q.get_nowait())
            except queue.Empty:
                break
        return chunks

    def _run_dot_printer(self, stop_event):
        """Show 📝 + growing dots while transcription runs, then erase them.

        Uses Event.wait() for timing instead of sleep() so that the thread
        unblocks immediately when stop_event is set.  `count` is a pure local
        variable – no shared state, no race condition.

        In terminals the emoji is skipped (some TUIs need multiple backspaces
        to delete a single emoji, leaving artefacts).
        """
        skip_emoji = self.keyb_c.backend_name == "ydotool" and is_terminal_focused()
        if skip_emoji:
            count = 0
        else:
            count = 1
            self.keyb_c.paste("📝", end="")
        while True:
            if stop_event.wait(timeout=0.5):
                break
            self.keyb_c.write('.', end="", interval=0)
            count += 1
        if count > 0:
            self.keyb_c.backspace(count)

    def _transcribe_and_paste(self):
        # stream.stop() in stop() already blocked until all callbacks finished,
        # so the queue contains the complete recording at this point.
        chunks = self._drain_audio_queue()
        if not chunks:
            self.keyb_c.load_clipboard()
            return

        full = ""
        dot_stop = threading.Event()
        dot_thread = threading.Thread(
            target=self._run_dot_printer, args=(dot_stop,), daemon=True
        )
        dot_thread.start()
        try:
            audio = np.concatenate(chunks, axis=0)[:, 0]
            seg_iterator, _ = self.model.transcribe(
                audio,
                language=self.language,
                vad_filter=True,
                beam_size=1,
                best_of=1,
                temperature=0,
                condition_on_previous_text=False,
            )
            segments = list(seg_iterator)
            full = " ".join(s.text.strip() for s in segments).strip()
        except Exception as e:
            print(f"Transkription fehlgeschlagen: {e}")
        finally:
            # Signal dot printer to stop and wait for it to erase its chars
            # before we paste the result – order matters for the text field.
            dot_stop.set()
            dot_thread.join()

        action_text, _ = self._run_spoken_action(full)
        output_text, should_press_enter = self._split_trailing_enter_command(action_text)

        if output_text:
            self.keyb_c.paste(output_text)
            if not should_press_enter:
                self.keyb_c.write(" ", end="", interval=0)  # direct keypress – clipboard strips trailing space on Windows
        if should_press_enter:
            self.keyb_c.press("enter")

        self.keyb_c.load_clipboard()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self, auto_stop=False, silence_timeout_ms=1500, max_initial_wait_ms=None):
        # Wait for a previous transcription to finish before inserting the new
        # REC marker. Without this, the first thread can paste its text *after*
        # the new marker, causing stop()'s backspace to delete transcribed text.
        if self._transcribe_thread and self._transcribe_thread.is_alive():
            self._transcribe_thread.join()

        with self._lock:
            if self._running:
                return
            self._flush_audio_queue()

            self._auto_stop = auto_stop
            self._silence_timeout_ms = silence_timeout_ms
            self._max_initial_wait_ms = self._normalize_initial_wait_ms(max_initial_wait_ms)
            self._silence_start_time = None
            self._speech_detected = False

            if self._vad is not None:
                self._vad.reset()

            # Silero VAD needs exactly 512 samples per chunk (~32 ms at 16 kHz).
            # For normal PTT (no auto-stop) we use the configured chunk_ms.
            blocksize = (
                _SileroVAD.WINDOW_SIZE
                if auto_stop and self._vad is not None
                else int(16_000 * self.chunk_ms / 1000)
            )

            self._stream = sd.InputStream(
                samplerate=16_000,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._start_time = time.time()
            self._running = True
            self._active_rec_mark = self._recording_marker_text()
            self._rec_mark_pasted = bool(self._active_rec_mark)

        self.keyb_c.save_clipboard()
        if sys.platform == "linux":
            self.keyb_c.write(self._active_rec_mark, end="", interval=0)
        else:
            self.keyb_c.paste(self._active_rec_mark)

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            do_clear = self._rec_mark_pasted
            self._rec_mark_pasted = False
            active_rec_mark = self._active_rec_mark
            self._active_rec_mark = ""
            stream = self._stream
            self._stream = None

        if do_clear:
            self.keyb_c.backspace(len(active_rec_mark))

        # stop() blocks until the last audio callback completes (≤ one
        # chunk_ms = 30 ms), guaranteeing all audio is in the queue before
        # the transcribe thread drains it.
        if stream:
            stream.stop()
            stream.close()

        self._transcribe_thread = threading.Thread(
            target=self._transcribe_and_paste, daemon=True
        )
        self._transcribe_thread.start()
