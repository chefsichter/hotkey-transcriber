"""
Compute Device Detector - Probe CTranslate2 to determine whether CUDA, HIP, or CPU is available.

Architecture:
    ┌─────────────────────────────────────────┐
    │  ComputeDeviceDetector                  │
    │  ┌───────────────────────────────────┐  │
    │  │  Windows DLL path setup           │  │
    │  │  → ROCm/CUDA DLLs added to PATH   │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  detect_device()                  │  │
    │  │  → tries CUDA count               │  │
    │  │  → tries HIP/CUDA compute types   │  │
    │  │  → falls back to "cpu"            │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.compute_device_detector import detect_device

    device = detect_device()  # returns "cuda", "hip", or "cpu"
"""

import contextlib
import importlib
import importlib.util
import os
import platform
import sys
from pathlib import Path


def _configure_windows_dll_search_path() -> None:
    if platform.system().lower() != "windows":
        return

    candidates = []

    rocm_root = os.getenv("HOTKEY_TRANSCRIBER_ROCM_ROOT")
    if rocm_root:
        candidates.append(Path(rocm_root) / "bin")

    rocm_env = os.getenv("ROCM_PATH")
    if rocm_env:
        candidates.append(Path(rocm_env) / "bin")

    candidates.append(Path(sys.prefix) / "bin")

    extra_dirs = os.getenv("HOTKEY_TRANSCRIBER_DLL_DIRS", "")
    if extra_dirs:
        for raw in extra_dirs.split(os.pathsep):
            raw = raw.strip()
            if raw:
                candidates.append(Path(raw))

    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve()
        if path in seen or not path.is_dir():
            continue
        seen.add(path)

        os.environ["PATH"] = f"{path}{os.pathsep}{os.environ.get('PATH', '')}"
        if hasattr(os, "add_dll_directory"):
            with contextlib.suppress(FileNotFoundError, OSError):
                os.add_dll_directory(str(path))


_configure_windows_dll_search_path()

import ctranslate2 as ct2  # noqa: E402

_utils_mod = (
    importlib.import_module("ctranslate2.utils")
    if importlib.util.find_spec("ctranslate2.utils")
    else ct2
)
_get_supported_compute_types = getattr(
    _utils_mod, "get_supported_compute_types", ct2.get_supported_compute_types
)


def detect_device() -> str:
    """Return 'cuda', 'hip', or 'cpu' based on available hardware and drivers."""
    try:
        if getattr(ct2, "get_cuda_device_count", lambda: 0)() > 0:
            return "cuda"
    except RuntimeError:
        pass

    for dev in ("hip", "cuda"):
        try:
            _get_supported_compute_types(dev)
            return dev
        except (ValueError, RuntimeError):
            continue

    return "cpu"
