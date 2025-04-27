#!/usr/bin/env python3
"""Setzt eine Conda-Umgebung für Hotkey-Transcriber mit CTranslate2-ROCm auf."""

import os
import sys

sys.path.append(os.path.dirname(__file__))
import json
import pathlib
import subprocess
import shutil

from conda_helper import prepend_ld_library_path

ENV_NAME = "hotkey_transcriber"
REPO_URL = "https://github.com/arlo-phoenix/CTranslate2-rocm.git"


def run(cmd: str, **kw):
    print(">>>", cmd)
    subprocess.check_call(cmd, shell=True, **kw)


def get_env_prefix(name: str) -> pathlib.Path:
    """Liefert den absoluten Pfad zu einer Conda-Env anhand ihres Namens."""
    out = subprocess.check_output(["conda", "env", "list", "--json"], text=True)
    env_paths = json.loads(out)["envs"]
    for p in env_paths:
        if pathlib.Path(p).name == name:
            return pathlib.Path(p)
    raise RuntimeError(f"Conda-Umgebung '{name}' nicht gefunden")


def add_rocm_path(env_name: str = ENV_NAME) -> None:
    """
    Hängt /opt/rocm/llvm/lib und <env>/lib an LD_LIBRARY_PATH
    **der angegebenen Conda-Umgebung** und legt ein activate.d-Snippet an.
    """
    llvm_dir = pathlib.Path("/opt/rocm/llvm/lib")
    if not llvm_dir.exists():
        print("ℹ️  ROCm LLVM-Verzeichnis nicht gefunden – Schritt übersprungen")
        return

    prepend_ld_library_path(llvm_dir)

    env_prefix = get_env_prefix(env_name)
    activate_d = env_prefix / "etc" / "conda" / "activate.d"
    activate_d.mkdir(parents=True, exist_ok=True)
    snippet = activate_d / "rocm-ldlibpath.sh"
    snippet.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# Hotkey-Transcriber ROCm-Patch",
                f'export LD_LIBRARY_PATH="{llvm_dir}:$LD_LIBRARY_PATH"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    # Optional: Dateiattribute setzen (Unix-Ausführbar)
    snippet.chmod(0o755)

    print(f"ℹ️  LD_LIBRARY_PATH dauerhaft erweitert → {snippet}")


def create_launcher(env_name: str = ENV_NAME) -> None:
    """
    Legt ~/.local/bin/hotkey-transcriber an, das immer
    'conda run -n <env> hotkey-transcriber "$@"' aufruft.
    """
    launcher = pathlib.Path.home() / ".local" / "bin" / "hotkey-transcriber"
    launcher.parent.mkdir(parents=True, exist_ok=True)

    launcher.write_text(
        "#!/usr/bin/env bash\n"
        "# Auto-generated: starte Hotkey-Transcriber in Conda-Env\n"
        "# 1) Conda initialisieren (Miniconda- oder Anaconda-Install)\n"
        'for croot in "$HOME/miniconda3" "$HOME/anaconda3"; do\n'
        '  if [ -f "$croot/etc/profile.d/conda.sh" ]; then\n'
        '    source "$croot/etc/profile.d/conda.sh"\n'
        "    break\n"
        "  fi\n"
        "done\n"
        "\n"
        "# 2) Umgebung aktivieren\n"
        f"conda activate {env_name} || {{ echo \"Konnte Env '{env_name}' nicht aktivieren\" >&2; exit 1; }}\n"
        "\n"
        "# 3) Programm starten – absoluter Pfad vermeidet Rekursion\n"
        'exec "$CONDA_PREFIX/bin/hotkey-transcriber" "$@"\n',
        encoding="utf-8",
    )

    launcher.chmod(0o755)
    print(f"ℹ️  Starter erstellt → {launcher}")


def main():
    # 0) Alte Umgebung und Quellen entfernen
    print(f"ℹ️  Entferne bestehende Conda-Umgebung '{ENV_NAME}' (falls vorhanden)")
    # conda env remove (ignore error)
    run(f"conda env remove -y -n {ENV_NAME} || true")
    # altes CTranslate2-rocm Verzeichnis löschen
    old_dir = pathlib.Path("CTranslate2-rocm")
    if old_dir.exists() and old_dir.is_dir():
        print(f"ℹ️  Entferne altes Verzeichnis {old_dir}")
        shutil.rmtree(old_dir)
    # 1) Conda-env anlegen
    try:
        run(f"conda create -y -n {ENV_NAME} python")
    except subprocess.CalledProcessError:
        print(f"ℹ️  Env '{ENV_NAME}' existiert bereits, verwende bestehendes")

    # 1a) Installiere moderne libstdc++ (libstdcxx-ng) für aktuelle GLIBCXX-Versionen
    print(f"ℹ️  Installiere moderne libstdc++ in Env '{ENV_NAME}'")
    run(f"conda install -y -n {ENV_NAME} -c conda-forge libstdcxx-ng")

    # 1b) Intel OpenMP-Laufzeit installieren (für CTranslate2 build)
    print(f"ℹ️  Installiere Intel OpenMP-Laufzeit in Env '{ENV_NAME}'")
    run(f"conda install -y -n {ENV_NAME} -c anaconda intel-openmp")

    # 2) CTranslate2-ROCm klonen, bauen und installieren
    build_steps = [
        f"git clone --recurse-submodules {REPO_URL} || true",
        "cd CTranslate2-rocm",
        'export PYTORCH_ROCM_ARCH=$(rocminfo | grep -o "gfx[0-9]\\+" | head -1)',
        "export CLANG_CMAKE_CXX_COMPILER=clang++",
        'export CC="$(hipconfig -l)/clang"',
        'export CXX="$(hipconfig -l)/clang++"',
        'export HIPCXX="$(hipconfig -l)/clang"',
        'export HIP_PATH="$(hipconfig -R)"',
        'cmake -S . -B build -DWITH_MKL=OFF -DWITH_HIP=ON -DCMAKE_HIP_ARCHITECTURES="$PYTORCH_ROCM_ARCH" -DBUILD_TESTS=ON -DWITH_CUDNN=ON -DIOMP5_LIBRARY=$CONDA_PREFIX/lib/libiomp5.so',
        "cmake --build build -- -j$(nproc)",
        'cmake --install build --prefix "$CONDA_PREFIX"',
        'export LIBRARY_PATH="$CONDA_PREFIX/lib:$LIBRARY_PATH"',
        'export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"',
        "cd python",
        "pip install -r install_requirements.txt",
        "python setup.py bdist_wheel",
        "pip install dist/*.whl",
    ]
    # Führe Build in der Umgebung über bash aus
    script = " && ".join(build_steps)
    run(f"conda run -n {ENV_NAME} bash -lc '{script}'")

    # 3) Hotkey-Transcriber installieren
    run(f"conda run -n {ENV_NAME} pip install -e .")

    # 4) LD_LIBRARY_PATH setzen
    add_rocm_path(ENV_NAME)

    # 5) Launcher erstellen
    create_launcher(ENV_NAME)


if __name__ == "__main__":
    main()
