#!/usr/bin/env bash
set -euo pipefail

AUTOSTART="ask"
AMD_GPU=0

for arg in "$@"; do
  case "$arg" in
    --autostart=on|--autostart=off|--autostart=ask)
      AUTOSTART="${arg#*=}"
      ;;
    --amd-gpu)
      AMD_GPU=1
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--autostart=on|off|ask] [--amd-gpu]" >&2
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

# --- input-Gruppe fuer evdev (globaler Hotkey ohne Root) ---
if ! groups | grep -qw input; then
  echo "Adding $USER to 'input' group (needed for global hotkey)..."
  sudo usermod -aG input "$USER"
  echo "⚠️  Gruppenaenderung wird erst nach erneutem Login aktiv."
  echo "   Nach der Installation bitte ab- und wieder anmelden (oder 'newgrp input')."
fi

# --- System dependencies for PyGObject / AT-SPI (terminal detection) ---
echo "Installing system dependencies for AT-SPI terminal detection..."
sudo apt install -y libgirepository-2.0-dev gir1.2-atspi-2.0

# --- ydotool v1.x fuer Tastatureingabe (Wayland + X11) ---
# The distro package (v0.1.8) is too old; v1.x uses raw keycodes and requires
# ydotoold.  Build from source if no working v1.x is found.
_need_ydotool_build=0
if command -v ydotool >/dev/null 2>&1; then
  # v1.x prints "Usage: ydotool <cmd>" while v0.x prints "Usage: ydotool <tool>"
  if ! ydotool key "" >/dev/null 2>&1; then
    echo "ydotool found but too old (v0.x). Building v1.x from source..."
    _need_ydotool_build=1
  fi
else
  _need_ydotool_build=1
fi

if [[ "${_need_ydotool_build}" -eq 1 ]]; then
  echo "Building ydotool v1.x from source (needed for keyboard input on Wayland)..."
  sudo apt install -y cmake scdoc libevdev-dev build-essential git
  _ydotool_tmp="$(mktemp -d)"
  git clone --depth 1 --branch v1.0.4 https://github.com/ReimuNotMoe/ydotool.git "${_ydotool_tmp}"
  cmake -S "${_ydotool_tmp}" -B "${_ydotool_tmp}/build"
  cmake --build "${_ydotool_tmp}/build" --parallel
  sudo cmake --install "${_ydotool_tmp}/build"
  rm -rf "${_ydotool_tmp}"
fi

# Ensure ydotoold user service is installed and running.
if command -v systemctl >/dev/null 2>&1; then
  _svc_dir="${HOME}/.config/systemd/user"
  mkdir -p "${_svc_dir}"
  if [[ ! -f "${_svc_dir}/ydotoold.service" ]]; then
    cat > "${_svc_dir}/ydotoold.service" <<'SVC_EOF'
[Unit]
Description=ydotoold - ydotool daemon

[Service]
ExecStart=/usr/local/bin/ydotoold
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
SVC_EOF
  fi
  systemctl --user daemon-reload
  systemctl --user enable --now ydotoold >/dev/null 2>&1 || true
fi

