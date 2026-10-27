"""Score an isolated filter trial with the unchanged pinned Turkish Whisper backend."""

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("compare", ROOT / "tools/asr-compare/run.py")
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--expected-cases", type=int, default=16)
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=("bypass", "voxlock", "hush100", "hush20"),
        default=["bypass", "voxlock"],
    )
    parser.add_argument(
        "--windows",
        nargs="+",
        choices=("target_repeat", "background_only"),
        default=["target_repeat", "background_only"],
    )
    args = parser.parse_args()
    data = json.loads((args.results / "results.json").read_text())
    assert args.expected_cases > 0 and len(data["rows"]) == args.expected_cases, "incomplete run"
    assert len(set(args.profiles)) == len(args.profiles), "duplicate profile"
    output = args.results / "recognition.json"
    assert not output.exists()
    backend = compare.quality.WhisperBackend()
    backend.transcribe(np.zeros(16000, "<f4").tobytes(), "pcm_f32le")
    rows = []
    for index, item in enumerate(data["rows"]):
        profiles = args.profiles if index % 2 else args.profiles[::-1]
        for profile in profiles:
            samples, sr = sf.read(args.results / f"{item['name']}-{profile}.wav", dtype="float32")
            assert sr == 16000 and samples.ndim == 1 and np.isfinite(samples).all()
            for window, (start, end) in item["windows"].items():
                if window not in args.windows:
                    continue
                assert 0 <= start < end <= len(samples)
                text = backend.transcribe(samples[start:end].astype("<f4").tobytes(), "pcm_f32le")
                reference = compare.words(item["reference"]) if window == "target_repeat" else []
                actual = compare.words(text)
                rows.append(
                    dict(
                        case=item["name"],
                        profile=profile,
                        window=window,
                        word_errors=compare.quality.distance(reference, actual),
                        reference_words=len(reference),
                        words=len(actual),
                        digital_silence=not bool(np.any(samples[start:end])),
                        text=text,
                    )
                )
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        print(json.dumps({"scored": index + 1}), flush=True)


if __name__ == "__main__":
    main()
