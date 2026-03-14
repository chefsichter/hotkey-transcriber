import signal

from hotkey_transcriber.app_log_capture import setup_log_capture
from hotkey_transcriber.config.config_manager import load_config
from hotkey_transcriber.gui.tray_app import _DEFAULT_HOTKEY, TrayApp
from hotkey_transcriber.speech_recorder import normalize_language
from hotkey_transcriber.transcription.model_and_recorder_factory import (
    load_keyboard_listener,
    load_model,
    load_speech_recorder,
)
from hotkey_transcriber.transcription.whisper_backend_selector import resolve_backend
from hotkey_transcriber.wake_word.wake_word_listener import (
    WakeWordListener,
    list_available_wake_word_models,
)
from hotkey_transcriber.wake_word.wake_word_script_actions import (
    WakeWordScriptActionExecutor,
    load_wake_word_script_actions,
)


def _init_runtime(config: dict):
    runtime = resolve_backend(config)
    backend = runtime["backend"]
    device = runtime["device"]
    compute_type = runtime["compute_type"]
    use_torch_whisper = runtime.get("use_torch_whisper", False)

    model = load_model(
        size=config.get("model_size", "large-v3-turbo"),
        device=device,
        compute_type=compute_type,
        backend=backend,
        use_torch_whisper=use_torch_whisper,
    )

    recorder = load_speech_recorder(
        model=model,
        wait_on_keyboard=config.get("wait_on_keyboard", 0.02),
        channels=config.get("channels", 1),
        chunk_ms=config.get("chunk_ms", 30),
        language=normalize_language(config.get("language", "de")),
        rec_mark=config.get("rec_mark", "🔴 REC"),
        spoken_enter_enabled=config.get("spoken_enter_enabled", False),
        spoken_undo_enabled=config.get("spoken_undo_enabled", False),
        spoken_text_actions_enabled=config.get("spoken_text_actions_enabled", True),
        spoken_text_actions=config.get("spoken_text_actions", []),
        silence_timeout_ms=config.get("silence_timeout_ms", 1500),
        max_initial_wait_ms=config.get("max_initial_wait_ms", 5000),
    )

    hotkey = load_keyboard_listener(
        recorder, hotkey_config=config.get("hotkey", _DEFAULT_HOTKEY)
    )

    wake_word_script_actions_list = config.get(
        "wake_word_script_actions",
        config.get(
            "wake_word_actions",
            [
                {
                    "wake_word_model": "hey chat",
                    "builtin": "temporary_chat_firefox",
                    "start_recording_after": True,
                    "delay_ms": 1200,
                }
            ],
        ),
    )
    wake_word_script_action_map = load_wake_word_script_actions(wake_word_script_actions_list)
    wake_word_script_action_executor = WakeWordScriptActionExecutor(
        actions=wake_word_script_action_map,
        enabled=config.get("wake_word_script_actions_enabled", True),
    )

    available_models = set(list_available_wake_word_models())
    ww_model = str(config.get("wake_word_model", "hey jarvis")).strip()
    ww_model_names = [ww_model] if ww_model else []
    if wake_word_script_action_executor.enabled:
        for action in wake_word_script_actions_list:
            m = str(action.get("wake_word_model", "")).strip()
            if m and m in available_models and m not in ww_model_names:
                ww_model_names.append(m)

    ww_listener = WakeWordListener(
        callback=lambda _name=None: None,
        model_name=ww_model,
        model_names=ww_model_names,
    )
    if config.get("wake_word_enabled", False):
        ww_listener.start()

    return (
        backend,
        device,
        compute_type,
        use_torch_whisper,
        recorder,
        hotkey,
        ww_listener,
        wake_word_script_action_map,
        wake_word_script_action_executor,
    )


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    config = load_config()
    log_path = setup_log_capture()

    (
        backend,
        device,
        compute_type,
        use_torch_whisper,
        recorder,
        hotkey,
        ww_listener,
        wake_word_script_action_map,
        wake_word_script_action_executor,
    ) = _init_runtime(config)

    tray_app = TrayApp(
        config=config,
        recorder=recorder,
        hotkey=hotkey,
        ww_listener=ww_listener,
        wake_word_script_action_map=wake_word_script_action_map,
        wake_word_script_action_executor=wake_word_script_action_executor,
        backend=backend,
        device=device,
        compute_type=compute_type,
        use_torch_whisper=use_torch_whisper,
        log_path=log_path,
    )
    tray_app.run()


if __name__ == "__main__":
    main()
