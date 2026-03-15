"""
App Log Capture - Redirect stdout/stderr to a rotating log file while teeing to the original stream.

Architecture:
    ┌─────────────────────────────────────────┐
    │  AppLogCapture                          │
    │  ┌───────────────────────────────────┐  │
    │  │  _TeeStream                       │  │
    │  │  → writes to logfile + original   │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  setup_log_capture()              │  │
    │  │  → redirects sys.stdout/stderr    │  │
    │  └──────────────┬────────────────────┘  │
    │  ┌──────────────▼────────────────────┐  │
    │  │  read_log_tail()                  │  │
    │  │  → returns last N bytes of log    │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Usage:
    from hotkey_transcriber.app_log_capture import setup_log_capture, read_log_tail

    log_path = setup_log_capture()
    tail = read_log_tail(log_path)
"""

import contextlib
import io
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path


class _TeeStream(io.TextIOBase):
    def __init__(self, original, logfile):
        self._original = original
        self._logfile = logfile

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            text = str(text)
        self._logfile.write(text)
        self._logfile.flush()
        if self._original and hasattr(self._original, "write"):
            with contextlib.suppress(Exception):
                self._original.write(text)
        return len(text)

    def flush(self) -> None:
        self._logfile.flush()
        if self._original and hasattr(self._original, "flush"):
            with contextlib.suppress(Exception):
                self._original.flush()


def _runtime_log_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA", str(Path.home())))
    else:
        base = Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    log_dir = base / "hotkey-transcriber" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "hotkey-transcriber.log"


_LOG_FILE_HANDLE = None


def setup_log_capture() -> Path:
    """Redirect stdout and stderr to a log file (while teeing to the originals).

    Returns the path to the log file.
    """
    global _LOG_FILE_HANDLE
    primary_path = _runtime_log_path()
    temp_log_dir = Path(tempfile.gettempdir()) / "hotkey-transcriber-logs"
    with contextlib.suppress(Exception):
        temp_log_dir.mkdir(parents=True, exist_ok=True)

    candidate_paths = [
        primary_path,
        primary_path.with_name(f"{primary_path.stem}-{os.getpid()}.log"),
        temp_log_dir / "hotkey-transcriber.log",
        temp_log_dir / f"hotkey-transcriber-{os.getpid()}.log",
    ]

    log_path = primary_path
    last_exc: Exception | None = None
    for candidate in candidate_paths:
        try:
            _LOG_FILE_HANDLE = open(candidate, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
            log_path = candidate
            break
        except (PermissionError, OSError) as exc:
            last_exc = exc
            continue
    else:
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Konnte keine Logdatei oeffnen.")

    if log_path != primary_path:
        with contextlib.suppress(Exception):
            sys.__stderr__.write(f"Nutzung Fallback-Log: {log_path}\n")
    sys.stdout = _TeeStream(getattr(sys, "stdout", None), _LOG_FILE_HANDLE)
    sys.stderr = _TeeStream(getattr(sys, "stderr", None), _LOG_FILE_HANDLE)
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Hotkey Transcriber started")
    return log_path


def read_log_tail(path: Path, max_bytes: int = 200_000) -> str:
    """Return the last *max_bytes* bytes of the log file as a string."""
    if not path.exists():
        return "Noch keine Logs vorhanden."
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        start = max(0, size - max_bytes)
        f.seek(start)
        data = f.read()
    return data.decode("utf-8", errors="replace")
