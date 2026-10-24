"""Prepare a bounded public FLEURS sample and existing synthetic audio, locally only."""

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows = pq.read_table(args.parquet).to_pylist()
    fixtures = []
    # Spread selection across the test split; speaker identities are not available.
    counts = {}
    for index in np.linspace(0, len(rows) - 1, 24, dtype=int):
        row = rows[index]
        gender = str(row["gender"])
        samples, rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
        if samples.ndim != 1 or not 2 <= len(samples) / rate <= 20:
            continue
        name = f"fleurs-{row['id']}-{len(fixtures)}"
        path = args.output / f"{name}.wav"
        sf.write(path, samples, rate, subtype="PCM_16")
        fixtures.append(
            dict(
                name=name,
                file=path.name,
                text=row["transcription"],
                corpus="fleurs",
                gender=gender,
                entities=[],
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
        counts[gender] = counts.get(gender, 0) + 1
    synthetic = json.loads(args.synthetic.read_text())
    assert synthetic["provenance"] == "synthetic-ema"
    for item in synthetic["fixtures"]:
        source = args.synthetic.parent / item["file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item["sha256"]
        path = args.output / f"ema-{len(fixtures)}.wav"
        path.write_bytes(source.read_bytes())
        fixtures.append(
            {**item, "file": path.name, "corpus": "synthetic-ema", "gender": "synthetic"}
        )
    (args.output / "manifest.json").write_text(
        json.dumps({"fixtures": fixtures}, ensure_ascii=False)
    )
    print(json.dumps({"public_samples": counts, "total": len(fixtures)}))


if __name__ == "__main__":
    main()
