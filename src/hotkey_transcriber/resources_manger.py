from pathlib import Path
import importlib.resources

def get_microphone_icon_path():
    try:
        # Wenn "resources" ein Python-Paket (mit __init__.py) ist:
        with importlib.resources.path("resources.icon", "microphone.png") as icon_path:
            return str(icon_path)
    except Exception:
        # Fallback: relative Suche basierend auf __file__
        current_file = Path(__file__).resolve()
        icon_path = current_file.parent / "resources" / "icon" / "microphone.png"
        return str(icon_path)
