import threading
import queue
import numpy as np
import sounddevice as sd

from hotkey_transcriber.keyboard_controller import KeyboardController


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
        self._rec_mark_printed = False

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
        """
        count = 1  # accounts for the emoji pasted below
        self.keyb_c.paste("📝", end="")
        while True:
            # Wait up to 0.5 s; returns True immediately if event is set.
            if stop_event.wait(timeout=0.5):
                break
            # interval=0: pyautogui types the dot instantly; the 0.5 s pacing
            # is handled entirely by the Event.wait() above.
            self.keyb_c.write('.', end="", interval=0)
            count += 1
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
            self._rec_mark_printed = True  # set atomically before paste

        self.keyb_c.save_clipboard()
        self.keyb_c.paste(self.rec_mark)

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            do_clear = self._rec_mark_printed
            self._rec_mark_printed = False  # cleared atomically inside lock
            stream = self._stream
            self._stream = None

        # Remove REC marker immediately – text field still has focus here.
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
