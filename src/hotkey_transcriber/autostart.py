import argparse
import os
import shlex
import sys
from pathlib import Path


WINDOWS_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_RUN_VALUE = "HotkeyTranscriber"
LINUX_AUTOSTART_FILE = "hotkey-transcriber.desktop"


def is_supported() -> bool:
    return sys.platform.startswith("linux") or sys.platform == "win32"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            return f'"{sys.executable}"'
        return shlex.quote(sys.executable)
    return "hotkey-transcriber"


def _linux_autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / LINUX_AUTOSTART_FILE


def _linux_desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        "Name=Hotkey Transcriber\n"
        "Comment=Live dictation tray app\n"
        f"Exec={_launch_command()}\n"
        "Icon=microphone\n"
        "Terminal=false\n"
        "Categories=Audio;Utility;Accessibility;\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _linux_is_enabled() -> bool:
    return _linux_autostart_path().is_file()


def _linux_set_enabled(enabled: bool) -> None:
    path = _linux_autostart_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
        path.write_text(_linux_desktop_entry(), encoding="utf-8")
    elif path.exists():
        path.unlink()


def _windows_is_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, WINDOWS_RUN_VALUE)
            return bool(value)
    except FileNotFoundError:
        return False


def _windows_set_enabled(enabled: bool) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_PATH) as key:
        if enabled:
            winreg.SetValueEx(key, WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(key, WINDOWS_RUN_VALUE)
            except FileNotFoundError:
                pass


def is_enabled() -> bool:
    if sys.platform.startswith("linux"):
        return _linux_is_enabled()
    if sys.platform == "win32":
        return _windows_is_enabled()
    return False


def set_enabled(enabled: bool) -> None:
    if not is_supported():
        raise RuntimeError(f"Autostart is not supported on platform: {sys.platform}")
    if sys.platform.startswith("linux"):
        _linux_set_enabled(enabled)
    elif sys.platform == "win32":
        _windows_set_enabled(enabled)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Manage Hotkey Transcriber autostart.")
    parser.add_argument("--status", action="store_true", help="Print autostart status.")
    parser.add_argument("--set", metavar="on|off", help="Set autostart to on/off.")
    args = parser.parse_args(argv)

    if not is_supported():
        print(f"unsupported:{sys.platform}")
        return 1

    if args.set is not None:
        try:
            desired = _parse_bool(args.set)
        except ValueError as exc:
            print(str(exc))
            return 2
        set_enabled(desired)

    if args.status or args.set is not None:
        print("on" if is_enabled() else "off")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
