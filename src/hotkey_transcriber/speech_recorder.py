import pyautogui
import threading, queue, numpy as np, sounddevice as sd
import time
from faster_whisper import WhisperModel
 
from hotkey_transcriber.keyboard_controller import KeyboardController

class SpeechRecorder:
    def __init__(self, model: WhisperModel, keyboard_controller: KeyboardController, 
                 channels: int, chunk_ms: int,
                 interval: float, language: str, rec_mark: str):
        # Objekte übergeben
        self.model      = model
        self.keyb_c = keyboard_controller
        # Variablen für Audiostream setzen
        self.channels = channels
        self.chunk_ms = chunk_ms
        
        self.interval   = interval
        self.language   = language
        self.rec_mark   = rec_mark

        self.running    = False
        self.rec_mark_printed = False
        self.is_transcribing = False
        self.transcription_printed = False
        self.last_text  = ""
        self.audio_q    = queue.Queue()
        self.buffer     = []
        
        self.event      = threading.Event()
        self.lock       = threading.Lock()
        self.recorder_thread    = None
        self.transcriber_thread = None
        self.dot_printer_thread = None

        # Audio-Stream starten
        self.stream = sd.InputStream(
            samplerate=16_000,
            channels=1,
            dtype="float32",
            blocksize=int(16_000 * self.chunk_ms / 1000),
            callback=self._audio_callback,
        )
        self.clear_variables()
        self.stream.start()

    def clear_variables(self):
        self.running    = False
        self.rec_mark_printed = False
        self.is_transcribing = False
        self.transcription_printed = False
        self.last_text = ""
        while not self.audio_q.empty():
            self.audio_q.get_nowait()
        self.buffer.clear()
        self.event.clear()

    def set_interval(self, interval: float):
        """Ändert das Transkribier-Intervall on-the-fly."""
        self.interval = interval

    def set_language(self, language: str):
        self.language = language

    def _audio_callback(self, indata, frames, ti, status):
        if self.running:
            self.audio_q.put(indata.copy())

    def _recorder(self):
        self.buffer = []
        while self.running:
            try:
                self.buffer.append(self.audio_q.get(timeout=0.1))
            except queue.Empty:
                pass

    def start_dot_printer_thread(self):
        self.clear_rec_symbol()
        self.continue_dot_printing = True
        self.char_count = 1

        def dot_printer():
            # Punkte ausgeben, bis die Transkription abgeschlossen ist
            self.keyb_c.paste("📝", end="")
            while self.continue_dot_printing:
                self.keyb_c.write('.', end="", interval=0.5)  # Punkt ausgeben
                self.char_count += 1
            # Entferne die ausgegebenen Punkte und das Emoji
            self.keyb_c.backspace(self.char_count)

        # Als Daemon-Thread, damit er bei Programmende nicht blockiert
        self.dot_printer_thread = threading.Thread(target=dot_printer, daemon=True)
        self.dot_printer_thread.start()

    def clear_dot_printing(self):
        if not self.running: # when user stopped, write dots for transcription waiting time
            self.continue_dot_printing = False
            if self.dot_printer_thread:
                self.dot_printer_thread.join()

    def print_rec_symbol(self):
        if not self.rec_mark_printed:
            self.rec_mark_printed = True
            self.keyb_c.paste(self.rec_mark)

    def clear_rec_symbol(self):
        if self.rec_mark_printed:
            self.rec_mark_printed = False
            self.keyb_c.undo()

    def clear_partial_transcription(self, transcription_len=None):
        if self.transcription_printed:
            self.keyb_c.undo()
            self.transcription_printed = False
            # self.keyb_c.backspace(transcription_len)

    def _live_loop(self):
        self.keyb_c.save_clipboard()
        self.print_rec_symbol()
        while self.running:
            self.event.wait(timeout=self.interval)

            if not self.buffer:
                continue

            snap = list(self.buffer)
            try:
                audio = np.concatenate(snap, axis=0)[:,0]
            except ValueError:
                continue

            seg_iterator, _ = self.model.transcribe(
                audio, language=self.language, vad_filter=True,
                beam_size=5, best_of=5
            )
            try:
                self.is_transcribing = True
                segments = list(seg_iterator)
            except RuntimeError as e:
                print("Transkription fehlgeschlagen: {e}")
                break
            finally:
                self.is_transcribing = False

            full = " ".join(s.text.strip() for s in segments).strip()
            
            if not full or full == self.last_text:
                continue

            self.clear_rec_symbol()
            self.clear_dot_printing()

            if self.last_text and full.startswith(self.last_text):
                # nur Tail anhängen
                self.keyb_c.paste(full[len(self.last_text):])
            else:
                self.clear_partial_transcription()  
                self.keyb_c.paste(full)

            self.transcription_printed = True
            self.last_text = full
        self.clear_rec_symbol()
        self.clear_dot_printing()

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self.recorder_thread    = threading.Thread(target=self._recorder, daemon=True)
            self.transcriber_thread = threading.Thread(target=self._live_loop, daemon=True)
            self.recorder_thread.start()
            self.transcriber_thread.start()

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            # Transkription kann starten, wecke das Event
            self.event.set()
            # Progress-Indikator (Punkte) starten
            if self.is_transcribing:
                self.start_dot_printer_thread()
            # Warte auf Ende der Aufnahme- und Transkriptions-Threads
            self.recorder_thread.join()
            self.transcriber_thread.join()
            print("✋ STOP")
            self.clear_variables()
            self.keyb_c.load_clipboard()
