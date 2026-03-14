from hotkey_transcriber.builtin_scripts.browser_temporary_chat_firefox import (
    run_browser_temporary_chat_firefox,
)


_BUILTIN_SCRIPT_RUNNERS = {
    "temporary_chat_firefox": run_browser_temporary_chat_firefox,
}


def list_builtin_scripts() -> list[str]:
    return sorted(_BUILTIN_SCRIPT_RUNNERS.keys())


def execute_builtin_script(
    name: str,
    argument: str = "",
    submit_after: bool = False,
) -> None:
    runner = _BUILTIN_SCRIPT_RUNNERS.get(name)
    if runner is None:
        raise ValueError(f"Unbekanntes eingebautes Skript: {name}")
    runner(argument, submit_after=submit_after)
