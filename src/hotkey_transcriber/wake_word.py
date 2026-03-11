import threading
import time
import queue
import numpy as np

from hotkey_transcriber.speech_recorder import _import_sounddevice

sd = _import_sounddevice()

try:
    import openwakeword
    from openwakeword.model import Model
    _HAVE_WAKE_WORD = True
except ImportError:
    _HAVE_WAKE_WORD = False


class WakeWordListener:
    """Listens for a wake word in the background and triggers a callback when detected."""

    def __init__(self, callback, model_name="hey jarvis", threshold=0.5):
        self.callback = callback
        self.model_name = model_name
        self.threshold = threshold
        
        self._lock = threading.Lock()
        self._running = False
        self._paused = False
        self._audio_q = queue.Queue()
        self._stream = None
        self._listen_thread = None
        self._model = None
        self._cooldown_until = 0.0  # ignore detections until this timestamp

    def _resolve_model(self):
        normalized_name = self.model_name.strip().lower().replace(" ", "_")
        model_info = openwakeword.models.get(normalized_name)
        if not model_info:
            available = ", ".join(sorted(openwakeword.models.keys()))
            raise ValueError(
                f"Unknown wake word model '{self.model_name}'. Available models: {available}"
            )
        return normalized_name, model_info["model_path"]

    @property
    def is_supported(self) -> bool:
        return _HAVE_WAKE_WORD

    @property
    def running(self) -> bool:
        return self._running

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block."""
        if self._running and not self._paused:
            self._audio_q.put(indata.copy())

    def _flush_queue(self):
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def _listen_loop(self):
        """Background thread loop that loads the model and processes audio chunks."""
        # Load model lazily in the thread to avoid blocking main thread at startup
        print(f"Loading openwakeword model '{self.model_name}'...")
        try:
            _, model_path = self._resolve_model()
            self._model = Model(wakeword_model_paths=[model_path])
            model_key = next(iter(self._model.models.keys()))
        except Exception as e:
            print(f"Failed to load openwakeword model: {e}")
            self._running = False
            return
            
        print("Wake word listener active.")
        
        while self._running:
            if self._paused:
                time.sleep(0.1)
                self._flush_queue() # keep queue empty while paused
                continue
                
            try:
                # Wait for audio data
                audio_chunk = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
                
            if not self._running:
                break
                
            # openwakeword expects 16kHz, 1-channel, int16 data
            # sounddevice gives us float32 [-1.0, 1.0] depending on dtype, let's process it
            audio_data_int16 = (audio_chunk[:, 0] * 32767).astype(np.int16)
            
            prediction = self._model.predict(audio_data_int16)
            
            # Predict returns a dict predicting scores for each model
            score = prediction.get(model_key, 0.0)
            
            if score > self.threshold:
                # Ignore detections during cooldown period (after resume)
                if time.time() < self._cooldown_until:
                    continue
                
                print(f"\nWake word detected! (score: {score:.2f})")
                self._flush_queue()
                self._model.reset()
                self._cooldown_until = time.time() + 4.0
                try:
                    self.callback()
                except Exception as e:
                    print(f"Error in wake word callback: {e}")

    def start(self):
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

    def _open_stream(self):
        """Open the microphone stream for wake word detection."""
        # openwakeword uses 16kHz sample rate, frame size ~1280 (80ms)
        self._stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="float32",
            blocksize=1280,
            callback=self._audio_callback,
        )
        self._stream.start()

    def _close_stream(self):
        """Close the microphone stream to release the audio device."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def stop(self):
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

    def pause(self):
        """Pause listening and release the microphone.

        Closing the stream ensures the OS no longer shows an active
        microphone indicator while the main recorder is taking over.
        """
        self._paused = True
        self._close_stream()

    def resume(self):
        """Resume listening and re-open the microphone stream."""
        self._flush_queue()  # Clear any old data
        # Reset model and set cooldown to prevent immediate re-trigger
        if self._model is not None:
            self._model.reset()
        self._cooldown_until = time.time() + 4.0
        try:
            self._open_stream()
        except Exception as e:
            print(f"Failed to reopen audio stream for wake word: {e}")
        self._paused = False
