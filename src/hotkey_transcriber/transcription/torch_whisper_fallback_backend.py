"""
Torch Whisper Fallback Backend - OpenAI-Whisper (PyTorch) backend for AMD GPUs where CTranslate2/HIP is incompatible.

Architecture:
    ┌─────────────────────────────────────────┐
    │  TorchWhisperFallbackBackend            │
    │  ┌───────────────────────────────────┐  │
    │  │  TorchWhisperModel                │  │
    │  │  → wraps openai-whisper           │  │
    │  │  → matches faster_whisper API     │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  transcribe(audio, ...)           │  │
    │  │  → pads/trims 30s                 │  │
    │  │  → returns iter(_Segment), info   │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.torch_whisper_fallback_backend import TorchWhisperModel

    model = TorchWhisperModel(model_size="large-v3-turbo", device="cuda")
    segments, info = model.transcribe(audio_array, language="de")
"""

import os

# Enable ROCm AOTriton experimental flash/mem-efficient attention.
# The original startup crash was caused by PyQt5 DLL conflicts (now fixed),
# not AOTriton - enabling this gives ~2x faster inference on AMD iGPUs.
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

import numpy as np
import torch
import whisper


class _Segment:
    """Minimal segment object matching faster_whisper's interface."""

    __slots__ = ("text", "start", "end")

    def __init__(self, text: str, start: float = 0.0, end: float = 0.0):
        self.text = text
        self.start = start
        self.end = end


# Mapping from faster-whisper model names to openai-whisper names.
_MODEL_NAME_MAP: dict[str, str] = {
    "large-v3-turbo": "turbo",
}

# Models only available in CTranslate2/faster-whisper format.
_CT2_ONLY_MODELS: frozenset[str] = frozenset(
    {
        "distil-small.en",
        "distil-medium.en",
        "distil-large-v3",
    }
)


class TorchWhisperModel:
    """Wraps openai-whisper to provide the faster_whisper.WhisperModel interface."""

    def __init__(self, model_size: str, device: str = "cuda", compute_type: str = "float32"):
        if model_size in _CT2_ONLY_MODELS or "/" in model_size:
            raise ValueError(
                f"Modell '{model_size}' ist nur im CTranslate2-Format verfuegbar "
                f"und kann nicht mit dem torch-Backend verwendet werden. "
                f"Bitte ein Standard-Whisper-Modell waehlen (tiny, base, small, "
                f"medium, large-v3, large-v3-turbo)."
            )
        ow_name = _MODEL_NAME_MAP.get(model_size, model_size)
        self._fp16 = device != "cpu" and "float16" in compute_type
        self._model = whisper.load_model(ow_name, device=device)

    def transcribe(
        self,
        audio,
        language=None,
        vad_filter=True,
        beam_size=1,
        best_of=1,
        temperature=0,
        condition_on_previous_text=False,
        **kwargs,
    ):
        if isinstance(audio, np.ndarray):
            audio = audio.astype(np.float32)
            audio = whisper.pad_or_trim(torch.from_numpy(audio)).numpy()

        result = self._model.transcribe(
            audio,
            language=language,
            fp16=self._fp16,
            beam_size=beam_size,
            best_of=best_of,
            temperature=temperature,
            condition_on_previous_text=condition_on_previous_text,
        )

        segments = [
            _Segment(
                text=seg["text"],
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
            )
            for seg in result.get("segments", [])
        ]

        class _Info:
            pass

        info = _Info()
        info.language = result.get("language", language or "")

        return iter(segments), info
