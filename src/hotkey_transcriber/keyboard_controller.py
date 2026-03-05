import os
import shutil
import subprocess
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
            break
        except Exception:
            continue

    # Fallback: DISPLAY default
    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":0"


# ---------------------------------------------------------------------------
# ydotool backend
# ---------------------------------------------------------------------------

def _detect_yz_swap() -> bool:
    """Return True if the active keyboard layout swaps Y and Z (QWERTZ).

    Checks GNOME gsettings first (works on Wayland), then falls back to
    localectl / setxkbmap.  Layouts that swap Y/Z: de, ch, at, etc.
    """
    _qwertz_prefixes = ("de", "ch", "at", "cz", "sk", "hu", "si", "hr", "ba", "rs", "me")
    # GNOME / gsettings (most reliable on Wayland)
    try:
        proc = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.input-sources", "sources"],
            capture_output=True, text=True, timeout=3,
        )
        out = proc.stdout.strip().lower()
        # e.g. "[('xkb', 'ch+de_nodeadkeys')]"
        for prefix in _qwertz_prefixes:
            if f"'{prefix}" in out or f'"{prefix}' in out:
                return True
    except Exception:
        pass
    # localectl fallback
    try:
        proc = subprocess.run(
            ["localectl", "status"],
            capture_output=True, text=True, timeout=3,
        )
        for line in proc.stdout.lower().splitlines():
            if "layout" in line:
                for prefix in _qwertz_prefixes:
                    if prefix in line:
                        return True
    except Exception:
        pass
    return False


# Y↔Z translation table for QWERTZ layouts
_YZ_SWAP = str.maketrans("yzYZ", "zyZY")


