import importlib
import os
import platform
import sys
from pathlib import Path


def _configure_windows_dll_search_path() -> None:
    if platform.system().lower() != "windows":
        return

    candidates = []

    # Explicit override for custom ROCm root.
    rocm_root = os.getenv("HOTKEY_TRANSCRIBER_ROCM_ROOT")
    if rocm_root:
        candidates.append(Path(rocm_root) / "bin")

    # ROCm SDK root variable used by HIP tooling.
    rocm_env = os.getenv("ROCM_PATH")
    if rocm_env:
        candidates.append(Path(rocm_env) / "bin")

    # Venv local runtime DLLs (ctranslate2.dll gets installed here in this setup).
    candidates.append(Path(sys.prefix) / "bin")

    # Optional additional DLL directories (os.pathsep separated).
    extra_dirs = os.getenv("HOTKEY_TRANSCRIBER_DLL_DIRS", "")
    if extra_dirs:
        for raw in extra_dirs.split(os.pathsep):
            raw = raw.strip()
            if raw:
                candidates.append(Path(raw))

    seen = set()
    for path in candidates:
        path = path.resolve()
        if path in seen or not path.is_dir():
            continue
        seen.add(path)

        # Keep compatibility for extension-module loading and subprocesses.
        os.environ["PATH"] = f"{path}{os.pathsep}{os.environ.get('PATH', '')}"
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(path))
            except (FileNotFoundError, OSError):
                pass


_configure_windows_dll_search_path()

import ctranslate2 as ct2

# utils-Wrapper
_utils_mod = (
    importlib.import_module("ctranslate2.utils")
    if importlib.util.find_spec("ctranslate2.utils")
    else ct2
)
_get_supported_compute_types = getattr(
    _utils_mod, "get_supported_compute_types", ct2.get_supported_compute_types
)


def detect_device() -> str:
    """
    Gibt 'cuda', 'hip' oder 'cpu' zurück.

    * probiert zuerst native CUDA-Zählung
    * fängt ValueError **und** RuntimeError ab
    * funktioniert ohne torch/rocminfo
    """
    # 1) Schneller Check, ob GPUs mit lauffähigem Treiber sichtbar sind
    try:
        if getattr(ct2, "get_cuda_device_count", lambda: 0)() > 0:
            return "cuda"                         # alles okay, CUDA nutzbar
    except RuntimeError:
        # z. B. „driver version is insufficient …“ → weiter zum Fallback
        pass

    # 2) Prüfe per Compute-Typ-Abfrage, ob HIP oder CUDA prinzipiell unterstützt wird
    for dev in ("hip", "cuda"):                  # Reihenfolge beibehalten
        try:
            _get_supported_compute_types(dev)    # RuntimeError ⇒ Treiberproblem
            return dev
        except (ValueError, RuntimeError):
            continue

    # 3) Nichts davon verfügbar → CPU
    return "cpu"
