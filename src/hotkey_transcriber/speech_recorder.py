import ctypes.util
import ctypes
import platform
import sys
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

from hotkey_transcriber.keyboard_controller import KeyboardController, is_terminal_focused


class SpeechRecorder:
    def __init__(self, model, keyboard_controller: KeyboardController,
                 channels: int, chunk_ms: int,
                 language: str, rec_mark: str):
        self.model = model
        self.keyb_c = keyboard_controller
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.language = language
        self.rec_mark = rec_mark

        self._lock = threading.Lock()
        self._running = False
        self._rec_mark_pasted = False

        self._audio_q = queue.Queue()
        self._stream = None  # opened on demand in start(), closed in stop()

        self._transcribe_thread = None

    @property
    def running(self):
        return self._running

    def set_language(self, language: str):
        self.language = language

    # ------------------------------------------------------------------ #
    # Audio callback (sounddevice internal thread)                         #
    # ------------------------------------------------------------------ #

    def _audio_callback(self, indata, frames, ti, status):
        if self._running:
            self._audio_q.put(indata.copy())

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

        if full:
            self.keyb_c.paste(full)
            self.keyb_c.write(" ", end="", interval=0)  # direct keypress – clipboard strips trailing space on Windows

        self.keyb_c.load_clipboard()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self):
        # Wait for a previous transcription to finish before inserting the new
        # REC marker. Without this, the first thread can paste its text *after*
        # the new marker, causing stop()'s backspace to delete transcribed text.
        if self._transcribe_thread and self._transcribe_thread.is_alive():
            self._transcribe_thread.join()

        with self._lock:
            if self._running:
                return
            self._flush_audio_queue()
            self._stream = sd.InputStream(
                samplerate=16_000,
                channels=1,
                dtype="float32",
                blocksize=int(16_000 * self.chunk_ms / 1000),
                callback=self._audio_callback,
            )
            self._stream.start()
            self._running = True
            self._rec_mark_pasted = sys.platform != "linux"

        self.keyb_c.save_clipboard()
        if sys.platform == "linux":
            # On Linux, Alt is physically held during PTT — Ctrl+V would
            # be interpreted as Alt+Ctrl+V by the compositor.  Only print
            # to terminal; the tray icon already signals recording status.
            print(self.rec_mark, flush=True)
        else:
            self.keyb_c.paste(self.rec_mark)

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            do_clear = self._rec_mark_pasted
            self._rec_mark_pasted = False
            stream = self._stream
            self._stream = None

        if do_clear:
            self.keyb_c.backspace(len(self.rec_mark))

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
