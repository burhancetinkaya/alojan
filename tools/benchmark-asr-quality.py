"""Paired CUDA decoder comparison on synthetic G.711 speech; never handset acceptance."""

import argparse
import audioop
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import time
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/asr"))
from alojan_asr.model import WhisperBackend  # noqa: E402


def words(text):
    return re.findall(r"\w+", text.casefold().replace("i\u0307", "i"))


def distance(reference, actual):
    row = list(range(len(actual) + 1))
    for index, word in enumerate(reference, 1):
        following = [index]
        for column, other in enumerate(actual, 1):
            following.append(
                min(row[column] + 1, following[-1] + 1, row[column - 1] + (word != other))
            )
        row = following
    return row[-1]


def load_fixtures(path):
    # Only synthetic/explicitly consented evaluation data may be supplied; keep it private.
    manifest = json.loads(path.read_text())
    assert manifest["provenance"] == "synthetic-ema", "synthetic fixture manifest required"
    result = []
    for item in manifest["fixtures"]:
        audio_path = path.parent / item["file"]
        assert hashlib.sha256(audio_path.read_bytes()).hexdigest() == item["sha256"]
        with wave.open(str(audio_path), "rb") as wav:
            assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
            assert 0 < wav.getnframes() <= 30 * wav.getframerate()
            audio = audioop.ratecv(
                wav.readframes(wav.getnframes()), 2, 1, wav.getframerate(), 8000, None
            )[0]
        result.append((item, np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768))
    assert result
    return result


def cases(fixtures, seed):
    rng = np.random.default_rng(seed)
    for item, audio in fixtures:
        rms = np.sqrt(np.mean(audio * audio))
        noise = rng.standard_normal(len(audio)).astype(np.float32)
        for condition in ("clean", "white15", "white5", "hum", "quiet"):
            samples = audio.copy()
            if condition.startswith("white"):
                samples += noise * rms / (10 ** (int(condition[5:]) / 20))
            elif condition == "hum":
                samples += (np.sin(2 * np.pi * 50 * np.arange(len(audio)) / 8000) * rms * 2).astype(
                    np.float32
                )
            elif condition == "quiet":
                samples *= 0.0631
            raw = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
            raw = audioop.alaw2lin(audioop.lin2alaw(raw, 2), 2)
            raw = audioop.ratecv(raw, 2, 1, 8000, 16000, None)[0]
            yield item, condition, raw
    for condition, samples in (
        ("silence", np.zeros(48000, dtype=np.float32)),
        ("noise", rng.standard_normal(48000).astype(np.float32) * 0.01),
        ("hum", np.sin(2 * np.pi * 50 * np.arange(48000) / 16000).astype(np.float32) * 0.03),
    ):
        yield (
            {"name": "nonspeech", "text": ""},
            condition,
            (samples * 32767).astype("<i2").tobytes(),
        )


def baseline(model, raw):
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
    if not np.any(samples):
        return ""
    segments, _ = model.transcribe(
        samples,
        language="tr",
        task="transcribe",
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=False,
        word_timestamps=False,
        max_new_tokens=440,
    )
    return "".join(segment.text for segment in segments).strip()


def summarize(rows):
    speech = [row for row in rows if row["reference_words"]]
    return {
        "speech_decodes": len(speech),
        "word_errors": sum(row["word_errors"] for row in speech),
        "reference_words": sum(row["reference_words"] for row in speech),
        "missing_speech": sum(not row["text"] for row in speech),
        "entity_misses": sum(row["entity_misses"] for row in speech),
        "hint_insertions": sum(row["hint_insertions"] for row in rows),
        "nonspeech_outputs": sum(bool(row["text"]) for row in rows if not row["reference_words"]),
        "p50_ms": float(np.median([row["wall_ms"] for row in speech])),
        "p95_ms": float(np.percentile([row["wall_ms"] for row in speech], 95)),
        "cpu_ms": sum(row["cpu_ms"] for row in rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--vocabulary-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261023)
    args = parser.parse_args()
    assert 1 <= args.repeats <= 10
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    vocabulary = args.vocabulary_file.read_text().strip()
    hints = list({"".join(words(term)) for term in json.loads(vocabulary).values()})
    data = list(cases(load_fixtures(args.fixtures), args.seed))
    backend = WhisperBackend(replacements=vocabulary)
    baseline(backend.model, data[0][2])
    backend.transcribe(data[0][2], "pcm_s16le")
    results = []
    for repeat in range(args.repeats):
        for index, (item, condition, raw) in enumerate(data):
            order = ["baseline", "candidate"]
            random.Random(args.seed + repeat * len(data) + index).shuffle(order)
            for profile in order:
                wall, cpu = time.perf_counter(), time.process_time()
                text = (
                    baseline(backend.model, raw)
                    if profile == "baseline"
                    else backend.transcribe(raw, "pcm_s16le")
                )
                wall_ms = (time.perf_counter() - wall) * 1000
                cpu_ms = (time.process_time() - cpu) * 1000
                reference = item["text"]
                actual_words, reference_words = words(text), words(reference)
                actual_key, reference_key = "".join(actual_words), "".join(reference_words)
                results.append(
                    {
                        "fixture": item["name"],
                        "condition": condition,
                        "repeat": repeat,
                        "profile": profile,
                        "wall_ms": wall_ms,
                        "cpu_ms": cpu_ms,
                        "word_errors": distance(reference_words, actual_words),
                        "reference_words": len(reference_words),
                        "entity_misses": sum(
                            "".join(words(entity)) not in actual_key
                            for entity in item.get("entities", [])
                        ),
                        "hint_insertions": sum(
                            term not in reference_key and term in actual_key for term in hints
                        ),
                        "text": text,
                    }
                )
        print(json.dumps({"repeat_completed": repeat + 1}), flush=True)
    summaries = {
        profile: summarize([row for row in results if row["profile"] == profile])
        for profile in ("baseline", "candidate")
    }
    (args.output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    (args.output / "summary.json").write_text(json.dumps(summaries, indent=2))
    print(json.dumps(summaries), flush=True)


if __name__ == "__main__":
    main()
