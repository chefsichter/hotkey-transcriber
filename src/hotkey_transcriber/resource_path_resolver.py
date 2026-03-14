"""
Resource Path Resolver - Resolve paths to bundled application resources (icons, etc.).

Architecture:
    ┌─────────────────────────────────────────┐
    │  ResourcePathResolver                   │
    │  ┌───────────────────────────────────┐  │
    │  │  get_microphone_icon_path()       │  │
    │  │  → importlib.resources lookup     │  │
    │  │  → fallback: __file__-relative    │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.resource_path_resolver import get_microphone_icon_path

    icon_path = get_microphone_icon_path()
"""

import importlib.resources
from pathlib import Path


def get_microphone_icon_path() -> str:
    """Return the absolute path to the microphone icon file."""
    try:
        with importlib.resources.path("resources.icon", "microphone.png") as icon_path:
            return str(icon_path)
    except Exception:
        current_file = Path(__file__).resolve()
        icon_path = current_file.parent / "resources" / "icon" / "microphone.png"
        return str(icon_path)
