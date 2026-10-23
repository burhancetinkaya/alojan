"""Generate the two synthetic M1 prompts with pinned EMA weights on CUDA."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time
from unittest.mock import patch
import warnings
import wave

ROOT = Path(__file__).resolve().parents[2]
MODEL = "canberkkkkkk/ema-lightning"
REVISION = "e7c96f2fc0ba843cd0f86e02786655bb56f50df8"
WEIGHTS = {
    "ema.pt": "95aec03dafbe0e1d69bca774ab597c779464729a14bc99bfcb52480090c7dfe6",
    "decoder.pt": "9595819b173f411340f63d11332695121a97f8bf1f6d8b6fef0b21cf99c7ad67",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets/prompts/tr-v3-ema")
    parser.add_argument("--text-dir", type=Path, default=ROOT / "assets/prompts/tr-v3-ema")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory already exists; choose a fresh directory")
    texts = {}
    for name in ["greeting", "unavailable"]:
        texts[name] = (args.text_dir / f"{name}.txt").read_text()
        if not texts[name].strip():
            parser.error(f"empty prompt text: {name}")
    for key, value in {
        "HF_HOME": str(ROOT / ".local/ema/huggingface"),
        "XDG_CACHE_HOME": str(ROOT / ".local/ema/cache"),
        "TORCHINDUCTOR_CACHE_DIR": str(ROOT / ".local/ema/inductor"),
        "TRITON_CACHE_DIR": str(ROOT / ".local/ema/triton"),
        "TORCHINDUCTOR_COMPILE_THREADS": "4",
        "OMP_NUM_THREADS": "4",
        "HF_HUB_DISABLE_TELEMETRY": "1",
    }.items():
        os.environ[key] = value

    import numpy as np
    import torch
    from ema_lightning import EMA
    from huggingface_hub import hf_hub_download

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; no CPU fallback for this evidence")
    torch.set_num_threads(4)
    paths = {}
    for name in ["config.json", *WEIGHTS]:
        paths[name] = Path(hf_hub_download(MODEL, name, revision=REVISION))
        if name in WEIGHTS and sha256(paths[name]) != WEIGHTS[name]:
            raise RuntimeError(f"model checksum mismatch: {name}")

    def pinned_download(repo, filename):
        if repo != MODEL or filename not in paths:
            raise ValueError("unexpected model file")
        return str(paths[filename])

    # shortcut: EMA 1.1.2 has no revision argument; remove this scoped shim when it does.
    with patch("ema_lightning.api.hf_hub_download", pinned_download):
        tts = EMA(device="cuda")
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tts.lightning(batch_size=1)
    torch.cuda.synchronize()
    if tts._engine.graphs is None:
        raise RuntimeError("EMA rejected lightning graphs; inspect numerical validation")
    manifest = {
        "profile": "tr-v3-ema-cuda",
        "model": MODEL,
        "model_revision": REVISION,
        "weight_sha256": WEIGHTS,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["ema-lightning", "torch", "numpy", "normalizer-tr", "huggingface-hub"]
        },
        "device": torch.cuda.get_device_name(0),
        "cuda_runtime": torch.version.cuda,
        "seed": 0,
        "speed": 1.0,
        "batch_size": 1,
        "warmup_seconds": round(time.perf_counter() - started, 3),
        "warmup_warnings": [str(item.message) for item in caught],
        "listening_status": "pending_owner_review",
        "files": [],
        "previews": [],
    }
    args.output_dir.mkdir(parents=True)
    for name in ["greeting", "unavailable"]:
        text_path = args.output_dir / f"{name}.txt"
        text_path.write_text(texts[name])
        for rate in [48000, 8000]:
            started = time.perf_counter()
            chunks, first_ms = [], None
            for chunk in tts.stream(text_path.read_text().strip(), seed=0, sample_rate=rate):
                if first_ms is None:
                    first_ms = (time.perf_counter() - started) * 1000
                if chunk.ndim != 1 or not np.isfinite(chunk).all():
                    raise RuntimeError("invalid EMA audio chunk")
                chunks.append(chunk)
            audio = np.concatenate(chunks)
            elapsed = time.perf_counter() - started
            peak = float(np.max(np.abs(audio)))
            rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
            if not rate <= len(audio) <= rate * 30 or not 0.001 < rms or peak > 1.0:
                raise RuntimeError("unexpected speech duration, silence or clipping")
            frame = rate // 50
            audio = np.pad(audio, (0, (-len(audio)) % frame))
            filename = f"{name}.wav" if rate == 8000 else f"{name}-48000.wav"
            path = args.output_dir / filename
            with wave.open(str(path), "wb") as wav:
                wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                wav.writeframes((audio * 32767).round().astype("<i2").tobytes())
            entry = {
                "file": filename,
                "text_file": text_path.name,
                "sha256": sha256(path),
                "text_sha256": sha256(text_path),
                "sample_rate_hz": rate,
                "samples": len(audio),
                "duration_ms": len(audio) * 1000 // rate,
                "chunks": len(chunks),
                "first_chunk_ms": round(first_ms, 3),
                "generation_ms": round(elapsed * 1000, 3),
                "peak": peak,
                "rms": rms,
            }
            manifest["files" if rate == 8000 else "previews"].append(entry)
            print(json.dumps(entry), flush=True)
    manifest["peak_allocated_mib"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    manifest["peak_reserved_mib"] = round(torch.cuda.max_memory_reserved() / 2**20, 1)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("EMA prompt generation complete", flush=True)


if __name__ == "__main__":
    main()