# ---------------------------------------------------------------------------
# AMD GPU (ROCm) install path — uses venv + CTranslate2 ROCm wheel
# ---------------------------------------------------------------------------
if [[ "${AMD_GPU}" -eq 1 ]]; then

  # Check ROCm runtime
  if ! command -v hipconfig >/dev/null 2>&1 || ! command -v rocminfo >/dev/null 2>&1; then
    echo "⚠️  ROCm runtime not found (hipconfig/rocminfo missing)." >&2
    echo "   Install ROCm first: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/" >&2
    echo "   Then re-run this script with --amd-gpu." >&2
    exit 1
  fi

  # Check build dependencies
  for cmd in git cmake ninja-build; do
    real_cmd="${cmd}"
    # ninja-build package provides the 'ninja' command
    [[ "$cmd" == "ninja-build" ]] && real_cmd="ninja"
    if ! command -v "${real_cmd}" >/dev/null 2>&1; then
      echo "Missing build dependency: ${cmd}" >&2
      echo "Install with: sudo apt install -y build-essential git cmake ninja-build pkg-config libnuma-dev" >&2
      exit 1
    fi
  done

  VENV_DIR="${REPO_ROOT}/.venv"
  CT2_DIR="${HOME}/CTranslate2"
  LAUNCHER="${HOME}/.local/bin/hotkey-transcriber"

  # Detect GPU architecture
  GPU_ARCH="$(rocminfo | grep -o 'gfx[0-9]\+' | head -n 1 || true)"
  if [[ -z "${GPU_ARCH}" ]]; then
    echo "Could not detect GPU architecture from rocminfo." >&2
    exit 1
  fi
  echo "Detected GPU architecture: ${GPU_ARCH}"

  ROCM_LLVM_BIN="$(hipconfig -l)"
  ROCM_ROOT="$(hipconfig -R)"

  # --- venv setup ---
  echo "Setting up venv at ${VENV_DIR}..."
  python3 -m venv --clear "${VENV_DIR}"
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"

  pip install --upgrade pip
  pip install -U wheel setuptools ninja "cmake>=3.29,<4"

  # --- Clone / update CTranslate2 ---
  echo "Preparing CTranslate2 source..."
  if [[ -d "${CT2_DIR}/.git" ]]; then
    git -C "${CT2_DIR}" fetch --all --tags
    git -C "${CT2_DIR}" pull --ff-only
    git -C "${CT2_DIR}" submodule update --init --recursive
  else
    rm -rf "${CT2_DIR}"
    git clone --recurse-submodules https://github.com/OpenNMT/CTranslate2.git "${CT2_DIR}"
  fi

  # --- Find libomp.so from ROCm ---
  OMP_LIB="$(find /opt/rocm* -path '*/lib/llvm/lib/libomp.so' 2>/dev/null | head -n 1 || true)"
  if [[ -z "${OMP_LIB}" || ! -f "${OMP_LIB}" ]]; then
    echo "Could not find libomp.so from ROCm. Build may fail." >&2
  fi

  # --- Build CTranslate2 with HIP ---
  echo "Building CTranslate2 with HIP for ${GPU_ARCH}..."
  cd "${CT2_DIR}"
  rm -rf build

  export CC="${ROCM_LLVM_BIN}/clang"
  export CXX="${ROCM_LLVM_BIN}/clang++"
  export HIPCXX="${ROCM_LLVM_BIN}/clang"
  export HIP_PATH="${ROCM_ROOT}"

  CMAKE_ARGS=(
    -S . -B build -G Ninja
    -DWITH_MKL=OFF
    -DWITH_HIP=ON
    -DBUILD_TESTS=OFF
    -DCMAKE_HIP_ARCHITECTURES="${GPU_ARCH}"
    -DCMAKE_PREFIX_PATH="${ROCM_ROOT}"
  )
  if [[ -n "${OMP_LIB}" && -f "${OMP_LIB}" ]]; then
    CMAKE_ARGS+=(-DIOMP5_LIBRARY="${OMP_LIB}")
  fi

  cmake "${CMAKE_ARGS[@]}"
  cmake --build build --parallel
  cmake --install build --prefix "${VENV_DIR}"

  # --- Build and install CTranslate2 Python wheel ---
  echo "Building CTranslate2 Python wheel..."
  cd "${CT2_DIR}/python"
  pip install -r install_requirements.txt
  export CTRANSLATE2_ROOT="${VENV_DIR}"
  python setup.py bdist_wheel
  pip install --force-reinstall dist/*.whl

  cd "${REPO_ROOT}"

  # Install faster-whisper (uses the already-installed ctranslate2)
  pip install faster-whisper

  # Install hotkey-transcriber itself
  pip install -e "${REPO_ROOT}"

  # Verify GPU support
  echo ""
  echo "Verifying GPU support..."
  # Need LD_LIBRARY_PATH for the freshly built libs
  export LD_LIBRARY_PATH="${VENV_DIR}/lib:${ROCM_ROOT}/lib:${ROCM_ROOT}/lib/llvm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  python3 -c "
import ctranslate2 as ct2
print('ctranslate2:', ct2.__version__)
for dev in ('hip', 'cuda'):
    try:
        types = ct2.get_supported_compute_types(dev)
        print(f'  {dev}: {types}')
    except (ValueError, RuntimeError):
        pass
try:
    count = ct2.get_cuda_device_count()
    print(f'  GPU devices visible: {count}')
except Exception:
    pass
" || echo "  (verification skipped — run hotkey-transcriber to test)"

  # Create launcher script
  mkdir -p "$(dirname "${LAUNCHER}")"
  cat > "${LAUNCHER}" <<LAUNCHER_EOF
#!/usr/bin/env bash
# Auto-generated launcher for hotkey-transcriber (AMD GPU / ROCm)
export LD_LIBRARY_PATH="${VENV_DIR}/lib:${ROCM_ROOT}/lib:${ROCM_ROOT}/lib/llvm/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
source "${VENV_DIR}/bin/activate"
exec python3 -c "from hotkey_transcriber.main import main; main()" "\$@"
LAUNCHER_EOF
  chmod +x "${LAUNCHER}"
  echo "Launcher created at ${LAUNCHER}"

# ---------------------------------------------------------------------------
# Standard install path — uses pipx (unchanged)
# ---------------------------------------------------------------------------
else

  if ! command -v pipx >/dev/null 2>&1; then
    echo "pipx not found - installing with python3..."
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    echo "pipx installed. Reopen your shell if pipx is still not found in PATH."
  fi

  echo "Installing hotkey-transcriber with pipx..."
  pipx install --force "${REPO_ROOT}"

fi

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
