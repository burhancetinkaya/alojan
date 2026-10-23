"""Regenerate the M1 Turkish test prompts on the pinned Linux development host."""

import argparse
import audioop  # Python 3.12 pin; replace the offline resampler before upgrading to 3.13.
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]


def generate(engine: Path, output_dir: Path):
    engine_hash = hashlib.sha256(engine.read_bytes()).hexdigest()
    if engine_hash != "34191438b1e0f8f5aac5d4fdc5df574762b6fbb3c7a219a8c6f14feceb1bd076":
        raise ValueError("Fixture generation requires the documented Ubuntu amd64 engine binary")
    for package in ("libespeak-ng1", "espeak-ng-data"):
        installed = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Version}", package], text=True
        )
        if installed != "1.51+dfsg-12build1":
            raise ValueError("Fixture generation requires the documented library/data versions")
    version = subprocess.check_output([str(engine), "--version"], text=True).splitlines()[0]
    if not version.startswith("eSpeak NG text-to-speech: 1.51 "):
        raise ValueError("Fixture generation requires the documented eSpeak NG 1.51 build")
    output_dir.mkdir(parents=True, exist_ok=True)
    files = []
    with tempfile.TemporaryDirectory() as temporary:
        for name in ("greeting", "unavailable"):
            source = ROOT / "assets/prompts/tr-v1" / f"{name}.txt"
            raw = Path(temporary) / f"{name}.wav"
            subprocess.run(
                [
                    str(engine),
                    "-v",
                    "tr",
                    "-s",
                    "155",
                    "-a",
                    "80",
                    "-f",
                    str(source),
                    "-w",
                    str(raw),
                ],
                check=True,
                timeout=30,
            )
            with wave.open(str(raw), "rb") as speech:
                if (speech.getnchannels(), speech.getsampwidth()) != (1, 2):
                    raise ValueError("Unexpected synthesis format")
                pcm, _ = audioop.ratecv(
                    speech.readframes(speech.getnframes()), 2, 1, speech.getframerate(), 8000, None
                )
            # End on a telephony frame boundary; never crop the final spoken samples.
            pcm += bytes((-len(pcm)) % 320)
            destination = output_dir / f"{name}.wav"
            with wave.open(str(destination), "wb") as speech:
                speech.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                speech.writeframes(pcm)
            files.append(
                {
                    "file": destination.name,
                    "text_file": source.name,
                    "text_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    "samples": len(pcm) // 2,
                    "duration_ms": len(pcm) // 16,
                }
            )
    manifest = {
        "schema_version": 1,
        "profile": "tr-v1-formant-test",
        "engine": "espeak-ng",
        "engine_version": "1.51+dfsg-12build1",
        "engine_binary_sha256": engine_hash,
        "engine_package_sha256": "ffeac730f1f43b5cdbca708a8215d6b7310bf3bd40d7dcf0affd6a62f86aa6df",
        "voice": "tr",
        "words_per_minute": 155,
        "amplitude": 80,
        "resampler": f"CPython {platform.python_version()} audioop.ratecv, default weights",
        "format": "pcm_s16le",
        "sample_rate_hz": 8000,
        "channels": 1,
        "files": files,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    generate(arguments.engine.resolve(), arguments.output_dir)
