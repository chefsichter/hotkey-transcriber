# Windows AMD-GPU Setup (natives ROCm + torch)

Diese Anleitung beschreibt den nativen Windows-ROCm-Weg fuer AMD-GPUs mit `openai-whisper` und PyTorch.

CTranslate2s HIP-Kernel stuerzen auf neueren AMD-GPUs ab (z.B. RDNA 4 / gfx1150), daher nutzt die App das torch-basierte `openai-whisper`-Backend statt `faster-whisper`/CTranslate2.

Getesteter Stand:
- Windows 11
- AMD Radeon 890M (gfx1150, RDNA 4)
- ROCm Windows: 7.2
- Python: 3.12 (cp312, erforderlich)
- PyTorch: 2.9.1+rocmsdk20260116

## 1) Voraussetzungen

1. **AMD Software: Adrenalin Edition** fuer Windows installieren (inkl. ROCm-Support), danach neu starten.
2. **Python 3.12** installieren (nicht 3.13 — AMD-ROCm-Wheels sind nur `cp312`).

## 2) Automatisierte Installation (empfohlen)

Im Repo:

```powershell
.\tools\install_windows.ps1 -AmdGpu -Autostart ask
```

Das Script erledigt:
- Erstellen einer Python-3.12-venv (`.venv`) im Repo
- Installation der ROCm-SDK-Pakete (`rocm_sdk_core`, `rocm_sdk_devel`, `rocm_sdk_libraries_custom`, `rocm` Meta)
- Installation der ROCm-PyTorch-Wheels (`torch`, `torchaudio`, `torchvision`, alle cp312)
- Installation von `openai-whisper`
- Installation des Projekts (`pip install -e .`)
- Verifikation des GPU-Zugriffs (`torch.cuda.is_available()`)
- Erstellen einer Startmenue-Verknuepfung

## 3) App starten

Ueber die Startmenue-Verknuepfung oder direkt:

```powershell
& ".\.venv\Scripts\hotkey-transcriber.exe"
```

Die App erkennt die AMD-GPU automatisch und nutzt das torch-Backend mit `float16`.

## 4) Manuelle Verifikation

Pruefen ob PyTorch die GPU erkennt:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Erwartete Ausgabe (Beispiel):
```
2.9.1+rocmsdk20260116
True
AMD Radeon 890M Graphics
```

Pruefen ob openai-whisper laedt:

```powershell
.\.venv\Scripts\python.exe -c "import whisper; m = whisper.load_model('tiny'); print('ok')"
```

## 5) Funktionsweise

Beim Start der App:
1. `backend_manager.py` erkennt eine AMD-GPU unter Windows via `Win32_VideoController`
2. `device_detector.py` bestaetigt ein CUDA/HIP-Device via CTranslate2
3. Die Kombination AMD-GPU + CUDA-Device + Windows loest `use_torch_whisper=True` aus
4. `object_loader.py` laedt `TorchWhisperModel` aus `torch_whisper_backend.py` statt `faster_whisper.WhisperModel`
5. Das torch-Backend nutzt `openai-whisper` mit `fp16=True` fuer optimale GPU-Performance

Die Umgebungsvariable `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1` wird automatisch gesetzt, um Flash/Memory-Efficient Attention auf ROCm zu aktivieren.

## 6) Verfuegbare Modelle

Das torch-Backend unterstuetzt Standard-OpenAI-Whisper-Modelle:
- `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`

Nicht verfuegbar mit dem torch-Backend:
- Distil-Modelle (`distil-small.en`, `distil-medium.en`, `distil-large-v3`) — nur CTranslate2-Format
- Eigene HuggingFace-Modelle (z.B. `TheChola/...`) — nur CTranslate2-Format

## 7) Typische Fehlerbilder

1. **`torch.cuda.is_available()` gibt `False` zurueck**
   - AMD-Treiber nicht installiert oder veraltet. AMD Software: Adrenalin Edition installieren und neu starten.
   - Falsche Python-Version. AMD-ROCm-Wheels erfordern Python 3.12.

2. **`No module named 'whisper'`**
   - `openai-whisper` nicht installiert. Ausfuehren: `.\.venv\Scripts\python.exe -m pip install openai-whisper`

3. **Langsame Transkription (mehrere Sekunden)**
   - Pruefen ob `float16` verwendet wird (Log-Meldung: "torch-Backend").
   - Falls aus einer pipx-Installation statt der venv gestartet, steht das torch-Backend nicht zur Verfuegung.

4. **Modell nicht verfuegbar Fehler**
   - Distil-Modelle und eigene HuggingFace-Modelle funktionieren nicht mit dem torch-Backend.
   - Auf ein Standard-Modell wechseln (z.B. `large-v3-turbo`).

5. **`UserWarning: Flash Efficient attention ... is still experimental`**
   - Wird automatisch behandelt via `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1`.

## 8) WSL-Alternative

Falls du `faster-whisper`/CTranslate2 ueber WSL bevorzugst (z.B. auf Hardware wo CTranslate2s HIP-Kernel funktionieren), siehe das WSL-Setup in der [README](../README.de.md).
