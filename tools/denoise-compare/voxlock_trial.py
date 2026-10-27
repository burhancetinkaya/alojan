"""Bounded CPU VoxLock trial using existing public/synthetic fixtures, never call audio."""

import argparse
import audioop
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import soundfile as sf
import soxr

SR = 16000
MODEL_HASHES = {
    "chunk_int8.onnx": "f0d2b0aaf95affe8894ea008d0105be4f5f5354f7244835534c31b1a7dd4699a",
    "enroll.onnx": "86645cba23f207def0b31a6e74a615d3b7a813b4fdf957c53b3af2905ba2ffd3",
}


def telephone(x, codec):
    """Round-trip one continuous file through G.711 at 8 kHz."""
    assert codec in {"pcma", "pcmu"} and np.isfinite(x).all()
    assert np.max(np.abs(x)) < 1
    raw = (x * 32767).astype("<i2").tobytes()
    raw = audioop.ratecv(raw, 2, 1, SR, 8000, None)[0]
    encode, decode = (
        (audioop.lin2alaw, audioop.alaw2lin)
        if codec == "pcma"
        else (audioop.lin2ulaw, audioop.ulaw2lin)
    )
    raw = audioop.ratecv(decode(encode(raw, 2), 2), 2, 1, 8000, SR, None)[0]
    out = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    return np.pad(out, (0, len(x) - len(out)))


def load(item, directory):
    path = directory / item["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    assert item["corpus"] in {"fleurs", "synthetic-ema"}
    x, sr = sf.read(path, dtype="float32")
    assert x.ndim == 1 and np.isfinite(x).all()
    x = soxr.resample(x, sr, SR) if sr != SR else x
    # Controlled level comparison, not a simulation of microphone distance.
    return (x * (0.35 / np.max(np.abs(x)))).astype(np.float32)


def make_case(target, background, condition):
    assert condition in {"clean", "background-quiet", "background-equal", "background-first"}
    first = (5 if condition == "background-first" else 1) * SR
    second = first + len(target) + 7 * SR
    n = second + len(target) + SR
    wanted = np.zeros(n, np.float32)
    wanted[first : first + len(target)] = target
    wanted[second : second + len(target)] = target
    other = np.zeros(n, np.float32)
    if condition != "clean":
        start = 0 if condition == "background-first" else first + len(target)
        gain = 0.25 if condition == "background-quiet" else 1.0
        other[start : n - SR] = np.resize(background, n - SR - start) * gain
    return wanted + other, {
        "background_only": [first + len(target) + SR, second - SR],
        "target_repeat": [second, second + len(target)],
    }


def run_stream(model, samples):
    stream = model.live()
    out, ms, lock_at, deficits = [], [], None, []
    produced = 0
    for start in range(0, len(samples), 1280):  # 80 ms, two CPU threads
        chunk = samples[start : start + 1280]
        before = time.perf_counter()
        y = stream.push(chunk)
        ms.append((time.perf_counter() - before) * 1000)
        out.append(y)
        produced += len(y)
        deficits.append(start + len(chunk) - produced)
        if stream.locked and lock_at is None:
            lock_at = (start + len(chunk)) / SR
    before = time.perf_counter()
    out.append(stream.flush())
    flush_ms = (time.perf_counter() - before) * 1000
    y = np.concatenate(out)
    assert len(y) >= len(samples) and np.isfinite(y).all()
    return y[: len(samples)], {
        "lock_seconds": lock_at,
        "push_ms_p50": float(np.percentile(ms, 50)),
        "push_ms_p95": float(np.percentile(ms, 95)),
        "push_ms_max": max(ms),
        "wall_work_ratio": (sum(ms) + flush_ms) / (len(samples) / SR * 1000),
        "pushes_over_80ms": sum(t > 80 for t in ms),
        "max_output_deficit_ms": max(deficits) / SR * 1000,
        "flush_ms": flush_ms,
        "extra_tail_samples": len(y) - len(samples),
        "output_out_of_range_samples": int(np.count_nonzero(np.abs(y) > 1)),
    }


def self_check():
    x = np.sin(np.arange(SR, dtype=np.float32) * 0.03) * 0.1
    for codec in ("pcma", "pcmu"):
        y = telephone(x, codec)
        assert len(y) == len(x) and np.isfinite(y).all()
        assert np.sqrt(np.mean((x - y) ** 2)) < 0.01
    for condition in ("clean", "background-quiet", "background-equal", "background-first"):
        mix, windows = make_case(x, x * 0.5, condition)
        assert (
            np.array_equal(mix[windows["target_repeat"][0] : windows["target_repeat"][1]], x)
            if condition == "clean"
            else True
        )
        a, b = windows["background_only"]
        assert b > a and (np.any(mix[a:b]) == (condition != "clean"))


def main():
    from voxlock import VoxLock

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    self_check()
    for name, expected in MODEL_HASHES.items():
        assert hashlib.sha256((args.models / name).read_bytes()).hexdigest() == expected
    args.output.mkdir(parents=True, exist_ok=False)
    fixtures = {x["name"]: x for x in json.loads(args.fixtures.read_text())["fixtures"]}
    items = [fixtures["fleurs-1853-1"], fixtures["greeting"]]
    signals = [load(item, args.fixtures.parent) for item in items]
    before = time.perf_counter()
    model = VoxLock(model_dir=args.models, precision="int8", threads=2)
    init_ms = (time.perf_counter() - before) * 1000
    assert model.chunk.get_providers() == ["CPUExecutionProvider"]
    rows = []
    for role in range(2):
        for condition in ("clean", "background-quiet", "background-equal", "background-first"):
            for codec in ("pcma", "pcmu"):
                name = f"{role}-{condition}-{codec}"
                mix, windows = make_case(signals[role], signals[1 - role], condition)
                raw = telephone(mix, codec)
                y, timing = run_stream(model, raw)
                for profile, signal in (("bypass", raw), ("voxlock", y)):
                    sf.write(args.output / f"{name}-{profile}.wav", signal, SR, subtype="FLOAT")
                a, b = windows["background_only"]
                ratio_db = 10 * np.log10(
                    (np.mean(y[a:b] ** 2) + 1e-12) / (np.mean(raw[a:b] ** 2) + 1e-12)
                )
                row = dict(
                    name=name,
                    target=items[role]["name"],
                    reference=items[role]["text"],
                    condition=condition,
                    codec=codec,
                    windows=windows,
                    audio_seconds=len(raw) / SR,
                    background_output_input_db=float(ratio_db),
                    timing=timing,
                )
                rows.append(row)
                (args.output / "results.json").write_text(
                    json.dumps(dict(init_ms=init_ms, rows=rows), indent=2)
                )
                print(
                    json.dumps({"case": name, "timing": timing, "background_db": float(ratio_db)}),
                    flush=True,
                )


if __name__ == "__main__":
    main()
