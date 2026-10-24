"""Run one pinned ASR profile on identical public/synthetic audio; no live calls."""

import argparse
import audioop
import hashlib
import importlib.util
import json
import re
import unicodedata
from pathlib import Path
import sys
import time
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/asr"))
spec = importlib.util.spec_from_file_location("quality", ROOT / "tools/benchmark-asr-quality.py")
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def words(text):
    return re.findall(
        r"\w+", unicodedata.normalize("NFKC", text).translate(str.maketrans("Iİ", "ıi")).lower()
    )


def samples_for(item, directory):
    path = directory / item["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    with wave.open(str(path)) as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        raw = audioop.ratecv(
            wav.readframes(wav.getnframes()), 2, 1, wav.getframerate(), 16000, None
        )[0]
    return np.frombuffer(raw, "<i2").astype(np.float32) / 32768


def variants(samples, seed):
    yield "clean16", samples
    raw = (samples * 32767).astype("<i2").tobytes()
    low = audioop.ratecv(raw, 2, 1, 16000, 8000, None)[0]
    low = audioop.alaw2lin(audioop.lin2alaw(low, 2), 2)
    telephone = (
        np.frombuffer(audioop.ratecv(low, 2, 1, 8000, 16000, None)[0], "<i2").astype(np.float32)
        / 32768
    )
    yield "pcma", telephone
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(telephone)).astype(np.float32)
    rms = np.sqrt(np.mean(telephone**2))
    yield "pcma-noise10", np.clip(telephone + noise * rms / np.sqrt(10), -1, 1)
    yield "pcma-quiet", telephone * 0.0631


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--profile", choices=["whisper", "nemotron"], required=True)
    parser.add_argument("--lookahead", type=int, choices=[0, 3, 6, 13], default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    if args.profile == "whisper":
        backend = quality.WhisperBackend()

        def decode(samples):
            return backend.transcribe(samples.astype("<f4").tobytes(), "pcm_f32le")
    else:
        from alojan_asr.nemotron import NemotronBackend

        backend = NemotronBackend(lookahead=args.lookahead)

        def decode(samples):
            return backend.transcribe(samples.astype("<f4").tobytes(), "pcm_f32le")

    data = json.loads(args.fixtures.read_text())["fixtures"]
    decode(samples_for(data[0], args.fixtures.parent))
    rows = []
    for index, item in enumerate(data):
        for condition, samples in variants(samples_for(item, args.fixtures.parent), index):
            start = time.perf_counter()
            text = decode(samples)
            elapsed = (time.perf_counter() - start) * 1000
            reference, actual = words(item["text"]), words(text)
            rows.append(
                dict(
                    fixture=item["name"],
                    corpus=item["corpus"],
                    condition=condition,
                    gender=item["gender"],
                    word_errors=quality.distance(reference, actual),
                    reference_words=len(reference),
                    wall_ms=elapsed,
                    text=text,
                    entity_misses=sum(
                        "".join(words(e)) not in "".join(actual) for e in item.get("entities", [])
                    ),
                )
            )
        print(json.dumps({"completed": index + 1, "total": len(data)}), flush=True)
        (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    summary = {}
    for corpus in sorted({r["corpus"] for r in rows}):
        for condition in sorted({r["condition"] for r in rows}):
            subset = [r for r in rows if r["corpus"] == corpus and r["condition"] == condition]
            summary[corpus + "/" + condition] = {
                "n": len(subset),
                "wer": sum(r["word_errors"] for r in subset)
                / sum(r["reference_words"] for r in subset),
                "entity_misses": sum(r["entity_misses"] for r in subset),
                "p50_ms": float(np.median([r["wall_ms"] for r in subset])),
                "p95_ms": float(np.percentile([r["wall_ms"] for r in subset], 95)),
            }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
