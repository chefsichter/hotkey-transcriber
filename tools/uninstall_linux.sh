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

# Remove AMD GPU launcher (if present)
LAUNCHER="${HOME}/.local/bin/hotkey-transcriber"
if [[ -f "${LAUNCHER}" ]]; then
  echo "Removing AMD GPU launcher at ${LAUNCHER}..."
  rm -f "${LAUNCHER}"
fi

# Remove venv (AMD GPU install path)
VENV_DIR="${REPO_ROOT}/.venv"
if [[ -d "${VENV_DIR}" ]]; then
  echo "Removing venv at ${VENV_DIR}..."
  rm -rf "${VENV_DIR}"
fi

# Stop and disable ydotoold user service
if command -v systemctl >/dev/null 2>&1; then
  if systemctl --user is-enabled ydotoold >/dev/null 2>&1; then
    echo "Stopping and disabling ydotoold service..."
    systemctl --user disable --now ydotoold >/dev/null 2>&1 || true
  fi
  rm -f "${HOME}/.config/systemd/user/ydotoold.service"
  systemctl --user daemon-reload 2>/dev/null || true
fi

if command -v pipx >/dev/null 2>&1; then
  echo "Uninstalling hotkey-transcriber from pipx..."
  pipx uninstall hotkey-transcriber >/dev/null || true
else
  echo "pipx not found, skipping pipx uninstall."
fi

echo "Uninstall complete."
