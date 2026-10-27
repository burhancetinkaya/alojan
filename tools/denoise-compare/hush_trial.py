"""Evaluate Hush BEFORE the unchanged Silero detector, never on live audio."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import onnxruntime as ort
import soundfile as sf

from voice_trial import cases, window_score
from voxlock_trial import SR, load, self_check, telephone

MODEL_SHA = "45632ccaa82b71bb743d6caa7c78e983fe2f2790a3af7f6ec48e6ed7ba085df6"
LIB_SHA = {
    "Linux": "c4a5915c92e9500a49e6cd14804e6e88319277de2ef7d4d5cf6c0ac4456f3bbf",
    "Darwin": "4bcd38634000d456ad68db4b6ff97fe4a462542aa65ac5f910fbf374ca33fbaa",
}
SILERO_SHA = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"


def verified(path, expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path.name
    return path


def process(session, samples):
    """Keep native error sentinel visible; upstream process_frame discards it."""
    assert session.frame_length == 160 and session.sample_rate == SR
    assert samples.dtype == np.float32 and np.isfinite(samples).all()
    padded = np.pad(samples, (0, (-len(samples)) % 160 + 5 * 160))
    output = np.zeros_like(padded)
    ms = []
    pointer = ctypes.POINTER(ctypes.c_float)
    for offset in range(0, len(padded), 160):
        before = time.perf_counter()
        # One owning thread per session; pinned wrapper declares these C signatures.
        snr = session._lib.weya_nc_process_frame(
            session._session,
            padded[offset : offset + 160].ctypes.data_as(pointer),
            output[offset : offset + 160].ctypes.data_as(pointer),
        )
        ms.append((time.perf_counter() - before) * 1000)
        assert np.isfinite(snr) and snr != -100, "native processing failed"
    assert np.isfinite(output).all()
    return output, {
        "p50_ms": float(np.percentile(ms, 50)),
        "p95_ms": float(np.percentile(ms, 95)),
        "max_ms": max(ms),
        "frames_over_10ms": sum(t > 10 for t in ms),
        "wall_work_ratio": sum(ms) / (len(ms) * 10),
        "out_of_range_samples": int(np.count_nonzero(np.abs(output) > 1)),
    }


def filtered(model, samples, attenuation):
    before = time.perf_counter()
    with model.create_session(sample_rate=SR, atten_lim_db=attenuation) as session:
        init_ms = (time.perf_counter() - before) * 1000
        y, timing = process(session, samples)
    return y, timing | {"session_init_ms": init_ms}


def vad(model, samples):
    context = np.zeros(64, np.float32)
    state = np.zeros((2, 1, 128), np.float32)
    values = []
    for offset in range(0, len(samples) - 511, 512):
        chunk = samples[offset : offset + 512]
        p, state = model.run(
            ["output", "stateN"],
            {
                "input": np.concatenate((context, chunk))[None],
                "state": state,
                "sr": np.array(SR, np.int64),
            },
        )
        values.append(float(p.item()))
        context = chunk[-64:]
    assert np.isfinite(values).all()
    return values


def checks(model, signal):
    self_check()
    assert window_score([1] * 20, (0, 20 * 512))["sustained_trigger_ms_from_window_start"] == 640
    assert (
        window_score([1] * 10 + [0] * 5 + [1] * 15, (0, 30 * 512))["max_sustained_evidence_ms"]
        == 480
    )
    x = signal[: 3 * SR]
    # Exactly 0 dB bypasses synthesis upstream. Near-zero attenuation keeps the
    # DSP path active; continuous calibration noise avoids its silent-frame shortcut.
    calibration = np.random.default_rng(7).normal(0, 0.05, 3 * SR).astype(np.float32)
    y, _ = filtered(model, calibration, 0.001)
    start, end = SR // 2, 2 * SR
    errors = [
        float(np.mean((y[start + d : end + d] - calibration[start:end]) ** 2)) for d in range(801)
    ]
    delay = int(np.argmin(errors))
    assert 0 < delay < 800 and errors[delay] < 1e-8, "DSP alignment/passthrough failed"
    signals = (x, x[::-1].copy())
    expected = [filtered(model, s, 100)[0] for s in signals]
    with ThreadPoolExecutor(max_workers=2) as pool:
        actual = list(pool.map(lambda s: filtered(model, s, 100)[0], signals))
    for a, b in zip(expected, actual, strict=True):
        np.testing.assert_allclose(a, b, atol=1e-6, rtol=1e-6)
    with model.create_session(sample_rate=SR) as session:
        first, _ = process(session, x)
        process(session, signals[1])
        session.reset()
        again, _ = process(session, x)
        np.testing.assert_array_equal(first, again)
    return {
        "fixture_policy_checks": "passed",
        "two_session_parallel_equivalence": "passed",
        "reset_equivalence": "passed",
        "dsp_delay_samples": delay,
        "near_zero_attenuation_rmse": float(np.sqrt(errors[delay])),
    }


def main():
    from weya_nc import WeyaModel

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--silero", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    verified(args.library, LIB_SHA[platform.system()])
    verified(args.model, MODEL_SHA)
    verified(args.silero, SILERO_SHA)
    fixtures = {x["name"]: x for x in json.loads(args.fixtures.read_text())["fixtures"]}
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    silero = ort.InferenceSession(str(args.silero), options, providers=["CPUExecutionProvider"])
    assert silero.get_providers() == ["CPUExecutionProvider"]
    before = time.perf_counter()
    with WeyaModel(lib_path=args.library, model_path=args.model) as model:
        init_ms = (time.perf_counter() - before) * 1000
        checked = checks(model, load(fixtures["fleurs-1853-1"], args.fixtures.parent))
        delay = checked["dsp_delay_samples"]
        result = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "versions": {
                "numpy": np.__version__,
                "soundfile": sf.__version__,
                "onnxruntime": ort.__version__,
            },
            "checks": checked,
            "model_init_ms": init_ms,
            "manifest_sha256": hashlib.sha256(args.fixtures.read_bytes()).hexdigest(),
            "rows": [],
        }
        print(json.dumps(checked), flush=True)
        for name, condition, mix, windows in cases(fixtures, args.fixtures.parent):
            for codec in ("pcma", "pcmu"):
                raw = telephone(mix, codec)
                target = "fleurs-1853-1" if name.startswith("0-") else "greeting"
                if "interrupt" in name:
                    target = "interrupt"
                row = {
                    "name": f"{name}-{codec}",
                    "condition": condition,
                    "codec": codec,
                    "audio_seconds": len(raw) / SR,
                    "reference": "" if condition == "silence" else fixtures[target]["text"],
                    "windows": windows,
                    "profiles": {},
                }
                for profile, attenuation in (("bypass", None), ("hush100", 100), ("hush20", 20)):
                    if attenuation is None:
                        aligned, timing = raw, None
                    else:
                        out, timing = filtered(model, raw, attenuation)
                        aligned = out[delay : delay + len(raw)]
                        # Match the PCM16 boundary before VAD/ASR without hiding clipping counts.
                        aligned = (np.clip(aligned, -1, 32767 / 32768) * 32768).astype(
                            np.int16
                        ).astype(np.float32) / 32768
                    probabilities = vad(silero, aligned)
                    sf.write(
                        args.output / f"{name}-{codec}-{profile}.wav", aligned, SR, subtype="FLOAT"
                    )
                    scores = {}
                    for win, bounds in windows.items():
                        a, b = bounds
                        scores[win] = window_score(probabilities, bounds) | {
                            "output_input_db": float(
                                10
                                * np.log10(
                                    (np.mean(aligned[a:b] ** 2) + 1e-12)
                                    / (np.mean(raw[a:b] ** 2) + 1e-12)
                                )
                            ),
                        }
                    row["profiles"][profile] = {"timing": timing, "scores": scores}
                result["rows"].append(row)
                (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
                print(row["name"], flush=True)


if __name__ == "__main__":
    main()
