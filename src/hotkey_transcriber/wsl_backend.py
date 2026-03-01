import atexit
import json
import os
import shlex
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np


SERVER_SCRIPT = r'''
import argparse
import json
import os
import shutil
import sys

from faster_whisper import WhisperModel, download_model
from huggingface_hub.errors import LocalEntryNotFoundError
from huggingface_hub.utils import HfHubHTTPError
import ctranslate2 as ct2


def detect_device():
    try:
        if getattr(ct2, "get_cuda_device_count", lambda: 0)() > 0:
            return "cuda"
    except RuntimeError:
        pass

    try:
        if ct2.get_supported_compute_types("hip"):
            return "hip"
    except Exception:
        pass

    return "cpu"


def emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _snapshot_has_model_bin(model_path):
    return os.path.isfile(os.path.join(model_path, "model.bin"))


def _repair_and_download(model_name, model_path):
    # Remove broken snapshot and force a clean download.
    try:
        if os.path.isdir(model_path):
            shutil.rmtree(model_path, ignore_errors=True)
    except Exception:
        pass
    return download_model(model_name, local_files_only=False)


def _resolve_model_path(model_name):
    try:
        model_path = download_model(model_name, local_files_only=True)
    except (ValueError, HfHubHTTPError, LocalEntryNotFoundError):
        model_path = download_model(model_name, local_files_only=False)

    if not _snapshot_has_model_bin(model_path):
        model_path = _repair_and_download(model_name, model_path)
        if not _snapshot_has_model_bin(model_path):
            raise RuntimeError(
                f"Model '{model_name}' does not contain model.bin and is not a faster-whisper/ctranslate2 model."
            )

    return model_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    model_path = _resolve_model_path(args.model)

    device = detect_device()
    compute_type = "float16" if device in ("cuda", "hip") else "float32"
    try:
        model = WhisperModel(model_path, device=device, compute_type=compute_type, local_files_only=True)
    except RuntimeError:
        # Final safety net for stale snapshots or backend issues.
        model_path = _repair_and_download(args.model, model_path)
        if not _snapshot_has_model_bin(model_path):
            raise RuntimeError(
                f"Model '{args.model}' does not contain model.bin and is not a faster-whisper/ctranslate2 model."
            )
        model = WhisperModel(model_path, device=device, compute_type=compute_type, local_files_only=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
            cmd = req.get("cmd")
            if cmd == "ping":
                emit({"ok": True, "device": device, "compute_type": compute_type})
                continue
            if cmd == "shutdown":
                emit({"ok": True})
                return
            if cmd != "transcribe":
                emit({"ok": False, "error": "unsupported_cmd"})
                continue

            segs, _ = model.transcribe(
                req["audio_path"],
                language=req.get("language"),
                vad_filter=req.get("vad_filter", True),
                beam_size=req.get("beam_size", 5),
                best_of=req.get("best_of", 5),
            )
            emit({"ok": True, "segments": [s.text for s in segs]})
        except Exception as exc:
            emit({"ok": False, "error": str(exc)})


if __name__ == "__main__":
    main()
'''


class _Segment:
    def __init__(self, text):
        self.text = text


def _win_to_wsl_path(path_str):
    path = Path(path_str).resolve()
    drive = path.drive[:-1].lower()
    rel = str(path).replace("\\", "/").split(":/", 1)[1]
    return f"/mnt/{drive}/{rel}"


def _run_wsl(script):
    try:
        return subprocess.check_output(
            ["wsl.exe", "-e", "bash", "-lc", script],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.output or "").strip()
        if details:
            raise RuntimeError(f"WSL command failed: {details}") from exc
        raise


class WslWhisperModel:
    def __init__(self, model_name):
        self.model_name = model_name
        self._io_lock = threading.Lock()
        self._server = None

        local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home()))
        self._work_dir = Path(local_appdata) / "hotkey-transcriber"
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._script_path = self._work_dir / "wsl_backend_server.py"
        self._script_path.write_text(SERVER_SCRIPT, encoding="utf-8")

        self._ensure_wsl_backend(force=False)
        self._start_server()
        atexit.register(self.close)

    def _ensure_wsl_backend(self, force=False):
        marker = self._work_dir / "wsl_backend_ready"
        if marker.exists() and not force:
            return

        setup_cmd = (
            "set -e;"
            "python3 -m venv ~/.hotkey-transcriber-wsl;"
            "source ~/.hotkey-transcriber-wsl/bin/activate;"
            "pip install -U pip;"
            "pip install -U faster-whisper huggingface_hub"
        )
        print("Initialisiere WSL-Backend (einmalig)...")
        _run_wsl(setup_cmd)
        marker.write_text("ok\n", encoding="utf-8")

    def _start_server(self):
        script_wsl = _win_to_wsl_path(str(self._script_path))
        script_arg = shlex.quote(script_wsl)
        model_arg = shlex.quote(self.model_name)
        venv_lib = "$HOME/.hotkey-transcriber-wsl/lib"
        rocm_llvm_lib = "/opt/rocm-7.2.0/lib/llvm/lib"
        token_exports = []
        for token_var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
            token_val = os.environ.get(token_var)
            if token_val:
                token_exports.append(f"export {token_var}={shlex.quote(token_val)}")
        token_prefix = (" && ".join(token_exports) + " && ") if token_exports else ""
        cmd = (
            "source ~/.hotkey-transcriber-wsl/bin/activate && "
            "export LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=UTF-8 && "
            f"export LD_LIBRARY_PATH={venv_lib}:{rocm_llvm_lib}:$LD_LIBRARY_PATH && "
            f"{token_prefix}"
            f"exec python3 -u {script_arg} --model {model_arg}"
        )

        self._server = subprocess.Popen(
            ["wsl.exe", "-e", "bash", "-lc", cmd],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        reply = self._request({"cmd": "ping"}, timeout=600)
        if not reply.get("ok"):
            raise RuntimeError(f"WSL-Backend konnte nicht gestartet werden: {reply}")

        device = reply.get("device", "cpu")
        compute_type = reply.get("compute_type", "float32")
        print(f"WSL-Backend bereit (device={device}, compute_type={compute_type}).")
        if device == "cpu":
            print("Hinweis: WSL-Backend laeuft ohne HIP-Beschleunigung (ctranslate2 ohne HIP-Support).")

    def _request(self, payload, timeout=120):
        if not self._server or not self._server.stdin or not self._server.stdout:
            raise RuntimeError("WSL backend process is not running.")

        line = json.dumps(payload, ensure_ascii=False)

        with self._io_lock:
            self._server.stdin.write(line + "\n")
            self._server.stdin.flush()

            done = threading.Event()
            holder = {"line": None}

            def reader():
                holder["line"] = self._server.stdout.readline()
                done.set()

            t = threading.Thread(target=reader, daemon=True)
            t.start()
            if not done.wait(timeout):
                raise TimeoutError("WSL backend request timed out.")

            raw = (holder["line"] or "").strip()
            if not raw:
                err = ""
                if self._server.stderr:
                    err = self._server.stderr.read()
                raise RuntimeError(f"WSL backend closed unexpectedly. {err}")

            return json.loads(raw)

    def transcribe(self, audio, language=None, vad_filter=True, beam_size=5, best_of=5):
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            prefix="ht_",
            dir=self._work_dir,
            delete=False,
        ) as tmp:
            wav_path = Path(tmp.name)

        try:
            arr = np.asarray(audio).reshape(-1)
            arr = np.clip(arr, -1.0, 1.0)
            pcm = (arr * 32767.0).astype(np.int16)

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm.tobytes())

            req = {
                "cmd": "transcribe",
                "audio_path": _win_to_wsl_path(str(wav_path)),
                "language": language,
                "vad_filter": vad_filter,
                "beam_size": beam_size,
                "best_of": best_of,
            }
            reply = self._request(req, timeout=300)
            if not reply.get("ok"):
                raise RuntimeError(reply.get("error", "WSL transcribe failed."))

            segments = [_Segment(text=t) for t in reply.get("segments", [])]
            return iter(segments), {}
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except OSError:
                pass

    def close(self):
        if not self._server:
            return
        try:
            self._request({"cmd": "shutdown"}, timeout=5)
        except Exception:
            pass
        try:
            self._server.terminate()
        except Exception:
            pass
        self._server = None

