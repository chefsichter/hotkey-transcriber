import threading
import queue
import time
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

        self.running = False
        self.rec_mark_printed = False
        self.start_stop_lock = threading.Lock()
        self.audio_q = queue.Queue()

        self._transcribe_thread = None
        self.dot_printer_thread = None

        self.stream = sd.InputStream(
            samplerate=16_000,
            channels=1,
            dtype="float32",
            blocksize=int(16_000 * self.chunk_ms / 1000),
            callback=self._audio_callback,
        )
        self.stream.start()

    def set_language(self, language: str):
        self.language = language

    def _audio_callback(self, indata, frames, ti, status):
        if self.running:
            self.audio_q.put(indata.copy())

    def _clear_queue(self):
        while not self.audio_q.empty():
            try:
                self.audio_q.get_nowait()
            except queue.Empty:
                break

    def _print_rec_symbol(self):
        if not self.rec_mark_printed:
            self.rec_mark_printed = True
            self.keyb_c.paste(self.rec_mark)

    def _clear_rec_symbol(self):
        if self.rec_mark_printed:
            self.rec_mark_printed = False
            self.keyb_c.undo()

    def _start_dot_printer(self):
        self.dot_stop_event = threading.Event()
        self.char_count = 1

        def dot_printer():
            self.keyb_c.paste("📝", end="")
            while not self.dot_stop_event.is_set():
                self.keyb_c.write('.', end="", interval=0.5)
                self.char_count += 1
            self.keyb_c.backspace(self.char_count)

        self.dot_printer_thread = threading.Thread(target=dot_printer, daemon=True)
        self.dot_printer_thread.start()

    def _stop_dot_printer(self):
        if hasattr(self, 'dot_stop_event'):
            self.dot_stop_event.set()
            if self.dot_printer_thread:
                self.dot_printer_thread.join()

    def _transcribe_and_paste(self):
        # Kurz warten, damit sounddevice In-Flight-Chunks noch in die Queue liefern kann
        time.sleep(0.15)
        # Alle aufgenommenen Chunks einsammeln
        chunks = []
        try:
            while True:
                chunks.append(self.audio_q.get_nowait())
        except queue.Empty:
            pass

        self._clear_rec_symbol()

        if not chunks:
            self.keyb_c.load_clipboard()
            return

        # Während Transkription: Punkte-Indikator anzeigen
        self._start_dot_printer()
        full = ""
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
            self._stop_dot_printer()

        if full:
            self.keyb_c.paste(full)

        self.keyb_c.load_clipboard()

    def start(self):
        with self.start_stop_lock:
            if self.running:
                return
            self._clear_queue()
            self.running = True
        self.keyb_c.save_clipboard()
        self._print_rec_symbol()

    def stop(self):
        with self.start_stop_lock:
            if not self.running:
                return
            self.running = False
        self._transcribe_thread = threading.Thread(
            target=self._transcribe_and_paste, daemon=True
        )
        self._transcribe_thread.start()
