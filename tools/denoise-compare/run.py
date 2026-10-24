"""Paired native denoising / CUDA Whisper evaluation; public or synthetic audio only."""

import argparse
import audioop
import importlib.util
import json
from pathlib import Path
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("compare", ROOT / "tools/asr-compare/run.py")
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)
PROFILES = ["bypass", "webrtc-low", "webrtc-moderate", "rnnoise", "speex"]


def variants(samples, seed):
    low = audioop.ratecv((samples * 32767).astype("<i2").tobytes(), 2, 1, 16000, 8000, None)[0]
    low = np.frombuffer(low, "<i2").astype(np.float32) / 32768
    rms = np.sqrt(np.mean(low**2))
    # Identical 300 ms lead-in / 200 ms tail retain filter startup and delayed speech.
    low = np.pad(low, (2400, 1600))
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(len(low))
    fan = np.convolve(white, np.ones(32) / 32, mode="same")
    fan += np.sin(2 * np.pi * 100 * np.arange(len(low)) / 8000) * 0.15
    clicks = np.zeros(len(low))
    for at in range(800, len(low) - 80, 2400):
        clicks[at : at + 80] = rng.standard_normal(80) * np.exp(-np.arange(80) / 20)
    for condition, noise in [
        ("pcma", None),
        ("white10", white),
        ("fan10", fan),
        ("clicks10", clicks),
        ("quiet", None),
    ]:
        signal = low.copy()
        if noise is not None:
            signal += noise * rms / (np.sqrt(np.mean(noise**2)) * np.sqrt(10))
        if condition == "quiet":
            signal *= 0.0631
        clipped = int(np.count_nonzero(np.abs(signal) > 1))
        raw = (np.clip(signal, -1, 1) * 32767).astype("<i2").tobytes()
        raw = audioop.alaw2lin(audioop.lin2alaw(raw, 2), 2)
        raw = audioop.ratecv(raw, 2, 1, 8000, 16000, None)[0]
        yield condition, np.frombuffer(raw, "<i2").astype(np.float32) / 32768, clipped


def process(probe, profile, samples, directory):
    source, target = directory / "input.f32", directory / "output.f32"
    source.write_bytes(samples.astype("<f4").tobytes())
    result = subprocess.run(
        [str(probe), profile, str(source), str(target)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    cleaned = np.frombuffer(target.read_bytes(), "<f4")
    assert len(cleaned) == len(samples) and np.isfinite(cleaned).all()
    return cleaned, json.loads(result.stdout)


def summarize(rows):
    summary = {}
    for corpus in sorted({r["corpus"] for r in rows}):
        for condition in sorted({r["condition"] for r in rows if r["corpus"] == corpus}):
            for profile in sorted({r["profile"] for r in rows}):
                group = [
                    r
                    for r in rows
                    if (r["corpus"], r["condition"], r["profile"]) == (corpus, condition, profile)
                ]
                if not group:
                    continue
                refs = sum(r["reference_words"] for r in group)
                frames = sum(r["native"]["frames"] for r in group)
                summary[f"{corpus}/{condition}/{profile}"] = dict(
                    n=len(group),
                    wer=sum(r["word_errors"] for r in group) / refs if refs else None,
                    entity_misses=sum(r["entity_misses"] for r in group),
                    empty_outputs=sum(not r["text"] for r in group),
                    asr_p50_ms=float(np.median([r["asr_ms"] for r in group])),
                    native_mean_us=sum(
                        r["native"]["mean_us"] * r["native"]["frames"] for r in group
                    )
                    / frames,
                    native_max_us=max(r["native"]["max_us"] for r in group),
                    native_cpu_ms=sum(r["native"]["cpu_ms"] for r in group),
                    audio_seconds=sum(r["audio_seconds"] for r in group),
                )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--profiles", nargs="+", choices=PROFILES + ["dtln", "dtln-half"], default=PROFILES
    )
    parser.add_argument("--dtln-models", type=Path)
    args = parser.parse_args()
    if len(set(args.profiles)) != len(args.profiles):
        parser.error("profiles must be unique")
    dtln = None
    if any(p.startswith("dtln") for p in args.profiles):
        if args.dtln_models is None:
            parser.error("--dtln-models is required for dtln")
        from dtln import DTLN

        dtln = DTLN(args.dtln_models)
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    data = json.loads(args.fixtures.read_text())["fixtures"]
    assert data and all(item["corpus"] in {"fleurs", "synthetic-ema"} for item in data)
    backend = compare.quality.WhisperBackend()
    backend.transcribe(np.zeros(16000, "<f4").tobytes(), "pcm_f32le")
    backend.transcribe(
        compare.samples_for(data[0], args.fixtures.parent).astype("<f4").tobytes(), "pcm_f32le"
    )
    rows = []
    for index, item in enumerate(data + [{"name": "nonspeech", "text": "", "corpus": "control"}]):
        if item["corpus"] == "control":
            rng = np.random.default_rng(20261024)
            cases = [
                ("silence", np.zeros(48000, np.float32), 0),
                ("noise", rng.standard_normal(48000).astype(np.float32) * 0.01, 0),
                (
                    "hum",
                    (np.sin(2 * np.pi * 100 * np.arange(48000) / 16000) * 0.03).astype(np.float32),
                    0,
                ),
            ]
        else:
            cases = variants(compare.samples_for(item, args.fixtures.parent), index + 20261024)
        for condition, samples, clipped in cases:
            # Rotate execution order to reduce fixed-order timing bias.
            shift = index % len(args.profiles)
            for profile in args.profiles[shift:] + args.profiles[:shift]:
                if profile.startswith("dtln"):
                    cleaned, native = dtln.process(samples, 0.5 if profile == "dtln-half" else 1)
                else:
                    cleaned, native = process(args.probe.resolve(), profile, samples, args.output)
                start = time.perf_counter()
                text = backend.transcribe(cleaned.tobytes(), "pcm_f32le")
                elapsed = (time.perf_counter() - start) * 1000
                reference, actual = compare.words(item["text"]), compare.words(text)
                rows.append(
                    dict(
                        fixture=item["name"],
                        corpus=item["corpus"],
                        condition=condition,
                        profile=profile,
                        word_errors=compare.quality.distance(reference, actual),
                        reference_words=len(reference),
                        text=text,
                        asr_ms=elapsed,
                        native=native,
                        audio_seconds=len(samples) / 16000,
                        input_clipped_samples=clipped,
                        entity_misses=sum(
                            "".join(compare.words(e)) not in "".join(actual)
                            for e in item.get("entities", [])
                        ),
                    )
                )
        (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        print(json.dumps({"completed": index + 1, "total": len(data) + 1}), flush=True)
    (args.output / "summary.json").write_text(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
