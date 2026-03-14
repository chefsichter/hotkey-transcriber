"""Tests for resource_path_resolver.py — get_microphone_icon_path."""


from hotkey_transcriber.resource_path_resolver import get_microphone_icon_path


def test_get_microphone_icon_path_returns_string():
    path = get_microphone_icon_path()
    assert isinstance(path, str)


def test_get_microphone_icon_path_ends_with_png():
    path = get_microphone_icon_path()
    assert path.endswith(".png")


def test_get_microphone_icon_path_contains_microphone():
    path = get_microphone_icon_path()
    assert "microphone" in path.lower()
