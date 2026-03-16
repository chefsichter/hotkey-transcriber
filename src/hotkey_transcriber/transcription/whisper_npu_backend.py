"""Whisper NPU backend via AMD ONNX/VitisAI.

Runs inference in the ryzen-ai-1.7.0 conda environment via a persistent
subprocess (tools/whisper_npu_server.py).  The main process downloads ONNX
models, starts the server, and communicates via line-delimited JSON on
stdin/stdout.  Audio is transferred through a temporary WAV file whose path
is included in each request.
"""

import json
import os
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from huggingface_hub import snapshot_download

# Maps model name → (amd_repo_id, encoder_filename, decoder_filename, openai_hf_id)
# The AMD repos contain ONNX exports; the openai HF ID is used for tokenizer/feature extractor.
_MODEL_TO_AMD_REPO: dict[str, tuple[str, str, str, str]] = {
    "tiny":           ("amd/whisper-tiny-onnx-npu",        "tiny_encoder.onnx",      "tiny_decoder.onnx",      "openai/whisper-tiny"),
    "base":           ("amd/whisper-base-onnx-npu",        "base_encoder.onnx",      "base_decoder.onnx",      "openai/whisper-base"),
    "small":          ("amd/whisper-small-onnx-npu",       "encoder_model.onnx",     "decoder_model.onnx",     "openai/whisper-small"),
    "medium":         ("amd/whisper-medium-onnx-npu",      "encoder_model.onnx",     "decoder_model.onnx",     "openai/whisper-medium"),
    "large-v3":       ("amd/whisper-large-v3-onnx-npu",    "large_v3_encoder.onnx",  "large_v3_decoder.onnx",  "openai/whisper-large-v3"),
    "large-v3-turbo": ("amd/whisper-large-turbo-onnx-npu", "encoder_model.onnx",     "decoder_model.onnx",     "openai/whisper-large-v3-turbo"),
}

_CONDA_PYTHON_CANDIDATES = [
    Path(r"C:\ProgramData\miniconda3\envs\ryzen-ai-1.7.0\python.exe"),
    Path.home() / ".conda" / "envs" / "ryzen-ai-1.7.0" / "python.exe",
]

_VAIP_CONFIG_CANDIDATES = [
    Path(r"C:\Program Files\RyzenAI\1.7.0\voe-4.0-win_amd64\vaip_config.json"),
    Path(r"C:\Program Files\RyzenAI\1.6.1\voe-4.0-win_amd64\vaip_config.json"),
    Path(r"C:\Program Files\RyzenAI\1.5.0\voe-4.0-win_amd64\vaip_config.json"),
]


@dataclass
class _Segment:
    text: str


def _find_conda_python() -> Path:
    candidates = list(_CONDA_PYTHON_CANDIDATES)
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        candidates.append(
            Path(local_appdata) / "conda" / "conda" / "envs" / "ryzen-ai-1.7.0" / "python.exe"
        )
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Python-Interpreter fuer ryzen-ai-1.7.0 Conda-Umgebung nicht gefunden. "
        "Stelle sicher, dass AMD Ryzen AI Software 1.7.0 installiert ist und "
        "Option [4] im Installer ausgefuehrt wurde."
    )


def _find_vaip_config() -> Path:
    for c in _VAIP_CONFIG_CANDIDATES:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "vaip_config.json nicht gefunden. Stelle sicher, dass AMD Ryzen AI Software "
        "installiert ist (Standard: C:\\Program Files\\RyzenAI\\1.7.0\\voe-4.0-win_amd64\\vaip_config.json)."
    )


def _find_server_script() -> Path:
    # Works for editable installs: src/hotkey_transcriber/transcription/ → repo root / tools/
    repo_root = Path(__file__).parent.parent.parent.parent
    script = repo_root / "tools" / "whisper_npu_server.py"
    if script.is_file():
        return script
    raise FileNotFoundError(
        f"whisper_npu_server.py nicht gefunden unter: {script}. "
        "Stelle sicher, dass das Projekt aus dem Repository-Verzeichnis heraus installiert wurde."
    )


