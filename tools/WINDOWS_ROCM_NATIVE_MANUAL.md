# Windows ROCm + CTranslate2 (manual guide)

This guide describes the native Windows ROCm path (without WSL) for `faster-whisper` using a self-built `ctranslate2`.

Tested setup:
- Date: 2026-03-03
- ROCm Windows: 7.2
- Python: 3.12 (cp312, important)
- CTranslate2: 4.7.1

Reference (official AMD Windows guide):
- https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html

## 1) Prerequisites

1. Install AMD Windows driver/ROCm according to AMD docs (Radeon/Ryzen ROCm on Windows).
2. Use a Python 3.12 venv (not 3.13).
3. In that venv, install ROCm Windows packages from AMD docs:
   - `rocm`
   - `rocm-sdk-core`
   - `rocm-sdk-devel`
   - ROCm PyTorch wheels (`torch`, `torchaudio`, `torchvision`, cp312)
4. Install Visual Studio Build Tools + Windows SDK:
   - MSVC C++ Build Tools
   - Windows 10/11 SDK (with `rc.exe` and `mt.exe`)

Quick test:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

## 2) Automated rebuild (recommended)

In this repository:

```powershell
.\tools\build_ctranslate2_rocm_windows.ps1
```

The script does:
- Detect venv in current directory (`.\.venv`, then `.\venv`) or create `.\.venv`
- Optional automatic install of AMD ROCm Windows packages (guide URLs, Python 3.12)
- Extract the `rocm_sdk_devel` payload
- Merge `core` + `libraries` + `devel` into `C:\rdev\_rocm_sdk_devel`
- Download CTranslate2 sources (v4.7.1)
- Download required third-party sources (`spdlog`, `cpu_features`)
- HIP build + install to `<ROCM_VENV>\bin` and `<ROCM_VENV>\lib`
- Build wheel and `pip install --force-reinstall`
- Smoke test

## 3) Start app with native ROCm

```powershell
$env:HOTKEY_TRANSCRIBER_BACKEND="native"
$env:HOTKEY_TRANSCRIBER_ROCM_ROOT="$((Resolve-Path .\build\rocm-win-ct2\_rocm_sdk_devel).Path)"
& ".\.venv\Scripts\hotkey-transcriber.exe"
```

Optional explicit DLL directories:

```powershell
$env:HOTKEY_TRANSCRIBER_DLL_DIRS="$((Resolve-Path .\build\rocm-win-ct2\_rocm_sdk_devel\bin).Path);$((Resolve-Path .\.venv).Path)\bin"
```

## 4) Manual verification

```powershell
.\.venv\Scripts\python.exe -c "import os, pathlib; os.add_dll_directory(r'C:\rdev\_rocm_sdk_devel\bin'); os.add_dll_directory(str(pathlib.Path(r'.\.venv\bin').resolve())); import ctranslate2; print(ctranslate2.__version__); print(ctranslate2.get_supported_compute_types('cuda'))"
```

`faster-whisper` GPU test:

```powershell
.\.venv\Scripts\python.exe -c "import os, pathlib; os.add_dll_directory(r'C:\rdev\_rocm_sdk_devel\bin'); os.add_dll_directory(str(pathlib.Path(r'.\.venv\bin').resolve())); from faster_whisper import WhisperModel; m=WhisperModel('tiny.en', device='cuda', compute_type='float16'); print('ok')"
```

## 5) Common issues

1. `ImportError: DLL load failed while importing _ext`
   - DLL paths are missing.
   - Set `HOTKEY_TRANSCRIBER_ROCM_ROOT` and verify both `<venv>\bin` and ROCm `bin` are in DLL search path.

2. `cannot find ROCm device library`
   - Build ran without correct `--rocm-path` / `--rocm-device-lib-path`.
   - Run the script again.

3. `hip/hip_runtime.h file not found`
   - ROCm include headers are missing in merged root.
   - Run the script again (it copies `core\include` to `C:\rdev\_rocm_sdk_devel\include`).

4. Python 3.13 in venv
   - AMD wheels in this flow are `cp312`.
   - Create/use a Python 3.12 venv.
