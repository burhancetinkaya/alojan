"""Compare native CPU preprocessing/inference with pinned upstream Python APIs."""

import argparse
import audioop
import json
from pathlib import Path
import re
import subprocess
import time
import wave

import numpy as np
import onnxruntime as ort
from transformers import WhisperFeatureExtractor

ROOT = Path(__file__).resolve().parents[2]


def validate(output):
    output.mkdir(parents=True, exist_ok=False)
    extractor = WhisperFeatureExtractor(chunk_length=8)
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    models = ROOT / ".local/turn-models"
    smart = ort.InferenceSession(
        str(models / "smart-turn-v3.2-cpu.onnx"), options, providers=["CPUExecutionProvider"]
    )
    vad = ort.InferenceSession(
        str(models / "silero-v6.2.onnx"), options, providers=["CPUExecutionProvider"]
    )
    with wave.open(str(ROOT / "assets/asr/tr-v1/phone.wav")) as wav:
        pcm = audioop.ratecv(
            wav.readframes(wav.getnframes()), 2, 1, wav.getframerate(), 16000, None
        )[0]
    speech = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    rng = np.random.default_rng(3101)
    cases = {
        "silence": np.zeros(16000, np.float32),
        "noise": rng.normal(0, 0.01, 160000).astype(np.float32),
        "impulse": np.pad(np.array([0.8], np.float32), (0, 16000)),
        "phone": speech,
        "phone_pause": np.pad(speech, (0, 8000)),
        "short_fragment": speech[:24000],
    }
    results = []
    for name, audio in cases.items():
        source, destination = output / f"{name}.f32", output / f"{name}.features"
        audio.tofile(source)
        process = subprocess.run(
            [
                str(ROOT / "build/local/turn-model-probe"),
                str(models),
                str(source),
                str(destination),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        metrics = {k: float(v) for k, v in re.findall(r"(\w+)=([0-9.eE+-]+)", process.stdout)}
        padded = np.pad(audio, (max(0, 128000 - len(audio)), 0))[-128000:]
        features = extractor(
            padded,
            sampling_rate=16000,
            return_tensors="np",
            padding="max_length",
            max_length=128000,
            truncation=True,
            do_normalize=True,
        ).input_features
        native = np.fromfile(destination, dtype=np.float32).reshape(1, 80, 800)
        error = float(np.max(np.abs(features - native)))
        reference = float(smart.run(None, {"input_features": features})[0][0, 0])
        native_reference = float(smart.run(None, {"input_features": native})[0][0, 0])
        # Independent reference state/context framing from the pinned Silero interface.
        state, context, scores = np.zeros((2, 1, 128), np.float32), np.zeros(64, np.float32), []
        start = time.monotonic()
        for pos in range(0, len(audio) - 511, 512):
            chunk = audio[pos : pos + 512]
            score, state = vad.run(
                None,
                {
                    "input": np.concatenate([context, chunk])[None],
                    "state": state,
                    "sr": np.array(16000, np.int64),
                },
            )
            scores.append(float(score[0, 0]))
            context = chunk[-64:]
        vad_ms = (time.monotonic() - start) * 1000 / len(scores)
        vad_error = float(
            np.max(
                np.abs(
                    np.asarray(scores) - np.fromfile(str(destination) + ".vad", dtype=np.float32)
                )
            )
        )
        assert error < 0.0001, (name, error)
        assert abs(metrics["probability"] - native_reference) < 0.00001
        # Dynamic int8 quantization amplifies sub-1e-5 FFT differences; bound score drift
        # separately and require identical decisions at both policy thresholds.
        assert abs(metrics["probability"] - reference) < 0.02, (name, metrics, reference)
        assert all((metrics["probability"] >= t) == (reference >= t) for t in [0.5, 0.75])
        assert vad_error < 1e-5, (name, vad_error)
        assert metrics["inference_ms"] < 250, (name, metrics)
        if name == "silence":
            assert metrics["vad_max"] < 0.5
        if name == "phone":
            assert metrics["vad_max"] > 0.5
        results.append(
            dict(
                case=name,
                feature_max_error=error,
                reference_probability=reference,
                vad_max_error=vad_error,
                vad_mean_ms=vad_ms,
                **metrics,
            )
        )
    report = {
        "scope": "synthetic numerical CPU calibration, not human pause accuracy",
        "cases": results,
    }
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    validate(parser.parse_args().output)
