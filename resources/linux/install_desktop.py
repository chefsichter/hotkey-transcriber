#!/usr/bin/env python3
"""
install_desktop.py:
Install desktop integration for Hotkey Transcriber on Kubuntu.
Copies the .desktop file and icon to the user's local applications and icon directories.
"""
import sys
import subprocess
from pathlib import Path

ICON = "microphone.png"

def main():
    resources_folder_path = Path(__file__).resolve().parent.parent
    desktop_src = resources_folder_path / "linux" / "hotkey-transcriber.desktop"
    icon_src = resources_folder_path / "icon" / f"{ICON}"

    if not desktop_src.is_file():
        print(f"Error: Desktop file not found: {desktop_src}", file=sys.stderr)
        sys.exit(1)
    if not icon_src.is_file():
        print(f"Error: Icon file not found: {icon_src}", file=sys.stderr)
        sys.exit(1)

    applications_dir = Path.home() / ".local" / "share" / "applications"
    icons_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    applications_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    desktop_dst = applications_dir / desktop_src.name
    icon_dst = icons_dir / icon_src.name
    # Copy files
    try:
        import shutil
        shutil.copy2(desktop_src, desktop_dst)
        print(f"Copied {desktop_src} to {desktop_dst}")
        shutil.copy2(icon_src, icon_dst)
        print(f"Copied {icon_src} to {icon_dst}")
    except Exception as e:
        print(f"Error copying files: {e}", file=sys.stderr)
        sys.exit(1)

    # Update desktop database
    try:
        subprocess.run(["update-desktop-database", str(applications_dir)], check=True)
    except FileNotFoundError:
        print("Warning: update-desktop-database not found, skipping", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Warning: update-desktop-database failed: {e}", file=sys.stderr)

    # Update icon cache
    try:
        icon_cache_dir = Path.home() / ".local" / "share" / "icons" / "hicolor"
        subprocess.run(["gtk-update-icon-cache", "-t", str(icon_cache_dir)], check=True)
    except FileNotFoundError:
        print("Warning: gtk-update-icon-cache not found, skipping", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Warning: gtk-update-icon-cache failed: {e}", file=sys.stderr)

    print("Installation complete.")

if __name__ == "__main__":
    main()