class WhisperNpuModel:
    """Whisper model running encoder on AMD NPU via VitisAI EP, decoder on CPU.

    Starts a persistent subprocess in the ryzen-ai-1.7.0 conda environment
    that loads the ONNX models and processes inference requests via JSON lines.
    The first startup may take several minutes while the NPU compiles the encoder.
    """

    def __init__(self, model_size: str):
        if model_size not in _MODEL_TO_AMD_REPO:
            supported = list(_MODEL_TO_AMD_REPO.keys())
            raise ValueError(
                f"Modell '{model_size}' wird vom NPU-ONNX-Backend nicht unterstuetzt. "
                f"Unterstuetzte Modelle: {supported}"
            )

        repo_id, enc_file, dec_file, hf_model_id = _MODEL_TO_AMD_REPO[model_size]

        print(f"[NPU] Lade ONNX-Modelle fuer '{model_size}' (falls noetig)...", flush=True)
        model_dir = Path(snapshot_download(
            repo_id=repo_id,
            allow_patterns=["*.onnx", "*.onnx.data"],
        ))

        encoder_path = model_dir / enc_file
        decoder_path = model_dir / dec_file

        if not encoder_path.is_file():
            raise FileNotFoundError(f"[NPU] Encoder-Modell nicht gefunden: {encoder_path}")
        if not decoder_path.is_file():
            raise FileNotFoundError(f"[NPU] Decoder-Modell nicht gefunden: {decoder_path}")

        conda_python = _find_conda_python()
        vaip_config = _find_vaip_config()
        server_script = _find_server_script()

        cache_dir = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "hotkey-transcriber"
            / "npu-cache"
        )
        cache_dir.mkdir(parents=True, exist_ok=True)

        print("[NPU] Starte NPU-Inference-Server (erste NPU-Kompilierung kann Minuten dauern)...", flush=True)

        cmd = [
            str(conda_python),
            str(server_script),
            "--encoder", str(encoder_path),
            "--decoder", str(decoder_path),
            "--model-id", hf_model_id,
            "--vaip-config", str(vaip_config),
            "--cache-dir", str(cache_dir),
        ]

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Block until server signals {"status": "ready"}.
        # VitisAI EP writes verbose debug output to stdout during NPU compilation.
        # Show a spinner with elapsed time on a background thread (independent of line rate).
        # The reader thread keeps running after startup so transcribe() reads from the same queue
        # (avoids race condition between reader thread and readline() competing on the same pipe).
        import time
        import queue

        start_time = time.time()
        self._line_queue: queue.Queue = queue.Queue()

        def _reader():
            for line in self._proc.stdout:
                self._line_queue.put(line)
            self._line_queue.put(None)  # Sentinel: pipe closed

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        spinner_chars = ["|", "/", "-", "\\"]
        spinner_idx = 0
        status = None

        while True:
            # Update spinner every 0.1s regardless of line rate
            try:
                line = self._line_queue.get(timeout=0.1)
            except queue.Empty:
                elapsed = int(time.time() - start_time)
                char = spinner_chars[spinner_idx % len(spinner_chars)]
                spinner_idx += 1
                print(f"\r{char} [NPU] Kompiliere Encoder fuer NPU... {elapsed}s", end="", flush=True)
                continue

            if line is None:
                # Pipe closed — server exited unexpectedly
                self._proc.wait()
                print()
                raise RuntimeError(
                    f"[NPU] NPU-Server-Prozess unerwartet beendet (exit={self._proc.returncode})."
                )
            line = line.strip()
            if not line:
                continue
            try:
                status = json.loads(line)
                break  # Got valid JSON — done
            except json.JSONDecodeError:
                # VitisAI debug line — just keep spinning
                elapsed = int(time.time() - start_time)
                char = spinner_chars[spinner_idx % len(spinner_chars)]
                spinner_idx += 1
                print(f"\r{char} [NPU] Kompiliere Encoder fuer NPU... {elapsed}s", end="", flush=True)

        print(f"\r[NPU] Encoder-Kompilierung abgeschlossen ({int(time.time() - start_time)}s).      ", flush=True)

        if status.get("status") != "ready":
            self._proc.terminate()
            if "error" in status:
                raise RuntimeError(f"[NPU] NPU-Server Fehler beim Start: {status['error']}")
            raise RuntimeError(f"[NPU] NPU-Server nicht bereit: {status}")

        self._lock = threading.Lock()
        print("[NPU] NPU-Server bereit.", flush=True)

    def transcribe(
        self,
        audio,
        language=None,
        vad_filter=True,
        beam_size=1,
        best_of=1,
        temperature=0,
        condition_on_previous_text=False,
    ):
        del vad_filter, beam_size, best_of, temperature, condition_on_previous_text

        audio_f32 = np.asarray(audio, dtype=np.float32)
        audio_i16 = np.clip(audio_f32, -1.0, 1.0)
        audio_i16 = (audio_i16 * 32767.0).astype(np.int16)

        with tempfile.TemporaryDirectory(prefix="hotkey-transcriber-npu-") as td:
            wav_path = Path(td) / "input.wav"

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_i16.tobytes())

            lang = "auto" if not language else str(language)
            request = json.dumps({"wav_path": str(wav_path), "language": lang})

            # Lock ensures requests are processed one at a time
            with self._lock:
                self._proc.stdin.write(request + "\n")
                self._proc.stdin.flush()
                # Read from the shared queue (reader thread owns the pipe; direct readline would race)
                result = None
                while True:
                    response_line = self._line_queue.get()  # blocks until next line or sentinel
                    if response_line is None:
                        raise RuntimeError("[NPU] NPU-Server-Prozess unerwartet beendet.")
                    response_line = response_line.strip()
                    if not response_line:
                        continue
                    try:
                        result = json.loads(response_line)
                        break
                    except json.JSONDecodeError:
                        continue  # Skip debug output
            # WAV temp dir cleaned up here (after server has already read and processed the file)

        if "error" in result:
            raise RuntimeError(f"[NPU] NPU-Server Fehler: {result['error']}")

        text = result.get("text", "").strip()
        return iter([_Segment(text=text)] if text else []), {"language": language}

    def __del__(self):
        try:
            if hasattr(self, "_proc") and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass
