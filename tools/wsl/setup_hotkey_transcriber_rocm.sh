#!/usr/bin/env bash
set -euo pipefail

SKIP_ROCM_INSTALL=0
SKIP_CT2_BUILD=0

for arg in "$@"; do
  case "$arg" in
    --skip-rocm-install) SKIP_ROCM_INSTALL=1 ;;
    --skip-ct2-build) SKIP_CT2_BUILD=1 ;;
    *)
      echo "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

VENV_DIR="${HOME}/.hotkey-transcriber-wsl"
CT2_DIR="${HOME}/CTranslate2"

echo "[1/7] Installing base packages..."
sudo apt update
sudo apt install -y \
  ca-certificates \
  wget \
  curl \
  gnupg \
  git \
  build-essential \
  pkg-config \
  libnuma-dev \
  python3-pip \
  python3-venv

if [[ "$SKIP_ROCM_INSTALL" -eq 0 ]]; then
  echo "[2/7] Installing ROCm for WSL..."
  source /etc/os-release
  CODENAME="${VERSION_CODENAME:-}"
  if [[ "$CODENAME" != "noble" && "$CODENAME" != "jammy" ]]; then
    echo "Unsupported Ubuntu codename: ${CODENAME}"
    echo "Supported by this installer: jammy (22.04), noble (24.04)"
    exit 1
  fi

  AMD_BASE_URL="https://repo.radeon.com/amdgpu-install/latest/ubuntu/${CODENAME}"
  AMD_DEB_NAME="$(wget -qO- "${AMD_BASE_URL}/" | grep -Eo 'amdgpu-install_[^" ]+_all\.deb' | head -n 1 || true)"
  if [[ -z "${AMD_DEB_NAME}" ]]; then
    echo "Could not resolve amdgpu-install package from ${AMD_BASE_URL}"
    echo "Check AMD docs and install amdgpu-install manually, then rerun with --skip-rocm-install."
    exit 1
  fi

  if [[ ! -f "${AMD_DEB_NAME}" ]]; then
    wget "${AMD_BASE_URL}/${AMD_DEB_NAME}"
  fi
  sudo apt install -y "./${AMD_DEB_NAME}"
  sudo amdgpu-install -y --usecase=wsl,rocm --no-dkms
fi

echo "[3/7] Verifying ROCm visibility..."
if ! command -v rocminfo >/dev/null 2>&1; then
  echo "rocminfo not found. ROCm install incomplete."
  exit 1
fi
rocminfo | grep -E "Name:|gfx" | head -n 20 || true

echo "[4/7] Creating venv for hotkey-transcriber backend..."
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install -U pip
pip install -U wheel setuptools ninja "cmake==3.29.6" faster-whisper huggingface_hub

if [[ "$SKIP_CT2_BUILD" -eq 0 ]]; then
  echo "[5/7] Building CTranslate2 (HIP) from source..."
  if [[ -d "${CT2_DIR}/.git" ]]; then
    git -C "${CT2_DIR}" fetch --all --tags
    git -C "${CT2_DIR}" pull --ff-only
    git -C "${CT2_DIR}" submodule update --init --recursive
  else
    rm -rf "${CT2_DIR}"
    git clone --recurse-submodules https://github.com/OpenNMT/CTranslate2.git "${CT2_DIR}"
  fi

  ROCM_LLVM_BIN="$(hipconfig -l)"
  ROCM_ROOT="$(hipconfig -R)"
  GPU_ARCH="$(rocminfo | grep -o 'gfx[0-9]\+' | head -n 1 || true)"
  if [[ -z "${GPU_ARCH}" ]]; then
    echo "Could not detect GPU architecture from rocminfo."
    exit 1
  fi

  OMP_LIB="/opt/rocm-7.2.0/lib/llvm/lib/libomp.so"
  if [[ ! -f "${OMP_LIB}" ]]; then
    OMP_LIB="$(find /opt/rocm* -path '*/lib/llvm/lib/libomp.so' | head -n 1 || true)"
  fi
  if [[ -z "${OMP_LIB}" || ! -f "${OMP_LIB}" ]]; then
    echo "Could not find libomp.so from ROCm."
    exit 1
  fi

  cd "${CT2_DIR}"
  rm -rf build
  export CLANG_CMAKE_CXX_COMPILER=clang++
  export CC="${ROCM_LLVM_BIN}/clang"
  export CXX="${ROCM_LLVM_BIN}/clang++"
  export HIPCXX="${ROCM_LLVM_BIN}/clang"
  export HIP_PATH="${ROCM_ROOT}"

  cmake -S . -B build -G Ninja \
    -DWITH_MKL=OFF \
    -DWITH_HIP=ON \
    -DBUILD_TESTS=OFF \
    -DCMAKE_HIP_ARCHITECTURES="${GPU_ARCH}" \
    -DIOMP5_LIBRARY="${OMP_LIB}"
  cmake --build build --parallel
  cmake --install build --prefix "${VENV_DIR}"

  echo "[6/7] Building and installing ctranslate2 Python wheel..."
  cd "${CT2_DIR}/python"
  pip install -r install_requirements.txt
  export CTRANSLATE2_ROOT="${VENV_DIR}"
  python setup.py bdist_wheel
  pip install --force-reinstall dist/*.whl
fi

echo "[7/7] Patching venv activation and validating backend..."
ACTIVATE_FILE="${VENV_DIR}/bin/activate"
if ! grep -q "HOTKEY_TRANSCRIBER_LD_PATCH" "${ACTIVATE_FILE}"; then
  {
    echo ""
    echo "# HOTKEY_TRANSCRIBER_LD_PATCH"
    echo "export LD_LIBRARY_PATH=\"${VENV_DIR}/lib:/opt/rocm-7.2.0/lib/llvm/lib:\${LD_LIBRARY_PATH}\""
  } >> "${ACTIVATE_FILE}"
fi

source "${VENV_DIR}/bin/activate"
python3 - <<'PY'
import ctranslate2 as ct2
print("ctranslate2:", ct2.__version__)
try:
    print("cuda_device_count:", ct2.get_cuda_device_count())
except Exception as exc:
    print("cuda_device_count error:", exc)
for dev in ("hip", "cuda", "cpu"):
    try:
        print(dev, ct2.get_supported_compute_types(dev))
    except Exception as exc:
        print(dev, "ERR", exc)
PY

echo "Done."
echo "Next on Windows:"
echo "  pipx install --force ."
echo "  \$env:HOTKEY_TRANSCRIBER_BACKEND='auto'"
echo "  hotkey-transcriber"
