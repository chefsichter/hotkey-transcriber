import os
import shlex
import subprocess
import time
from dataclasses import dataclass

from hotkey_transcriber.builtin_scripts import execute_builtin_script


@dataclass(frozen=True)
class WakeWordScriptAction:
    wake_word_model: str
    builtin: str | None = None
    command: str | None = None
    start_recording_after: bool = True
    delay_ms: int = 1200


def _build_wake_word_script_action(entry: dict) -> WakeWordScriptAction | None:
    wake_word_model = str(entry.get("wake_word_model", "")).strip()
    if not wake_word_model:
        return None
    builtin = str(entry.get("builtin", "")).strip() or None
    command = str(entry.get("command", "")).strip() or None
    if builtin is None and command is None:
        return None
    start_recording_after = bool(entry.get("start_recording_after", True))
    delay_ms = int(entry.get("delay_ms", 1200))
    return WakeWordScriptAction(
        wake_word_model=wake_word_model,
        builtin=builtin,
        command=command,
        start_recording_after=start_recording_after,
        delay_ms=max(0, delay_ms),
    )


def load_wake_word_script_actions(config_entries) -> dict[str, WakeWordScriptAction]:
    actions = {}
    for entry in config_entries or []:
        if not isinstance(entry, dict):
            continue
        action = _build_wake_word_script_action(entry)
        if action is not None:
            actions[action.wake_word_model.strip().lower()] = action
    return actions


class WakeWordScriptActionExecutor:
    def __init__(self, actions: dict[str, WakeWordScriptAction], enabled: bool = True):
        self._actions = actions
        self.enabled = enabled

    def set_actions(self, actions: dict[str, WakeWordScriptAction]) -> None:
        self._actions = actions

    @property
    def has_actions(self) -> bool:
        return bool(self._actions)

    def action_for_wake_word(self, wake_word_model: str | None) -> WakeWordScriptAction | None:
        if not self.enabled or not wake_word_model:
            return None
        return self._actions.get(wake_word_model.strip().lower())

    def execute(self, action: WakeWordScriptAction) -> bool:
        try:
            if action.builtin is not None:
                execute_builtin_script(action.builtin)
            elif action.command is not None:
                self._run_command(action.command)
            else:
                return False
        except Exception as exc:
            print(f"Wake-Word-Skript fehlgeschlagen fuer '{action.wake_word_model}': {exc}")
            return False
        if action.delay_ms > 0:
            time.sleep(action.delay_ms / 1000)
        return True

    @staticmethod
    def _run_command(command: str) -> None:
        stripped = command.strip()
        if os.path.isfile(stripped) and stripped.endswith(".sh"):
            args = ["bash", stripped]
        else:
            args = shlex.split(stripped)
        subprocess.run(args, check=False, timeout=15)
