"""Calibrate the pinned EMA adapter on synthetic text; stop the TTS server first."""

import argparse
import json
from pathlib import Path
import time

from alojan_tts.model import EmaBackend
import numpy as np
import torch
from ema_lightning.audio import Resampler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a fresh output file")
    backend = EmaBackend()
    texts = {
        "greeting": "Merhaba, ben Burhan Çetinkaya’nın yapay zekâ asistanıyım.",
        "date-time": "Randevum 12 Kasım Perşembe günü saat 14:30'da.",
        "phone": "Telefon numaram 0555 000 00 01.",
        "amount": "Toplam 1.250,50 TL ve yüzde 25 indirim.",
        "foreign": "Toplantıyı Zoom veya Microsoft Teams üzerinden yapabiliriz.",
    }
    normalized = {name: backend.tts._frontend(text) for name, text in texts.items()}
    assert "on iki kasım" in normalized["date-time"] and "on dört" in normalized["date-time"]
    assert "bin iki yüz elli" in normalized["amount"] and "elli kuruş" in normalized["amount"]
    assert "zum" in normalized["foreign"] and "maykrosoft teams" in normalized["foreign"]
    assert (
        normalized["phone"]
        == "telefon numaram sıfır beş beş beş sıfır sıfır sıfır sıfır sıfır sıfır bir nokta"
    )
    outputs, metrics = {}, []
    for rate in (8000, 16000, 24000, 48000):
        started = time.monotonic()
        chunks = list(backend.tts.stream(texts["greeting"], seed=0, sample_rate=rate))
        audio = np.concatenate(chunks)
        assert audio.ndim == 1 and np.isfinite(audio).all() and np.max(np.abs(audio)) <= 1
        outputs[rate] = audio
        metrics.append(
            {
                "rate": rate,
                "samples": len(audio),
                "duration": len(audio) / rate,
                "elapsed_ms": (time.monotonic() - started) * 1000,
            }
        )
    assert max(m["duration"] for m in metrics) - min(m["duration"] for m in metrics) < 1 / 8000
    # EMA's direct 8 kHz path is a stateful low-pass conversion from its native 48 kHz.
    source = torch.from_numpy(outputs[48000])

    def resample(parts):
        converter = Resampler(8000)
        result = [converter.push(part) for part in parts]
        result.append(converter.flush())
        return torch.cat([part for part in result if part is not None]).numpy()

    whole = resample([source])
    split = resample([source[:19], source[19:48031], source[48031:]])
    assert np.array_equal(whole, split)
    assert whole.shape == outputs[8000].shape
    maximum = float(np.max(np.abs(whole - outputs[8000])))
    # Different CUDA batch/kernel timing may produce tiny floating-point differences.
    assert maximum < 0.01
    result = {
        "normalization": normalized,
        "rates": metrics,
        "direct_8k_vs_resampled_48k_max_abs": maximum,
        "resampler_chunk_invariant": True,
        "torch_peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
        "torch_peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20,
        "scope": "synthetic numerical calibration; pronunciation still needs listening",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"sample_rates_passed": len(metrics), "max_abs": maximum}))


if __name__ == "__main__":
    main()
