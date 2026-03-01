#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Disabling autostart..."
if command -v python3 >/dev/null 2>&1; then
  PYTHONPATH="${REPO_ROOT}/src" python3 -m hotkey_transcriber.autostart --set off --status >/dev/null || true
fi

echo "Removing desktop integration..."
rm -f "${HOME}/.local/share/applications/hotkey-transcriber.desktop"
rm -f "${HOME}/.local/share/icons/hicolor/256x256/apps/microphone.png"
rm -f "${HOME}/.local/share/icons/hicolor/256x256/apps/hotkey-transcriber.png"
rm -f "${HOME}/.config/autostart/hotkey-transcriber.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${HOME}/.local/share/applications" || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -t "${HOME}/.local/share/icons/hicolor" || true
fi

if command -v pipx >/dev/null 2>&1; then
  echo "Uninstalling hotkey-transcriber from pipx..."
  pipx uninstall hotkey-transcriber >/dev/null || true
else
  echo "pipx not found, skipping pipx uninstall."
fi

echo "Uninstall complete."
