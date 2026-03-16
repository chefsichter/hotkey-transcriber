import json
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from huggingface_hub import hf_hub_download

_MODEL_TO_HF_FILE = {
    # Full precision
    "tiny": ("ggerganov/whisper.cpp", "ggml-tiny.bin"),
    "base": ("ggerganov/whisper.cpp", "ggml-base.bin"),
    "small": ("ggerganov/whisper.cpp", "ggml-small.bin"),
    "medium": ("ggerganov/whisper.cpp", "ggml-medium.bin"),
    "large-v3": ("ggerganov/whisper.cpp", "ggml-large-v3.bin"),
    "large-v3-turbo": ("ggerganov/whisper.cpp", "ggml-large-v3-turbo.bin"),
    # Quantized (q8_0 ≈ lossless, q5_0 ≈ 30% kleiner/schneller, minimaler Qualitätsverlust)
    "large-v3-turbo-q8_0": ("ggerganov/whisper.cpp", "ggml-large-v3-turbo-q8_0.bin"),
    "large-v3-turbo-q5_0": ("ggerganov/whisper.cpp", "ggml-large-v3-turbo-q5_0.bin"),
    "large-v3-q8_0": ("ggerganov/whisper.cpp", "ggml-large-v3-q8_0.bin"),
    "large-v3-q5_0": ("ggerganov/whisper.cpp", "ggml-large-v3-q5_0.bin"),
    # German-specific
    "cstr/whisper-large-v3-turbo-german-ggml": (
        "cstr/whisper-large-v3-turbo-german-ggml",
        "ggml-model.bin",
    ),
}
_CT2_ONLY_MODELS = {
    "distil-small.en",
    "distil-medium.en",
    "distil-large-v3",
    "TheChola/whisper-large-v3-turbo-german-faster-whisper",
}


@dataclass
class _Segment:
    text: str


class WhisperCppModel:
    def __init__(self, model_size: str):
        if model_size in _CT2_ONLY_MODELS or model_size not in _MODEL_TO_HF_FILE:
            raise ValueError(
                f"Modell '{model_size}' wird vom whisper.cpp-Backend nicht unterstuetzt."
            )
        self._model_size = model_size
        self._model_path = self._resolve_model_path(model_size)
        self._cli_path = self._resolve_cli_path()

    def _resolve_model_path(self, model_size: str) -> str:
        repo_id, file_name = _MODEL_TO_HF_FILE[model_size]
        return hf_hub_download(repo_id=repo_id, filename=file_name)

    def _resolve_cli_path(self) -> str:
        explicit = os.getenv("HOTKEY_TRANSCRIBER_WHISPER_CPP_CLI", "").strip()
        candidates = []
        if explicit:
            candidates.append(Path(explicit))

        local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home()))
        base = Path(local_appdata) / "hotkey-transcriber" / "whisper.cpp"
        drive = os.environ.get("SystemDrive", "C:")
        if not drive.endswith("\\"):
            drive = f"{drive}\\"
        short_base = Path(drive) / "htwcpp"
        candidates.extend(
            [
                base / "build" / "bin" / "Release" / "whisper-cli.exe",
                base / "build" / "bin" / "whisper-cli.exe",
                base / "whisper-cli.exe",
                short_base / "build" / "bin" / "Release" / "whisper-cli.exe",
                short_base / "build" / "bin" / "whisper-cli.exe",
            ]
        )

        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

        raise FileNotFoundError(
            "whisper-cli.exe nicht gefunden. Fuehre tools/install_windows.ps1 -AmdGpu aus."
        )

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
        del vad_filter, condition_on_previous_text

        import os

        cpu_count = os.cpu_count() or 4
        # With Vulkan active the GPU handles heavy computation; 4 threads suffice for
        # CPU-side pre/post-processing and avoids contention with Vulkan driver threads.
        threads = min(max(cpu_count // 6, 4), 8)

        audio_f32 = np.asarray(audio, dtype=np.float32)
        audio_i16 = np.clip(audio_f32, -1.0, 1.0)
        audio_i16 = (audio_i16 * 32767.0).astype(np.int16)

        with tempfile.TemporaryDirectory(prefix="hotkey-transcriber-whispercpp-") as td:
            wav_path = Path(td) / "input.wav"
            out_prefix = Path(td) / "result"
            out_json = Path(f"{out_prefix}.json")

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_i16.tobytes())

            lang = "auto" if not language else str(language)
            cmd = [
                self._cli_path,
                "-m", self._model_path,
                "-f", str(wav_path),
                "-oj",
                "-of", str(out_prefix),
                "-nt",
                "-np",
                "-t", str(threads),
                "-bs", str(max(1, beam_size)),
                "-bo", str(max(1, best_of)),
                "-tp", str(float(temperature)),
                "-nf",
                "-l", lang,
            ]
            # Flash attention causes quality regressions for non-English languages (issue #3020).
            if lang == "en":
                cmd.append("-fa")
            else:
                cmd.append("-nfa")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"whisper.cpp fehlgeschlagen (exit={proc.returncode}): {proc.stderr.strip()}"
                )
            if not out_json.is_file():
                raise RuntimeError("whisper.cpp hat keine JSON-Ausgabe erzeugt.")

            data = json.loads(out_json.read_text(encoding="utf-8"))
            text = str(data.get("text", "")).strip()
            if not text:
                # Older whisper.cpp JSON format stores text per segment.
                segs = data.get("transcription", [])
                text = " ".join(str(s.get("text", "")).strip() for s in segs).strip()

        return iter([_Segment(text=text)] if text else []), {"language": language}
