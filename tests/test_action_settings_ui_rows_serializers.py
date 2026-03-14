"""Tests for action_settings_ui_rows.py — serialize functions with mock row dicts."""

import pytest

from hotkey_transcriber.gui.action_settings_ui_rows import (
    serialize_spoken_text_script_rows,
    serialize_wake_word_script_rows,
)


class _MockCombo:
    def __init__(self, text: str):
        self._text = text

    def currentText(self) -> str:
        return self._text

    def isChecked(self) -> bool:
        return True


class _MockLineEdit:
    def __init__(self, text: str = ""):
        self._text = text

    def text(self) -> str:
        return self._text


class _MockCheckBox:
    def __init__(self, checked: bool = True):
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class _MockSpinBox:
    def __init__(self, value: float = 0.78):
        self._value = value

    def value(self) -> float:
        return self._value


def _make_spoken_text_row(
    trigger="hey chat",
    mode="Built-in",
    builtin="temporary_chat_firefox",
    command="",
    paste=True,
    fuzzy=0.78,
):
    return {
        "trigger": _MockLineEdit(trigger),
        "mode": _MockCombo(mode),
        "builtin": _MockCombo(builtin),
        "command": _MockLineEdit(command),
        "paste_remainder": _MockCheckBox(paste),
        "fuzzy_threshold": _MockSpinBox(fuzzy),
    }


def _make_wake_word_row(
    wake_word="hey jarvis",
    mode="Built-in",
    builtin="temporary_chat_firefox",
    command="",
    start_recording=True,
):
    return {
        "wake_word": _MockCombo(wake_word),
        "mode": _MockCombo(mode),
        "builtin": _MockCombo(builtin),
        "command": _MockLineEdit(command),
        "start_recording": _MockCheckBox(start_recording),
    }


class TestSerializeSpokenTextRows:
    def test_builtin_row_serialized(self):
        row = _make_spoken_text_row()
        result = serialize_spoken_text_script_rows([row])
        assert len(result) == 1
        entry = result[0]
        assert entry["builtin"] == "temporary_chat_firefox"
        assert "command" not in entry
        assert entry["paste_remainder"] is True
        assert entry["fuzzy_threshold"] == 0.78

    def test_empty_trigger_skipped(self):
        row = _make_spoken_text_row(trigger="  ")
        result = serialize_spoken_text_script_rows([row])
        assert result == []

    def test_shell_script_row_serialized(self):
        row = _make_spoken_text_row(mode="Shell-Skript", builtin="", command="/usr/local/bin/do.sh")
        result = serialize_spoken_text_script_rows([row])
        assert result[0]["command"] == "/usr/local/bin/do.sh"
        assert "builtin" not in result[0]

    def test_missing_builtin_raises(self):
        row = _make_spoken_text_row(mode="Built-in", builtin="")
        with pytest.raises(ValueError, match="Built-in-Skript fehlt"):
            serialize_spoken_text_script_rows([row])

    def test_missing_command_raises(self):
        row = _make_spoken_text_row(mode="Shell-Skript", command="")
        with pytest.raises(ValueError, match="Shell-Skript"):
            serialize_spoken_text_script_rows([row])

    def test_multiple_triggers_from_comma_separated(self):
        row = _make_spoken_text_row(trigger="hey chat, hey bot")
        result = serialize_spoken_text_script_rows([row])
        assert result[0]["triggers"] == ["hey chat", "hey bot"]


class TestSerializeWakeWordRows:
    def test_builtin_row_serialized(self):
        row = _make_wake_word_row()
        result = serialize_wake_word_script_rows([row])
        assert len(result) == 1
        entry = result[0]
        assert entry["wake_word_model"] == "hey jarvis"
        assert entry["builtin"] == "temporary_chat_firefox"
        assert entry["start_recording_after"] is True

    def test_empty_wake_word_skipped(self):
        row = _make_wake_word_row(wake_word="  ")
        result = serialize_wake_word_script_rows([row])
        assert result == []

    def test_shell_script_row_serialized(self):
        row = _make_wake_word_row(mode="Shell-Skript", command="/bin/my_script.sh")
        result = serialize_wake_word_script_rows([row])
        assert result[0]["command"] == "/bin/my_script.sh"

    def test_missing_builtin_raises(self):
        row = _make_wake_word_row(mode="Built-in", builtin="")
        with pytest.raises(ValueError, match="Built-in-Skript fehlt"):
            serialize_wake_word_script_rows([row])

    def test_missing_command_raises(self):
        row = _make_wake_word_row(mode="Shell-Skript", command="")
        with pytest.raises(ValueError, match="Shell-Skript"):
            serialize_wake_word_script_rows([row])
