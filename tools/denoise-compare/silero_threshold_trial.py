"""Offline interruption-threshold sweep; no listening or serving settings changed."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import onnxruntime as ort

from hush_trial import SILERO_SHA, vad, verified
from voice_trial import cases, window_score
from voxlock_trial import SR, self_check, telephone

THRESHOLDS = (0.5, 0.6, 0.7)


def checks():
    self_check()
    key = "sustained_trigger_ms_from_window_start"
    for threshold in THRESHOLDS:
        boundary = np.float32(threshold)
        below = np.nextafter(boundary, np.float32(0))
        assert window_score([boundary] * 20, (0, 10240), threshold=threshold)[key] == 640
        assert window_score([below] * 20, (0, 10240), threshold=threshold)[key] is None
        for quiet, expected in ((4, 768), (5, None)):
            values = [1] * 10 + [0] * quiet + [1] * 10
            assert (
                window_score(values, (0, len(values) * 512), threshold=threshold)[key] == expected
            )
    for bad in (float("nan"), float("inf"), 0, 1, -1):
        try:
            window_score([1] * 20, (0, 10240), threshold=bad)
        except ValueError:
            continue
        raise AssertionError("invalid threshold accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--silero", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks()
    verified(args.silero, SILERO_SHA)
    baseline = json.loads(args.baseline.read_text())
    manifest_sha = hashlib.sha256(args.fixtures.read_bytes()).hexdigest()
    assert baseline["manifest_sha256"] == manifest_sha
    prior = {row["name"]: row for row in baseline["rows"]}
    fixtures = {x["name"]: x for x in json.loads(args.fixtures.read_text())["fixtures"]}
    args.output.mkdir(parents=True, exist_ok=False)
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    model = ort.InferenceSession(str(args.silero), options, providers=["CPUExecutionProvider"])
    assert model.get_providers() == ["CPUExecutionProvider"]
    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "onnxruntime": ort.__version__,
        "manifest_sha256": manifest_sha,
        "silero_sha256": SILERO_SHA,
        "baseline_sha256": hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        "thresholds": THRESHOLDS,
        "sustained_voice_ms": 640,
        "sustained_quiet_ms": 160,
        "checks": "policy, float32 boundaries and invalid thresholds passed",
        "rows": [],
    }
    saved = {}
    for name, condition, mix, windows in cases(fixtures, args.fixtures.parent):
        for codec in ("pcma", "pcmu"):
            full_name = f"{name}-{codec}"
            raw = telephone(mix, codec)
            started = time.perf_counter()
            probabilities = vad(model, raw)
            elapsed = time.perf_counter() - started
            saved[full_name] = np.asarray(probabilities, dtype=np.float32)
            scores = {
                str(threshold): {
                    win: window_score(probabilities, bounds, threshold=threshold)
                    for win, bounds in windows.items()
                }
                for threshold in THRESHOLDS
            }
            old = prior[full_name]
            assert windows == old["windows"] and len(raw) / SR == old["audio_seconds"]
            for win, score in scores["0.5"].items():
                for field, value in score.items():
                    assert value == old["profiles"]["bypass"]["scores"][win][field], (
                        full_name,
                        win,
                        field,
                    )
            result["rows"].append(
                {
                    "name": full_name,
                    "condition": condition,
                    "codec": codec,
                    "audio_seconds": len(raw) / SR,
                    "inference_seconds": elapsed,
                    "windows": windows,
                    "scores": scores,
                }
            )
    assert len(result["rows"]) == len(prior) == 34
    result["baseline_reproduction"] = "all 0.5 window fields match previous bypass exactly"
    np.savez_compressed(args.output / "probabilities.npz", **saved)
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"streams": len(result["rows"]), "baseline": result["baseline_reproduction"]}))


if __name__ == "__main__":
    main()
