"""
Config Manager - Load and save the application configuration as JSON.

Architecture:
    ┌─────────────────────────────────────────┐
    │  ConfigManager                          │
    │  ┌───────────────────────────────────┐  │
    │  │  load_config()                    │  │
    │  │  → reads config.json → dict       │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  save_config(cfg)                 │  │
    │  │  → writes dict → config.json      │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.config.config_manager import load_config, save_config

    cfg = load_config()
    cfg["model_size"] = "large-v3-turbo"
    save_config(cfg)
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path(__file__).parent
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config() -> dict:
    """Read the config file and return a dict (empty dict on missing/invalid file)."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    """Persist the config dict as JSON to the config file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
