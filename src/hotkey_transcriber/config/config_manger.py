import json
import os

from pathlib import Path

CONFIG_DIR = Path(__file__).parent
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def load_config():
    """Liest das Config-File ein und gibt ein Dict zurück."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_config(cfg: dict):
    """Speichert das Dict als JSON ins Config-File."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