class _YdotoolBackend:
    """
    Wrapper around ydotool v1.x CLI with a pyautogui-compatible API.
    Requires ydotoold daemon (started via systemd user service).
    Works on both X11 and Wayland.

    ydotool v1.x uses raw Linux input-event-codes for the ``key`` command.
    See /usr/include/linux/input-event-codes.h for the full list.

    ``ydotool type`` maps characters via a built-in QWERTY table.  On QWERTZ
    layouts (de, ch, at, …) Y and Z are swapped, so we pre-swap them in the
    text before passing it to ydotool.
    """

    # Map pyautogui-style names → Linux KEY_* codes (decimal)
    _KEYMAP = {
        "backspace": 14,
        "enter": 28, "return": 28,
        "tab": 15, "escape": 1, "esc": 1,
        "delete": 111, "space": 57,
        "f1": 59, "f2": 60, "f3": 61, "f4": 62,
        "f5": 63, "f6": 64, "f7": 65, "f8": 66,
        "f9": 67, "f10": 68, "f11": 87, "f12": 88,
        # Modifiers
        "ctrl": 29, "ctrlleft": 29, "ctrlright": 97,
        "alt": 56, "altleft": 56, "altright": 100,
        "shift": 42, "shiftleft": 42, "shiftright": 54,
        # Letters / digits used by hotkey combos (ctrl+z, ctrl+v, …)
        "v": 47, "z": 44, "y": 21, "c": 46, "x": 45, "a": 30,
    }

    # On QWERTZ layouts, KEY_Y (21) and KEY_Z (44) are physically swapped.
    # ydotool sends raw keycodes that the compositor maps via the active layout,
    # so we must swap the codes to hit the intended character.
    _YZ_CODE_SWAP = {44: 21, 21: 44}

    def __init__(self):
        self._yz_swap = _detect_yz_swap()

    def _k(self, key: str) -> int:
        code = self._KEYMAP.get(key.lower())
        if code is None:
            raise ValueError(f"Unknown key for ydotool: {key!r}")
        if self._yz_swap:
            code = self._YZ_CODE_SWAP.get(code, code)
        return code

    @staticmethod
    def _run(args, timeout):
        proc = subprocess.run(args, capture_output=True, timeout=timeout, text=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(err or f"ydotool exited with code {proc.returncode}")
        return proc

    def hotkey(self, *keys):
        """Press a key combo using raw keycodes.  E.g. hotkey("ctrl", "v")."""
        codes = [self._k(k) for k in keys]
        # Build sequence: press all keys down, then release in reverse order
        seq = [f"{c}:1" for c in codes] + [f"{c}:0" for c in reversed(codes)]
        self._run(["ydotool", "key", *seq], timeout=5)

    def keyUp(self, key):
        """Release a key.  Needed to cancel physical modifiers (e.g. Alt from
        the hotkey) before injecting a new combo like Ctrl+V."""
        code = self._k(key)
        self._run(["ydotool", "key", f"{code}:0"], timeout=5)

    def press(self, key, presses=1, interval=0):
        code = self._k(key)
        seq = []
        for _ in range(max(1, int(presses))):
            seq += [f"{code}:1", f"{code}:0"]
        args = ["ydotool", "key"]
        if interval:
            args += ["--key-delay", str(int(interval * 1000))]
        args += seq
        self._run(args, timeout=5)

    def write(self, text, interval=0):
        if self._yz_swap:
            text = text.translate(_YZ_SWAP)
        args = ["ydotool", "type"]
        if interval:
            args += ["--key-delay", str(int(interval * 1000))]
        else:
            args += ["--key-delay", "0"]
        args += ["--", text]
        self._run(args, timeout=10)


_TERMINAL_APP_NAMES = frozenset({
    "gnome-terminal-server", "konsole", "xfce4-terminal", "mate-terminal",
    "lxterminal", "tilix", "terminator", "guake", "yakuake", "sakura",
    "alacritty", "kitty", "wezterm", "foot", "st", "urxvt", "xterm",
})


def _is_terminal_focused() -> bool:
    """Detect if the focused window is a terminal emulator via AT-SPI."""
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        Atspi.init()
        desktop = Atspi.get_desktop(0)
        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            for j in range(app.get_child_count()):
                win = app.get_child_at_index(j)
                states = win.get_state_set()
                if states.contains(Atspi.StateType.ACTIVE):
                    return app.get_name() in _TERMINAL_APP_NAMES
    except Exception:
        pass
    return False


def _ydotool_available() -> bool:
    """Check if ydotool v1.x is installed with ydotoold running."""
    if not shutil.which("ydotool"):
        return False
    # v1.x requires ydotoold – test by running a no-op key command.
    try:
        proc = subprocess.run(
            ["ydotool", "key", ""],
            capture_output=True, timeout=3,
        )
        return proc.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Backend loader
# ---------------------------------------------------------------------------

def _load_input_backend():
    """
    Platform-specific backend selection:
      Linux:   ydotool → pyautogui → keyboard
      Windows: pyautogui → keyboard
      Other:   pyautogui → keyboard
    """
    _ensure_display_env()
    os.environ.setdefault("PYAUTOGUI_FAILSAFE", "True")

    # Inject MouseInfo stub before pyautogui import.
    mouseinfo_stub = types.ModuleType("mouseinfo")
    mouseinfo_stub.MouseInfoWindow = lambda *args, **kw: None
    sys.modules["mouseinfo"] = mouseinfo_stub

    # Linux: prefer ydotool (works on Wayland and X11)
    if sys.platform == "linux" and _ydotool_available():
        return "ydotool", _YdotoolBackend(), None

    try:
        import pyautogui  # type: ignore
        return "pyautogui", pyautogui, None
    except Exception as exc:
        return "keyboard", keyboard, exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_print(text="", end="\n", flush=False):
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe = str(text).encode(enc, errors="replace").decode(enc, errors="replace")
    print(safe, end=end, flush=flush)


# ---------------------------------------------------------------------------
# KeyboardController
# ---------------------------------------------------------------------------

class KeyboardController:
    """
    Wraps undo/paste logic with clipboard restore and internal lock.
    """

    def __init__(self, wait: float = 0.05):
        self.wait = wait
        self.clipboard_content = None
        self.lock = threading.Lock()
        self.backend_name, self.backend, self.pyautogui_error = _load_input_backend()
        self._backend_error_reported = False
        if self.backend_name == "ydotool":
            _safe_print("✅ ydotool-Backend aktiv.")
        elif self.pyautogui_error is not None:
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
            if self.backend_name in ("pyautogui", "ydotool"):
                try:
                    self.backend.hotkey("ctrl", "z")
                except Exception as exc:
                    self._mark_backend_unavailable(exc)
            elif self.backend_name == "keyboard":
                try:
                    self.backend.send("ctrl+z")
                except Exception as exc:
                    self._mark_backend_unavailable(exc)
            time.sleep(self.wait)

    def backspace(self, n_times=1):
        """Send Backspace n times."""
        with self.lock:
            if self.backend_name in ("pyautogui", "ydotool"):
                try:
                    self.backend.press("backspace", presses=n_times, interval=0)
                except Exception as exc:
                    self._mark_backend_unavailable(exc)
            elif self.backend_name == "keyboard":
                for _ in range(max(1, int(n_times))):
                    try:
                        self.backend.send("backspace")
                    except Exception as exc:
                        self._mark_backend_unavailable(exc)
                        break

    def paste(self, text: str, end="\n"):
        """
        Type text into the focused window via clipboard + Ctrl+V.
        This handles Unicode, emojis, and all keyboard layouts correctly.
        """
        with self.lock:
            _safe_print(text, end=end, flush=True)
            pyperclip.copy(text)
            time.sleep(self.wait)
            if self.backend_name == "ydotool":
                try:
                    if _is_terminal_focused():
                        self.backend.hotkey("ctrl", "shift", "v")
                    else:
                        self.backend.hotkey("ctrl", "v")
                except Exception as exc:
                    self._mark_backend_unavailable(exc)
            elif self.backend_name == "pyautogui":
                self.backend.keyUp("altleft")
                self.backend.keyUp("altright")
                time.sleep(self.wait)
                self.backend.hotkey("ctrl", "v")
            elif self.backend_name == "keyboard":
                try:
                    self.backend.send("ctrl+v")
                except Exception as exc:
                    self._mark_backend_unavailable(exc)
            time.sleep(self.wait)

    def write(self, text: str, end="\n", interval=0):
        with self.lock:
            _safe_print(text, end=end, flush=True)
            try:
                if self.backend_name == "keyboard":
                    self.backend.write(text, delay=interval)
                elif self.backend_name in ("pyautogui", "ydotool"):
                    self.backend.write(text, interval=interval)
            except Exception as exc:
                self._mark_backend_unavailable(exc)

    def save_clipboard(self):
        """Store current clipboard content."""
        with self.lock:
            try:
                self.clipboard_content = pyperclip.paste()
            except Exception:
                self.clipboard_content = None
            time.sleep(self.wait)
            _safe_print("💾 Clipboard gespeichert.")

    def load_clipboard(self):
        """Restore previous clipboard content."""
        with self.lock:
            if self.clipboard_content is None:
                return
            try:
                pyperclip.copy(self.clipboard_content)
            except Exception:
                return
            _safe_print("📤 Clipboard wieder geladen.")
