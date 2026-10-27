"""Offline primary-speaker VAD screening; public/synthetic audio, CPU only."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import onnxruntime as ort
import torch
from neovad import ModelConfig, VADModel

from voice_trial import cases, window_score
from voxlock_trial import SR, load, self_check, telephone

NEOVAD_SHA = "5b78dfc84400aa7926ee6e339750b9d94fe402a71421a1dd461f701374a5cd8f"
SILERO_SHA = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"
MANIFEST_SHA = "dad31c9e7753ae3b0fae450ca872b99852464f02594809ba7bb5b019ef3e7955"
BLOCK = 512


def verified(path, expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path.name
    return path


@torch.inference_mode()
def stream(model, samples, neo):
    timings, rows, native = [], [], []
    if neo:
        state = model.init_state(1, torch.device("cpu"), torch.float32)
    else:
        state = np.zeros((2, 1, 128), np.float32)
        context = np.zeros(64, np.float32)
    for offset in range(0, len(samples) - BLOCK + 1, BLOCK):
        chunk = samples[offset : offset + BLOCK]
        before = time.perf_counter()
        if neo:
            logits = model.step(torch.from_numpy(chunk[None]), state)
            p = logits.softmax(-1)[0].numpy()
            assert p.shape[1] == 3 and len(p) in (3, 4)
            rows.append([p[-1, 1], p[:, 1].mean(), p[:, 1].max(), 1 - p[-1, 0]])
            native.append(p)
        else:
            probability, state = model.run(
                ["output", "stateN"],
                {
                    "input": np.concatenate((context, chunk))[None],
                    "state": state,
                    "sr": np.array(SR, np.int64),
                },
            )
            context = chunk[-64:]
            rows.append([float(probability.item())])
        timings.append((time.perf_counter() - before) * 1000)
    rows = np.asarray(rows)
    assert np.isfinite(rows).all() and ((rows >= 0) & (rows <= 1)).all()
    names = ("primary_last", "primary_mean", "primary_max", "any_last") if neo else ("speech",)
    return (
        dict(zip(names, rows.T, strict=True)),
        {
            "block_ms": 32,
            "p50_ms": float(np.percentile(timings, 50)),
            "p95_ms": float(np.percentile(timings, 95)),
            "max_ms": max(timings),
            "blocks_over_32ms": sum(t > 32 for t in timings),
            "wall_work_ratio": sum(timings) / (len(timings) * 32),
        },
        np.concatenate(native) if native else None,
    )


def checks(neo, silero, signal):
    self_check()
    bounds = (0, 30 * BLOCK)
    assert window_score([0] * 30, bounds)["max_sustained_evidence_ms"] == 0
    assert window_score([1] * 20, (0, 20 * BLOCK))["sustained_trigger_ms_from_window_start"] == 640
    assert window_score([1] * 10 + [0] * 5 + [1] * 15, bounds)["max_sustained_evidence_ms"] == 480
    assert (
        window_score([1] * 10 + [0] * 4 + [1] * 16, bounds)[
            "sustained_trigger_ms_from_window_start"
        ]
        == 768
    )
    x = signal[: (min(len(signal), 3 * SR) // BLOCK) * BLOCK]
    for model, is_neo in ((neo, True), (silero, False)):
        first, _, native = stream(model, x, is_neo)
        stream(model, x[::-1].copy(), is_neo)
        repeated, _, _ = stream(model, x, is_neo)
        for key in first:
            np.testing.assert_array_equal(first[key], repeated[key])
        if is_neo:
            with torch.inference_mode():
                batch = model(torch.from_numpy(x[None])).softmax(-1)[0].numpy()
            np.testing.assert_allclose(native, batch, atol=1e-4, rtol=1e-4)
    return {
        "fixture_checks": "passed",
        "policy_checks": "passed",
        "state_reset": "passed",
        "neovad_stream_batch_parity": "passed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--silero", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "preserve previous results"
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    checkpoint = torch.load(
        verified(args.checkpoint, NEOVAD_SHA), map_location="cpu", weights_only=True
    )
    neo = VADModel(ModelConfig.model_validate(checkpoint["config"]))
    neo.load_state_dict(checkpoint["state_dict"], strict=True)
    neo.eval()
    assert neo.cfg.frontend.sample_rate == SR and neo.cfg.frontend.hop_length == 160
    assert next(neo.parameters()).device.type == "cpu" and neo.head.n_classes == 3
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    silero = ort.InferenceSession(
        str(verified(args.silero, SILERO_SHA)), options, providers=["CPUExecutionProvider"]
    )
    assert silero.get_providers() == ["CPUExecutionProvider"]
    fixtures = {
        x["name"]: x
        for x in json.loads(verified(args.fixtures, MANIFEST_SHA).read_text())["fixtures"]
    }
    checked = checks(neo, silero, load(fixtures["fleurs-1853-1"], args.fixtures.parent))
    result = {
        "checks": checked,
        "versions": {
            "torch": torch.__version__,
            "onnxruntime": ort.__version__,
            "numpy": np.__version__,
        },
        "neovad_config": neo.cfg.model_dump(),
        "rows": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(checked), flush=True)
    for name, condition, mix, windows in cases(fixtures, args.fixtures.parent):
        for codec in ("pcma", "pcmu"):
            raw = telephone(mix, codec)
            row = {
                "name": f"{name}-{codec}",
                "condition": condition,
                "codec": codec,
                "audio_seconds": len(raw) / SR,
                "windows": windows,
                "models": {},
            }
            for key, model, is_neo in (("silero", silero, False), ("neovad", neo, True)):
                probabilities, timing, _ = stream(model, raw, is_neo)
                row["models"][key] = {
                    "timing": timing,
                    "scores": {
                        mode: {win: window_score(values, bounds) for win, bounds in windows.items()}
                        for mode, values in probabilities.items()
                    },
                }
            result["rows"].append(row)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            print(row["name"], flush=True)


if __name__ == "__main__":
    main()
