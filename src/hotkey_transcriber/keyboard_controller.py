import os
import sys
import threading
import time
import types

import keyboard
import pyperclip


def _ensure_display_env():
    """
    On Linux/Wayland the terminal session may lack DISPLAY and XAUTHORITY
    even though Xwayland is running.  Recover them from the compositor process
    so that pyautogui (which needs X11) can connect.
    """
    if sys.platform != "linux":
        return
    if os.environ.get("DISPLAY") and os.environ.get("XAUTHORITY"):
        return

    # Find a GUI process to read env from (compositor or desktop shell)
    import subprocess
    for proc_name in ("gnome-shell", "kwin_wayland", "plasmashell", "nautilus"):
        try:
            result = subprocess.run(
                ["pgrep", "-u", str(os.getuid()), "-x", proc_name],
                capture_output=True, text=True, timeout=2,
            )
            pids = result.stdout.strip().split()
            if not pids:
                continue
            environ = open(f"/proc/{pids[0]}/environ", "rb").read()
            env_vars = dict(
                item.split(b"=", 1)
                for item in environ.split(b"\x00")
                if b"=" in item
            )
            for key in (b"DISPLAY", b"XAUTHORITY", b"WAYLAND_DISPLAY"):
                if key in env_vars and not os.environ.get(key.decode()):
                    os.environ[key.decode()] = env_vars[key].decode()
            return
        except Exception:
            continue


def _load_input_backend():
    """
    Prefer pyautogui, but gracefully fall back to `keyboard` if GUI access is unavailable
    (e.g. missing X11 authorization / Wayland restrictions).
    """
    _ensure_display_env()
    os.environ.setdefault("PYAUTOGUI_FAILSAFE", "True")

    # Inject MouseInfo stub before pyautogui import.
    mouseinfo_stub = types.ModuleType("mouseinfo")
    mouseinfo_stub.MouseInfoWindow = lambda *args, **kw: None
    sys.modules["mouseinfo"] = mouseinfo_stub

    try:
        import pyautogui  # type: ignore
        return "pyautogui", pyautogui, None
    except Exception as exc:
        return "keyboard", keyboard, exc


def _safe_print(text="", end="\n", flush=False):
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe = str(text).encode(enc, errors="replace").decode(enc, errors="replace")
    print(safe, end=end, flush=flush)


class KeyboardController:
    """
    Wraps undo/paste logic with clipboard restore and internal lock.
    """

    def __init__(self, wait: float = 0.02):
        self.wait = wait
        self.clipboard_content = None
        self.lock = threading.Lock()
        self.backend_name, self.backend, self.pyautogui_error = _load_input_backend()
        self._backend_error_reported = False
        if self.pyautogui_error is not None:
            _safe_print(
                f"⚠️ pyautogui nicht nutzbar ({self.pyautogui_error}). "
                "Fallback auf keyboard-Backend."
            )

    def _mark_backend_unavailable(self, exc: Exception) -> None:
        if not self._backend_error_reported:
            _safe_print(
                "⚠️ Keyboard-Backend nicht nutzbar: "
                f"{exc}. Automatische Tastensteuerung deaktiviert."
            )
            self._backend_error_reported = True
        self.backend_name = "none"

    def undo(self):
        """Send Ctrl+Z."""
        with self.lock:
            if self.backend_name == "pyautogui":
                self.backend.hotkey("ctrl", "z")
            elif self.backend_name == "keyboard":
                try:
                    self.backend.send("ctrl+z")
                except Exception as exc:
                    self._mark_backend_unavailable(exc)
            time.sleep(self.wait)

    def backspace(self, n_times=1):
        """Send Backspace n times."""
        with self.lock:
            if self.backend_name == "pyautogui":
                self.backend.press("backspace", presses=n_times, interval=0)
            elif self.backend_name == "keyboard":
                for _ in range(max(1, int(n_times))):
                    try:
                        self.backend.send("backspace")
                    except Exception as exc:
                        self._mark_backend_unavailable(exc)
                        break

    def paste(self, text: str, end="\n"):
        """
        Put text into clipboard, press Ctrl+V, then keep clipboard behavior stable.
        """
        with self.lock:
            _safe_print(text, end=end, flush=True)
            pyperclip.copy(text)
            time.sleep(self.wait)
            if self.backend_name == "pyautogui":
                self.backend.keyUp("altleft")
                self.backend.keyUp("altright")
            time.sleep(self.wait)
            if self.backend_name == "pyautogui":
                self.backend.hotkey("ctrl", "v")
            elif self.backend_name == "keyboard":
                try:
                    self.backend.send("ctrl+v")
                except Exception as exc:
                    self._mark_backend_unavailable(exc)
            time.sleep(self.wait)

    def write(self, text: str, end="\n", interval=None):
        if interval is None:
            interval = self.wait
        with self.lock:
            _safe_print(text, end=end, flush=True)
            if self.backend_name == "pyautogui":
                self.backend.write(text, interval=interval)
            elif self.backend_name == "keyboard":
                try:
                    self.backend.write(text, delay=interval)
                except Exception as exc:
                    self._mark_backend_unavailable(exc)

    def save_clipboard(self):
        """Store current clipboard content."""
        with self.lock:
            self.clipboard_content = pyperclip.paste()
            time.sleep(self.wait)
            _safe_print("💾 Clipboard gespeichert.")

    def load_clipboard(self):
        """Restore previous clipboard content."""
        with self.lock:
            pyperclip.copy(self.clipboard_content)
            _safe_print("📤 Clipboard wieder geladen.")
