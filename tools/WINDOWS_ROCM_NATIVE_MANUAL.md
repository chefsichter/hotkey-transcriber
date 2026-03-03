# Windows AMD GPU Setup (native ROCm + torch)

This guide describes the native Windows ROCm path for AMD GPUs using `openai-whisper` with PyTorch.

CTranslate2's HIP kernels crash on newer AMD GPUs (e.g. RDNA 4 / gfx1150), so the app uses the torch-based `openai-whisper` backend instead of `faster-whisper`/CTranslate2.

Tested setup:
- Windows 11
- AMD Radeon 890M (gfx1150, RDNA 4)
- ROCm Windows: 7.2
- Python: 3.12 (cp312, required)
- PyTorch: 2.9.1+rocmsdk20260116

## 1) Prerequisites

1. Install **AMD Software: Adrenalin Edition** for Windows (includes ROCm support), then reboot.
2. Install **Python 3.12** (not 3.13 — AMD ROCm wheels are `cp312` only).

## 2) Automated install (recommended)

In this repository:

```powershell
.\tools\install_windows.ps1 -AmdGpu -Autostart ask
```

The script does:
- Create a Python 3.12 venv (`.venv`) in the repo
- Install ROCm SDK packages (`rocm_sdk_core`, `rocm_sdk_devel`, `rocm_sdk_libraries_custom`, `rocm` meta)
- Install ROCm PyTorch wheels (`torch`, `torchaudio`, `torchvision`, all cp312)
- Install `openai-whisper`
- Install the project (`pip install -e .`)
- Verify GPU access (`torch.cuda.is_available()`)
- Create a Start Menu shortcut

## 3) Start the app

Via Start Menu shortcut, or directly:

```powershell
& ".\.venv\Scripts\hotkey-transcriber.exe"
```

The app auto-detects the AMD GPU and uses the torch backend with `float16`.

## 4) Manual verification

Check that PyTorch sees the GPU:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Expected output (example):
```
2.9.1+rocmsdk20260116
True
AMD Radeon 890M Graphics
```

Check that openai-whisper loads:

```powershell
.\.venv\Scripts\python.exe -c "import whisper; m = whisper.load_model('tiny'); print('ok')"
```

## 5) How it works

When the app starts:
1. `backend_manager.py` detects an AMD GPU on Windows via `Win32_VideoController`
2. `device_detector.py` confirms a CUDA/HIP device is available via CTranslate2
3. The combination of AMD GPU + CUDA device + Windows triggers `use_torch_whisper=True`
4. `object_loader.py` loads `TorchWhisperModel` from `torch_whisper_backend.py` instead of `faster_whisper.WhisperModel`
5. The torch backend uses `openai-whisper` with `fp16=True` for optimal GPU performance

The environment variable `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1` is set automatically to enable flash/memory-efficient attention on ROCm.

## 6) Available models

The torch backend supports standard OpenAI Whisper models:
- `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`

Not available with the torch backend:
- Distil models (`distil-small.en`, `distil-medium.en`, `distil-large-v3`) — CTranslate2 format only
- Custom HuggingFace models (e.g. `TheChola/...`) — CTranslate2 format only

## 7) Common issues

1. **`torch.cuda.is_available()` returns `False`**
   - AMD driver not installed or outdated. Install AMD Software: Adrenalin Edition and reboot.
   - Wrong Python version. AMD ROCm wheels require Python 3.12.

2. **`No module named 'whisper'`**
   - `openai-whisper` not installed. Run: `.\.venv\Scripts\python.exe -m pip install openai-whisper`

3. **Slow transcription (several seconds)**
   - Check that `float16` is being used (look for log message: "torch-Backend").
   - If running from a pipx install instead of the venv, the torch backend won't be available.

4. **Model not available error**
   - Distil models and custom HuggingFace models don't work with the torch backend.
   - Switch to a standard model (e.g. `large-v3-turbo`).

5. **`UserWarning: Flash Efficient attention ... is still experimental`**
   - This is handled automatically via `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1`.

## 8) WSL alternative

If you prefer using `faster-whisper`/CTranslate2 (e.g. on hardware where CTranslate2's HIP kernels work), see the WSL setup in the main [README](../README.md).
