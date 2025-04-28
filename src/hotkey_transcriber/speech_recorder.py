import threading, queue, numpy as np, sounddevice as sd
from faster_whisper import WhisperModel

from hotkey_transcriber.keyboard_controller import KeyboardController

class SpeechRecorder:
    def __init__(self, model: WhisperModel, keyboard_controller: KeyboardController, 
                 channels: int, chunk_ms: int,
                 interval: float, language: str, rec_mark: str):
        # Objekte übergeben
        self.model      = model
        self.kb = keyboard_controller
        # Variablen für Audiostream setzen
        self.channels = channels
        self.chunk_ms = chunk_ms
        
        self.interval   = interval
        self.language   = language
        self.rec_mark   = rec_mark

        self.audio_q    = queue.Queue()
        self.buffer     = []
        self.running    = False
        self.event      = threading.Event()
        self.lock       = threading.Lock()
    
        self.last_text  = ""

        self.recorder_thread    = None
        self.transcriber_thread = None

        # Audio-Stream starten
        self.stream = sd.InputStream(
            samplerate=16_000,
            channels=1,
            dtype="float32",
            blocksize=int(16_000 * self.chunk_ms / 1000),
            callback=self._audio_callback,
        )
        self.stream.start()

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

    def _live_loop(self):
        self.last_text = ""
        while self.running:
            self.event.wait(timeout=self.interval)

            if not self.buffer:
                continue

            snap = list(self.buffer)
            try:
                audio = np.concatenate(snap, axis=0)[:,0]
            except ValueError:
                continue

            segments, _ = self.model.transcribe(
                audio, language=self.language, vad_filter=True,
                beam_size=5, best_of=5
            )

            full = " ".join(s.text.strip() for s in segments).strip()
            if not full or full == self.last_text:
                continue

            if self.last_text and full.startswith(self.last_text):
                # nur Tail anhängen
                self.kb.paste(full[len(self.last_text):])
            else:
                # kompletten Text ersetzen
                self.kb.undo()
                self.kb.paste(full)

            self.last_text = full
        print(self.last_text)

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self.event.clear()
            self.recorder_thread    = threading.Thread(target=self._recorder, daemon=True)
            self.transcriber_thread = threading.Thread(target=self._live_loop, daemon=True)
            self.recorder_thread.start()
            self.transcriber_thread.start()
            # REC-Marker einfügen
            print(self.rec_mark)
            self.kb.paste(self.rec_mark)

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.event.set()
            self.recorder_thread.join()
            self.transcriber_thread.join()
            # Marker nur entfernen, wenn nie Text kam
            if not self.last_text:
                self.kb.undo()
            print("✋ STOP")
