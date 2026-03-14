"""Tests for hotkey_change_dialog.py — hotkey_label, build_tray_tooltip."""

from hotkey_transcriber.gui.hotkey_change_dialog import build_tray_tooltip, hotkey_label


def test_hotkey_label_basic():
    cfg = {"modifier": "alt", "key": "r"}
    assert hotkey_label(cfg) == "Alt+R"


def test_hotkey_label_ctrl():
    cfg = {"modifier": "ctrl", "key": "space"}
    assert hotkey_label(cfg) == "Ctrl+SPACE"


def test_hotkey_label_shift():
    cfg = {"modifier": "shift", "key": "f1"}
    assert hotkey_label(cfg) == "Shift+F1"


def test_hotkey_label_multi_modifier():
    cfg = {"modifier": "ctrl+alt", "key": "t"}
    # title() on "ctrl+alt" → "Ctrl+Alt"
    assert hotkey_label(cfg) == "Ctrl+Alt+T"


def test_hotkey_label_defaults():
    assert hotkey_label({}) == "Alt+R"


def test_build_tray_tooltip_contains_label():
    cfg = {"modifier": "alt", "key": "r"}
    tip = build_tray_tooltip(cfg)
    assert "Alt+R" in tip
    assert "Live-Diktat" in tip


def test_build_tray_tooltip_custom_label():
    cfg = {"modifier": "ctrl", "key": "d"}
    tip = build_tray_tooltip(cfg, app_label="MyApp")
    assert "MyApp" in tip
    assert "Ctrl+D" in tip
