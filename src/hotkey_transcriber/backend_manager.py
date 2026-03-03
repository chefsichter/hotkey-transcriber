import os
import platform
import subprocess
import sys

from hotkey_transcriber.device_detector import detect_device


def _run(cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()


def _find_rocm_root():
    """Return the ROCm installation directory, or None."""
    import glob

    # Explicit symlink first
    if os.path.isdir("/opt/rocm"):
        return "/opt/rocm"

    # Versioned directories (e.g. /opt/rocm-7.2.0)
    candidates = sorted(glob.glob("/opt/rocm-*"), reverse=True)
    for c in candidates:
        if os.path.isdir(c):
            return c

    return None


def is_linux_amd_gpu():
    if sys.platform != "linux":
        return False

    if _find_rocm_root() is not None:
        return True

    try:
        lspci = _run(["lspci"])
        for line in lspci.splitlines():
            lower = line.lower()
            if any(k in lower for k in ("vga", "3d", "display")):
                if "amd" in lower or "radeon" in lower:
                    return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return False


def is_windows_amd_gpu():
    if platform.system().lower() != "windows":
        return False

    try:
        names = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ';'",
            ]
        ).lower()
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

    return ("amd" in names) or ("radeon" in names)


def _wsl_available():
    try:
        _run(["wsl.exe", "--status"])
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _wsl_rocm_ready():
    if not _wsl_available():
        return False

    probe = (
        "source ~/.hotkey-transcriber-wsl/bin/activate 2>/dev/null || true\n"
        "VENV_LIB=\"$HOME/.hotkey-transcriber-wsl/lib\"\n"
        "ROCM_LLVM_LIB=\"/opt/rocm/lib/llvm/lib\"\n"
        "ROCM_LIB=\"/opt/rocm/lib\"\n"
        "export LD_LIBRARY_PATH=\"$VENV_LIB:$ROCM_LLVM_LIB:$ROCM_LIB:$LD_LIBRARY_PATH\"\n"
        "export LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=UTF-8\n"
        "python3 - <<'PY'\n"
        "import sys\n"
        "try:\n"
        " import ctranslate2 as ct2\n"
        " ok = False\n"
        " try:\n"
        "  ok = ct2.get_cuda_device_count() > 0\n"
        " except Exception:\n"
        "  ok = False\n"
        " if not ok:\n"
        "  try:\n"
        "   ct2.get_supported_compute_types('hip')\n"
        "   ok = True\n"
        "  except Exception:\n"
        "   ok = False\n"
        " if ok:\n"
        "  sys.exit(0)\n"
        "except Exception:\n"
        " pass\n"
        "try:\n"
        " import subprocess\n"
        " rc = subprocess.call(['rocminfo'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        " sys.exit(0 if rc == 0 else 3)\n"
        "except Exception:\n"
        " sys.exit(1)\n"
        "PY"
    )
    try:
        subprocess.check_call(
            ["wsl.exe", "-e", "bash", "-lc", probe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def resolve_backend(config):
    selected = os.getenv("HOTKEY_TRANSCRIBER_BACKEND", config.get("backend", "auto"))

    if selected not in ("auto", "native", "wsl_amd"):
        selected = "auto"

    if selected == "auto":
        if is_windows_amd_gpu() and _wsl_rocm_ready():
            selected = "wsl_amd"
        else:
            selected = "native"

    if selected == "wsl_amd":
        print("🎮 AMD GPU unter Windows erkannt. Nutze WSL-Backend.")
        return {
            "backend": "wsl_amd",
            "device": "cpu",
            "compute_type": "float32",
        }

    device = detect_device()
    compute_type = "float16" if device == "cuda" else "float32"

    # Linux + AMD GPU: use CTranslate2/faster-whisper with ROCm (no torch backend)
    if sys.platform == "linux" and is_linux_amd_gpu() and device != "cpu":
        print("🎮 AMD GPU unter Linux erkannt. Nutze ROCm/CTranslate2-Backend.")
        return {
            "backend": "native",
            "device": device,
            "compute_type": "float16",
            "use_torch_whisper": False,
        }

    # CTranslate2's HIP kernels crash on RDNA 4 (gfx1150) and possibly other
    # newer AMD GPUs on Windows.  Use the torch-based openai-whisper backend
    # when we detect an AMD GPU with a CUDA/HIP device on Windows.
    use_torch = (
        selected == "native"
        and is_windows_amd_gpu()
        and device == "cuda"
    )

    return {
        "backend": "native",
        "device": device,
        "compute_type": compute_type,
        "use_torch_whisper": use_torch,
    }
