# Windows ROCm + CTranslate2 (manuelle Anleitung)

Diese Anleitung beschreibt den nativen Windows-ROCm-Weg (ohne WSL) fuer `faster-whisper` mit selbst gebautem `ctranslate2`.

Getesteter Stand:
- Datum: 2026-03-03
- ROCm Windows: 7.2
- Python: 3.12 (cp312, wichtig)
- CTranslate2: 4.7.1

## 1) Voraussetzungen

1. AMD Windows Treiber/ROCm laut AMD-Doku installieren (Radeon/Ryzen ROCm auf Windows).
2. Eine Python-3.12-venv anlegen (nicht 3.13).
3. In dieser venv die ROCm-Windows Wheels aus AMD-Doku installieren:
   - `rocm`
   - `rocm-sdk-core`
   - `rocm-sdk-devel`
   - ROCm-PyTorch Wheels (`torch`, `torchaudio`, `torchvision`, cp312)
4. Visual Studio Build Tools + Windows SDK installieren:
   - MSVC C++ Build Tools
   - Windows 10/11 SDK (mit `rc.exe`/`mt.exe`)

Kurztest:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

## 2) Automatisierter Rebuild (empfohlen)

Im Repo:

```powershell
.\tools\build_ctranslate2_rocm_windows.ps1
```

Das Script erledigt:
- Suche der venv im aktuellen Verzeichnis (`.\.venv`, dann `.\venv`) oder Anlegen von `.\.venv`
- Optional automatische Installation der AMD-ROCm-Windows-Pakete (Guide-URLs, Python 3.12)
- Entpacken der `rocm_sdk_devel` Payload
- Mergen von `core` + `libraries` + `devel` unter `C:\rdev\_rocm_sdk_devel`
- Download der CTranslate2 Quellen (v4.7.1)
- Nachziehen benoetigter Third-Party Quellen (`spdlog`, `cpu_features`)
- HIP-Build + Install nach `<ROCM_VENV>\bin`/`<ROCM_VENV>\lib`
- Wheel-Build und `pip install --force-reinstall`
- Smoke-Test

## 3) App nativ mit ROCm starten

```powershell
$env:HOTKEY_TRANSCRIBER_BACKEND="native"
$env:HOTKEY_TRANSCRIBER_ROCM_ROOT="C:\rdev\_rocm_sdk_devel"
hotkey-transcriber
```

Optional fuer freie DLL-Verzeichnisse:

```powershell
$env:HOTKEY_TRANSCRIBER_DLL_DIRS="C:\rdev\_rocm_sdk_devel\bin;$((Resolve-Path .\.venv).Path)\bin"
```

## 4) Manuelle Verifikation

```powershell
.\.venv\Scripts\python.exe -c "import os, pathlib; os.add_dll_directory(r'C:\rdev\_rocm_sdk_devel\bin'); os.add_dll_directory(str(pathlib.Path(r'.\.venv\bin').resolve())); import ctranslate2; print(ctranslate2.__version__); print(ctranslate2.get_supported_compute_types('cuda'))"
```

`faster-whisper` GPU Test:

```powershell
.\.venv\Scripts\python.exe -c "import os, pathlib; os.add_dll_directory(r'C:\rdev\_rocm_sdk_devel\bin'); os.add_dll_directory(str(pathlib.Path(r'.\.venv\bin').resolve())); from faster_whisper import WhisperModel; m=WhisperModel('tiny.en', device='cuda', compute_type='float16'); print('ok')"
```

## 5) Typische Fehlerbilder

1. `ImportError: DLL load failed while importing _ext`
   - DLL-Pfade fehlen.
   - Setze `HOTKEY_TRANSCRIBER_ROCM_ROOT` und pruefe, dass `<venv>\bin` sowie ROCm `bin` in der DLL-Suche sind.

2. `cannot find ROCm device library`
   - Build ohne korrektes `--rocm-path` / `--rocm-device-lib-path`.
   - Script erneut laufen lassen.

3. `hip/hip_runtime.h file not found`
   - ROCm Include-Header nicht korrekt im gemergten Root.
   - Script erneut laufen lassen (kopiert `core\include` nach `C:\rdev\_rocm_sdk_devel\include`).

4. Python 3.13 in venv
   - AMD-Wheels in dieser Anleitung sind `cp312`.
   - Neue Python-3.12-venv verwenden.
