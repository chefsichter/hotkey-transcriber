#!/usr/bin/env python3
"""Whisper NPU inference server.

Runs persistently in the ryzen-ai-1.7.0 conda environment.
Protocol: line-delimited JSON on stdin/stdout.
  stdin:  {"wav_path": "...", "language": "de"/"auto"}
  stdout: {"text": "..."} or {"error": "..."}
  First stdout line after startup: {"status": "ready"}
"""

import argparse
import json
import sys
import traceback
import wave

import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--encoder", required=True, help="Path to encoder ONNX model")
    p.add_argument("--decoder", required=True, help="Path to decoder ONNX model")
    p.add_argument("--model-id", required=True, help="HuggingFace model ID for processor")
    p.add_argument("--vaip-config", required=True, help="Path to vaip_config.json")
    p.add_argument("--cache-dir", required=True, help="VitisAI NPU compilation cache dir")
    return p.parse_args()


def load_sessions(encoder_path, decoder_path, vaip_config, cache_dir, model_id):
    import onnxruntime as ort

    # Cache key includes model id so different models don't share/overwrite the cache
    safe_model_id = model_id.replace("/", "_").replace("\\", "_")

    # Encoder: VitisAI EP (NPU) with CPU fallback
    encoder = ort.InferenceSession(
        encoder_path,
        providers=["VitisAIExecutionProvider", "CPUExecutionProvider"],
        provider_options=[
            {
                "config_file": vaip_config,
                "cache_dir": cache_dir,
                "cache_key": f"whisper_encoder_npu_{safe_model_id}",
            },
            {},
        ],
    )

    # Decoder: VitisAI EP (NPU) with CPU fallback
    decoder = ort.InferenceSession(
        decoder_path,
        providers=["VitisAIExecutionProvider", "CPUExecutionProvider"],
        provider_options=[
            {
                "config_file": vaip_config,
                "cache_dir": cache_dir,
                "cache_key": f"whisper_decoder_npu_{safe_model_id}",
            },
            {},
        ],
    )

    return encoder, decoder


def infer_dtype(session_input):
    """Return numpy dtype from ONNX tensor type string."""
    t = session_input.type  # e.g. "tensor(float16)" or "tensor(float)"
    if "float16" in t:
        return np.float16
    return np.float32


def greedy_decode(decoder, enc_hidden, tokenizer, language):
    """Simple greedy decoding loop."""
    dec_inputs = decoder.get_inputs()
    dec_output_names = [o.name for o in decoder.get_outputs()]

    # First output is logits
    logits_name = dec_output_names[0]

    # Detect which input is token ids (int) vs encoder hidden states (float).
    # AMD models use "x"/"xa" naming; HuggingFace Optimum uses "input_ids"/"encoder_hidden_states".
    token_inp = None
    enc_hs_inp = None
    for inp in dec_inputs:
        if "int" in inp.type:
            token_inp = inp
        else:
            enc_hs_inp = inp

    if token_inp is None:
        # Fallback: first input is tokens, second is encoder states
        token_inp = dec_inputs[0]
        enc_hs_inp = dec_inputs[1] if len(dec_inputs) > 1 else None

    # Build prompt tokens
    sot = tokenizer.convert_tokens_to_ids("<|startoftranscript|>")
    eot = tokenizer.eos_token_id
    task_tok = tokenizer.convert_tokens_to_ids("<|transcribe|>")
    nots_tok = tokenizer.convert_tokens_to_ids("<|notimestamps|>")

    if language and language != "auto":
        lang_tok = tokenizer.convert_tokens_to_ids(f"<|{language}|>")
    else:
        lang_tok = tokenizer.convert_tokens_to_ids("<|multilingual|>")

    ids = [sot, lang_tok, task_tok, nots_tok]
    max_new_tokens = 100  # Static-shape CPU decoder is slow for large models; 100 ≈ ~75 words

    enc_hs_dtype = infer_dtype(enc_hs_inp) if enc_hs_inp else np.float32

    # Detect static sequence length from the token input shape (e.g. AMD exports use [1, 448])
    static_seq_len = None
    if token_inp.shape and len(token_inp.shape) >= 2:
        dim1 = token_inp.shape[1]
        if isinstance(dim1, int) and dim1 > 0:
            static_seq_len = dim1

    for _ in range(max_new_tokens):
        n = len(ids)
        if static_seq_len is not None:
            # Pad to static length; read logit at position of last real token
            padded = np.zeros([1, static_seq_len], dtype=np.int64)
            padded[0, :n] = ids
            input_ids = padded
        else:
            input_ids = np.array([ids], dtype=np.int64)

        dec_feed = {token_inp.name: input_ids}
        if enc_hs_inp:
            dec_feed[enc_hs_inp.name] = enc_hidden.astype(enc_hs_dtype)

        out = decoder.run([logits_name], dec_feed)[0]  # [1, seq, vocab]
        # For static-shape models use position of last real token; dynamic use last position
        logit_pos = n - 1 if static_seq_len is not None else -1
        next_token = int(np.argmax(out[0, logit_pos, :]))
        if next_token == eot:
            break
        ids.append(next_token)

    return tokenizer.decode(ids, skip_special_tokens=True).strip()


def main():
    args = parse_args()

    from transformers import WhisperFeatureExtractor, WhisperTokenizer

    print("[NPU] Lade Feature Extractor und Tokenizer...", file=sys.stderr, flush=True)
    fe = WhisperFeatureExtractor.from_pretrained(args.model_id)
    tokenizer = WhisperTokenizer.from_pretrained(args.model_id)

    print("[NPU] Lade ONNX-Modelle (Encoder auf NPU kompilieren kann beim ersten Mal Minuten dauern)...",
          file=sys.stderr, flush=True)
    encoder, decoder = load_sessions(args.encoder, args.decoder, args.vaip_config, args.cache_dir, args.model_id)

    enc_inp_name = encoder.get_inputs()[0].name
    enc_inp_dtype = infer_dtype(encoder.get_inputs()[0])
    enc_out_name = encoder.get_outputs()[0].name

    print(json.dumps({"status": "ready"}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            wav_path = req["wav_path"]
            language = req.get("language") or "auto"

            # Load WAV
            with wave.open(wav_path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(frames, np.int16).astype(np.float32) / 32767.0

            # Mel spectrogram
            feats = fe(audio, sampling_rate=16000, return_tensors="np")
            input_features = feats.input_features.astype(enc_inp_dtype)

            # Encoder on NPU
            enc_hidden = encoder.run([enc_out_name], {enc_inp_name: input_features})[0]

            # Greedy decode on CPU
            text = greedy_decode(decoder, enc_hidden, tokenizer, language)

            print(json.dumps({"text": text}), flush=True)

        except Exception as e:
            print(json.dumps({"error": str(e), "trace": traceback.format_exc()}), flush=True)


if __name__ == "__main__":
    main()
