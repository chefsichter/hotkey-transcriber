"""Tests for spoken Enter/Undo command handling in SpeechRecorder."""

from hotkey_transcriber.speech_recorder import SpeechRecorder


class _KeyboardStub:
    def __init__(self):
        self.backspace_calls = []

    def backspace(self, count):
        self.backspace_calls.append(count)


def _build_recorder(
    spoken_enter_enabled=False, spoken_undo_enabled=False, last_insert_char_count=0
):
    recorder = SpeechRecorder.__new__(SpeechRecorder)
    recorder.spoken_enter_enabled = spoken_enter_enabled
    recorder.spoken_undo_enabled = spoken_undo_enabled
    recorder._last_speech_insert_char_count = last_insert_char_count
    recorder.keyb_c = _KeyboardStub()
    return recorder


def test_split_trailing_enter_command_removes_enter_suffix():
    recorder = _build_recorder(spoken_enter_enabled=True)

    text, should_press_enter = recorder._split_trailing_enter_command("hallo welt enter")

    assert text == "hallo welt"
    assert should_press_enter is True


def test_resolve_output_action_cancels_current_sentence_on_trailing_undo():
    recorder = _build_recorder(spoken_undo_enabled=True)

    output_text, should_press_enter, cancel_current, undo_previous = recorder._resolve_output_action(
        "das soll weg undo"
    )

    assert output_text == ""
    assert should_press_enter is False
    assert cancel_current is True
    assert undo_previous is False


def test_resolve_output_action_undo_alone_triggers_previous_undo():
    recorder = _build_recorder(spoken_undo_enabled=True)

    output_text, should_press_enter, cancel_current, undo_previous = recorder._resolve_output_action(
        "undo"
    )

    assert output_text == ""
    assert should_press_enter is False
    assert cancel_current is False
    assert undo_previous is True


def test_resolve_output_action_recognizes_andu_as_undo():
    recorder = _build_recorder(spoken_undo_enabled=True)

    output_text, should_press_enter, cancel_current, undo_previous = recorder._resolve_output_action(
        "das soll weg andu"
    )

    assert output_text == ""
    assert should_press_enter is False
    assert cancel_current is True
    assert undo_previous is False


def test_resolve_output_action_recognizes_undu_as_undo():
    recorder = _build_recorder(spoken_undo_enabled=True)

    output_text, should_press_enter, cancel_current, undo_previous = recorder._resolve_output_action(
        "undu"
    )

    assert output_text == ""
    assert should_press_enter is False
    assert cancel_current is False
    assert undo_previous is True


def test_resolve_output_action_recognizes_ando_with_punctuation_as_undo():
    recorder = _build_recorder(spoken_undo_enabled=True)

    output_text, should_press_enter, cancel_current, undo_previous = recorder._resolve_output_action(
        "ando."
    )

    assert output_text == ""
    assert should_press_enter is False
    assert cancel_current is False
    assert undo_previous is True


def test_resolve_output_action_recognizes_andou_as_undo():
    recorder = _build_recorder(spoken_undo_enabled=True)

    output_text, should_press_enter, cancel_current, undo_previous = recorder._resolve_output_action(
        "andou"
    )

    assert output_text == ""
    assert should_press_enter is False
    assert cancel_current is False
    assert undo_previous is True


def test_resolve_output_action_recognizes_und_du_as_undo():
    recorder = _build_recorder(spoken_undo_enabled=True)

    output_text, should_press_enter, cancel_current, undo_previous = recorder._resolve_output_action(
        "und du"
    )

    assert output_text == ""
    assert should_press_enter is False
    assert cancel_current is False
    assert undo_previous is True


def test_prepare_builtin_remainder_clears_submit_when_trailing_undo():
    recorder = _build_recorder(spoken_enter_enabled=True, spoken_undo_enabled=True)

    remainder, should_submit = recorder._prepare_builtin_remainder("fasse das zusammen undo")

    assert remainder == ""
    assert should_submit is False


def test_undo_last_speech_insert_uses_backspace_and_clears_last_count():
    recorder = _build_recorder(spoken_undo_enabled=True, last_insert_char_count=7)

    recorder._undo_last_speech_insert()
    recorder._undo_last_speech_insert()

    assert recorder.keyb_c.backspace_calls == [7]
    assert recorder._last_speech_insert_char_count == 0


def test_remember_speech_insert_stores_last_char_count():
    recorder = _build_recorder(spoken_undo_enabled=True)

    recorder._remember_speech_insert(12)

    assert recorder._last_speech_insert_char_count == 12
