#!/usr/bin/env bash
set -euo pipefail

AUTOSTART="ask"

for arg in "$@"; do
  case "$arg" in
    --autostart=on|--autostart=off|--autostart=ask)
      AUTOSTART="${arg#*=}"
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--autostart=on|off|ask]" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3." >&2
  exit 1
fi

if ! command -v pipx >/dev/null 2>&1; then
  echo "pipx not found - installing with python3..."
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  echo "pipx installed. Reopen your shell if pipx is still not found in PATH."
fi

echo "Installing hotkey-transcriber with pipx..."
pipx install --force "${REPO_ROOT}"

echo "Installing desktop integration..."
python3 "${REPO_ROOT}/desktop_files/linux/install_desktop.py"

if [[ "${AUTOSTART}" == "ask" ]]; then
  read -r -p "Enable autostart? [y/N]: " answer
  if [[ "${answer}" =~ ^([yY]|yes|YES)$ ]]; then
    AUTOSTART="on"
  else
    AUTOSTART="off"
  fi
fi

if [[ "${AUTOSTART}" == "on" || "${AUTOSTART}" == "off" ]]; then
  PYTHONPATH="${REPO_ROOT}/src" python3 -m hotkey_transcriber.autostart --set "${AUTOSTART}" --status
fi

echo "Installation complete."
