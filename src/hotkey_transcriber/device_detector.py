import importlib
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
