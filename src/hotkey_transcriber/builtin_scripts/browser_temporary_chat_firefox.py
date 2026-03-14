import subprocess
from urllib.parse import urlencode


_TEMPORARY_CHAT_URL = "https://chatgpt.com/?temporary-chat=true"


def _temporary_chat_url(argument: str, submit_after: bool) -> str:
    prompt = argument.strip()
    if not prompt and not submit_after:
        return _TEMPORARY_CHAT_URL
    params = {}
    if prompt:
        params["ht_prompt"] = prompt
    if submit_after:
        params["ht_submit"] = "1"
    return f"{_TEMPORARY_CHAT_URL}&{urlencode(params)}"


def run_browser_temporary_chat_firefox(
    argument: str = "",
    submit_after: bool = False,
) -> None:
    target_url = _temporary_chat_url(argument, submit_after)
    commands = [
        ["firefox", "--new-tab", target_url],
        ["xdg-open", target_url],
    ]
    last_error = None
    for cmd in commands:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError as exc:
            last_error = exc
    raise RuntimeError(last_error or "Kein Browser-Kommando verfuegbar.")
