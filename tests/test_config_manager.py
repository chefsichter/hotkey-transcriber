"""Tests for config/config_manager.py — load_config / save_config."""

import json
from pathlib import Path
from unittest.mock import patch


def _make_manager(tmp_path: Path):
    """Return (load_config, save_config) pointing at a temp config directory."""
    import hotkey_transcriber.config.config_manager as mod

    config_file = tmp_path / "config.json"
    with (
        patch.object(mod, "CONFIG_FILE", str(config_file)),
        patch.object(mod, "CONFIG_DIR", tmp_path),
    ):
        yield mod.load_config, mod.save_config, config_file


def test_load_config_returns_empty_dict_when_file_missing(tmp_path):
    import hotkey_transcriber.config.config_manager as mod

    config_file = tmp_path / "nonexistent.json"
    with patch.object(mod, "CONFIG_FILE", str(config_file)):
        result = mod.load_config()
    assert result == {}


def test_load_config_returns_empty_dict_on_invalid_json(tmp_path):
    import hotkey_transcriber.config.config_manager as mod

    config_file = tmp_path / "config.json"
    config_file.write_text("NOT VALID JSON", encoding="utf-8")
    with patch.object(mod, "CONFIG_FILE", str(config_file)):
        result = mod.load_config()
    assert result == {}


def test_save_and_load_roundtrip(tmp_path):
    import hotkey_transcriber.config.config_manager as mod

    config_file = tmp_path / "config.json"
    data = {"model_size": "large-v3-turbo", "language": "de", "silence_timeout_ms": 1500}
    with (
        patch.object(mod, "CONFIG_FILE", str(config_file)),
        patch.object(mod, "CONFIG_DIR", tmp_path),
    ):
        mod.save_config(data)
        result = mod.load_config()
    assert result == data


def test_save_config_creates_file(tmp_path):
    import hotkey_transcriber.config.config_manager as mod

    config_file = tmp_path / "config.json"
    with (
        patch.object(mod, "CONFIG_FILE", str(config_file)),
        patch.object(mod, "CONFIG_DIR", tmp_path),
    ):
        mod.save_config({"key": "value"})
    assert config_file.exists()
    content = json.loads(config_file.read_text(encoding="utf-8"))
    assert content == {"key": "value"}


def test_save_config_overwrites_existing(tmp_path):
    import hotkey_transcriber.config.config_manager as mod

    config_file = tmp_path / "config.json"
    config_file.write_text('{"old": true}', encoding="utf-8")
    with (
        patch.object(mod, "CONFIG_FILE", str(config_file)),
        patch.object(mod, "CONFIG_DIR", tmp_path),
    ):
        mod.save_config({"new": True})
        result = mod.load_config()
    assert result == {"new": True}
    assert "old" not in result
