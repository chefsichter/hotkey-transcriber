"""Tests for speech_recorder.normalize_language."""

from hotkey_transcriber.speech_recorder import normalize_language


def test_normalize_language_none_returns_none():
    assert normalize_language(None) is None


def test_normalize_language_empty_string_returns_none():
    assert normalize_language("") is None


def test_normalize_language_auto_returns_none():
    assert normalize_language("auto") is None


def test_normalize_language_de():
    assert normalize_language("de") == "de"


def test_normalize_language_en():
    assert normalize_language("en") == "en"


def test_normalize_language_preserves_code():
    assert normalize_language("zh") == "zh"
