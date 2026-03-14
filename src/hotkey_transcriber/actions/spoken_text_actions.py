import shlex
import subprocess
import time
from dataclasses import dataclass
from difflib import SequenceMatcher

from hotkey_transcriber.builtin_scripts import execute_builtin_script

_URL_INSERT_BUILTINS = frozenset({"temporary_chat_firefox"})


@dataclass(frozen=True)
class SpokenTextAction:
    triggers: tuple[str, ...]
    builtin: str | None = None
    command: str | None = None
    paste_remainder: bool = True
    delay_ms: int = 1200
    fuzzy_threshold: float = 0.78


def _normalize_token(token: str) -> str:
    return token.strip().casefold().strip(".,!?;:\"'()[]{}")


def _normalized_tokens(text: str) -> list[str]:
    return [_normalize_token(token) for token in text.split() if _normalize_token(token)]


def _match_trigger(text: str, trigger: str) -> str | None:
    raw_tokens = [token for token in text.strip().split() if token]
    normalized_text_tokens = [_normalize_token(token) for token in raw_tokens]
    normalized_trigger_tokens = _normalized_tokens(trigger)
    if not normalized_trigger_tokens:
        return None
    if normalized_text_tokens[:len(normalized_trigger_tokens)] != normalized_trigger_tokens:
        return None
    remainder_tokens = raw_tokens[len(normalized_trigger_tokens):]
    return " ".join(remainder_tokens).strip()


def _match_trigger_fuzzy(text: str, trigger: str, threshold: float) -> str | None:
    raw_tokens = [token for token in text.strip().split() if token]
    normalized_text_tokens = [_normalize_token(token) for token in raw_tokens]
    normalized_trigger_tokens = _normalized_tokens(trigger)
    if not normalized_trigger_tokens:
        return None
    prefix_tokens = normalized_text_tokens[:len(normalized_trigger_tokens)]
    if len(prefix_tokens) != len(normalized_trigger_tokens):
        return None
    prefix_text = " ".join(prefix_tokens)
    trigger_text = " ".join(normalized_trigger_tokens)
    if SequenceMatcher(a=prefix_text, b=trigger_text).ratio() < threshold:
        return None
    remainder_tokens = raw_tokens[len(normalized_trigger_tokens):]
    return " ".join(remainder_tokens).strip()


def _normalize_triggers(entry: dict) -> tuple[str, ...]:
    raw_triggers = entry.get("triggers")
    if isinstance(raw_triggers, list):
        cleaned = [str(item).strip() for item in raw_triggers if str(item).strip()]
        if cleaned:
            return tuple(cleaned)
    trigger = str(entry.get("trigger", "")).strip()
    if trigger:
        return (trigger,)
    return ()


def _build_spoken_text_action(entry: dict) -> SpokenTextAction | None:
    triggers = _normalize_triggers(entry)
    if not triggers:
        return None
    builtin = str(entry.get("builtin", "")).strip() or None
    command = str(entry.get("command", "")).strip() or None
    if builtin is None and command is None:
        return None
    paste_remainder = bool(entry.get("paste_remainder", True))
    delay_ms = int(entry.get("delay_ms", 1200))
    fuzzy_threshold = float(entry.get("fuzzy_threshold", 0.78))
    return SpokenTextAction(
        triggers=triggers,
        builtin=builtin,
        command=command,
        paste_remainder=paste_remainder,
        delay_ms=max(0, delay_ms),
        fuzzy_threshold=max(0.0, min(1.0, fuzzy_threshold)),
    )


def load_spoken_text_actions(config_entries) -> list[SpokenTextAction]:
    actions = []
    for entry in config_entries or []:
        if not isinstance(entry, dict):
            continue
        action = _build_spoken_text_action(entry)
        if action is not None:
            actions.append(action)
    return actions


class SpokenTextActionExecutor:
    def __init__(self, actions: list[SpokenTextAction], enabled: bool = True):
        self._actions = actions
        self.enabled = enabled

    def set_actions(self, actions: list[SpokenTextAction]) -> None:
        self._actions = actions

    @property
    def has_actions(self) -> bool:
        return bool(self._actions)

    def match(self, text: str) -> tuple[SpokenTextAction, str] | None:
        if not self.enabled:
            return None
        for action in self._actions:
            for trigger in action.triggers:
                remainder = _match_trigger(text, trigger)
                if remainder is not None:
                    return action, remainder
            for trigger in action.triggers:
                remainder = _match_trigger_fuzzy(text, trigger, action.fuzzy_threshold)
                if remainder is not None:
                    print(
                        f"[text-action] fuzzy match text='{text}' trigger='{trigger}' "
                        f"threshold={action.fuzzy_threshold}",
                        flush=True,
                    )
                    return action, remainder
        return None

    def execute(
        self,
        action: SpokenTextAction,
        remainder: str,
        submit_after: bool = False,
    ) -> tuple[bool, bool]:
        try:
            if action.builtin is not None:
                execute_builtin_script(
                    action.builtin,
                    remainder,
                    submit_after=submit_after,
                )
                consumed_remainder = (
                    action.builtin in _URL_INSERT_BUILTINS and bool(remainder.strip())
                )
            elif action.command is not None:
                self._run_command(action.command, remainder)
                consumed_remainder = False
            else:
                return False, False
        except Exception as exc:
            print(f"Text-Sprachaktion fehlgeschlagen fuer '{action.triggers[0]}': {exc}")
            return False, False
        if action.delay_ms > 0:
            time.sleep(action.delay_ms / 1000)
        return True, consumed_remainder

    @staticmethod
    def _run_command(command: str, remainder: str) -> None:
        args = shlex.split(command)
        subprocess.run([*args, remainder], check=False, timeout=15)
