from pathlib import Path


def get_microphone_icon_path():
    project_root = Path(__file__).parents[2]
    icon_path   = project_root / "resources" / "icon" / "microphone.png"
    return str(icon_path)
