# Architecture

## Overview

Hotkey Transcriber is a live-dictation tool. It captures audio while a hotkey is held (or after a wake word is detected), transcribes it with Whisper, and types the result into the active window.

## Module Map

```
src/hotkey_transcriber/
├── main.py                          # Qt5 tray app, menu, callbacks, entry point
├── app_log_capture.py               # stdout/stderr → log file (TeeStream)
├── hotkey_change_dialog.py          # Qt5 dialog to capture a new hotkey
│
├── config/
│   └── config_manager.py            # JSON config load/save (~/.config/…/config.json)
│
├── whisper_backend_selector.py      # GPU detection → backend/device/compute_type
├── compute_device_detector.py       # CTranslate2 CUDA/HIP/CPU probe
├── model_and_recorder_factory.py    # Download model, assemble SpeechRecorder
│
├── speech_recorder.py               # Audio capture, Silero VAD, Whisper transcription
├── keyboard_listener.py             # Platform hotkey listener (Win32/evdev/keyboard)
├── keyboard_controller.py           # Text input (pyautogui / ydotool / Win32)
├── resource_path_resolver.py        # Resolve bundled resource paths (icons)
│
├── wake_word_listener.py            # openwakeword background listener
├── wake_word_script_actions.py      # Wake-word → script/builtin action mapping
├── spoken_text_actions.py           # Transcribed text → trigger → action matching
├── action_settings_ui_rows.py       # Qt5 row widgets for configuring actions
│
├── wsl_whisper_bridge.py            # WSL subprocess bridge (Windows AMD GPU)
├── whisper_cpp_backend.py           # whisper.cpp fallback (Windows AMD)
│
├── autostart.py                     # Platform autostart (Windows registry / .desktop)
├── builtin_scripts/
│   ├── __init__.py                  # Builtin script registry + executor
│   └── browser_temporary_chat_firefox.py
└── resources/
    ├── icon/                        # Application icons
    ├── lib/linux/x86_64/            # Vendored PortAudio/JACK libraries
    └── wakewords/                   # Custom .onnx wake word models
```

## Event Flow

```
Hotkey press  ──────────────────────────────────────────────────────┐
                                                                     │
Wake word detected ─────────────────────────────────────────────┐   │
                                                                 ▼   ▼
                                                        SpeechRecorder.start()
                                                                 │
                                             ┌───────────────────┘
                                             ▼
                                     sounddevice InputStream
                                     (16kHz, float32)
                                             │
                              ┌──────────────┼─────────────────┐
                              ▼              ▼                  ▼
                          audio queue    Silero VAD        (auto-stop)
                                             │
                                       silence timeout → SpeechRecorder.stop()
                                             │
                                    Whisper transcription
                                    (faster-whisper / whisper.cpp / WSL)
                                             │
                              ┌──────────────┼──────────────────┐
                              ▼              ▼                  ▼
                     SpokenTextActions  spoken "Enter"    plain text
                     match & execute        │                   │
                                           ▼                   ▼
                                   KeyboardController.press()  .paste()
```

## Backend Selection

```
resolve_backend(config)
       │
       ├─ env HOTKEY_TRANSCRIBER_BACKEND=wsl_amd ──► WslWhisperModel
       │
       ├─ Windows + AMD + WSL-ROCm ready ──────────► WslWhisperModel
       │
       ├─ Linux + AMD GPU ─────────────────────────► WhisperModel (HIP/CTranslate2)
       │
       ├─ Windows + AMD GPU (no WSL) ─────────────► WhisperCppModel (whisper.cpp Vulkan)
       │
       └─ NVIDIA / CPU ────────────────────────────► WhisperModel (CUDA/CPU/CTranslate2)
```

## Key Design Decisions

- **Push-to-talk**: The hotkey listener uses evdev on Linux (Wayland-compatible, no root) and a Win32 low-level hook on Windows, suppressing the trigger key at the OS level during recording.
- **Wake word**: openwakeword runs in a background thread with its own sounddevice stream, which is paused/resumed around recordings so both streams don't compete for the microphone.
- **Silero VAD**: Used for auto-stop in wake-word mode — recording stops automatically after silence, avoiding manual key press.
- **WSL bridge**: On Windows AMD GPUs where CTranslate2/HIP crashes (RDNA 4), a Python server is spawned inside WSL and communicates via JSON over stdin/stdout.
- **Config persistence**: All settings are stored in `~/.config/hotkey-transcriber/config.json` and reloaded on startup.
