"""Real CUDA speech through loopback SIP/RTP; synthetic fixtures only, no carrier call."""

import argparse
import audioop
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/sip-integration"))
from test_sip import Peer, connect, run_gateway  # noqa: E402
from test_speech import align_pcm, drive  # noqa: E402


def load_fixture(directory, name):
    manifest = json.loads((directory / "manifest.json").read_text())
    entry = next(e for e in manifest["files"] if e["file"] == name)
    path = directory / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        audio = wav.readframes(wav.getnframes())
        return audioop.ratecv(audio, 2, 1, wav.getframerate(), 8000, None)[0]


def validate(output, turn_model_dir=None, asr_port=15071):
    source = load_fixture(ROOT / "assets/asr/tr-v1", "phone.wav")
    reference = load_fixture(ROOT / "assets/prompts/tr-v3-ema", "unavailable.wav")
    results = []
    for codec, name in [(8, "pcma"), (0, "pcmu")]:
        case = output / name
        case.mkdir()
        config = {
            "speech_profile": True,
            "answer_delay_ms": 0,
            "speech_options": (
                ["--turn-model-dir", str(turn_model_dir)]
                if turn_model_dir
                else ["--speech-test-ms", "7000"]
            )
            + ["--asr-port", str(asr_port)],
            "max_call_seconds": 25,
        }
        with contextmanager(run_gateway)(case, config) as (port, log, _):
            peer = Peer(port, codec)
            try:
                packets, arrivals, ended = drive(
                    peer, connect(peer), log, duration=24, source=source
                )
                assert ended, log.read_text()
                contents = log.read_text()
                assert (
                    "reason=speech_test_complete" in contents
                    and "event=speech_fallback" not in contents
                )
                line = next(
                    line
                    for line in contents.splitlines()
                    if line.startswith("event=speech_test_complete ")
                )
                metrics = {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", line)}
                if turn_model_dir:
                    assert len(source) // 320 <= metrics["asr_frames"] < 500
                    assert metrics["asr_partials"] >= 6
                    assert 500 <= metrics["turn_silence_ms"] < 2000
                    assert metrics["turn_probability_milli"] >= 500
                else:
                    assert metrics["asr_frames"] == 350 and metrics["asr_partials"] == 7
                assert (
                    metrics["final_text_bytes"] > 0
                    and metrics["tts_frames"] == len(reference) // 320
                )
                assert metrics["output_port_ms"] == len(reference) // 16
                assert "input_bad_frames=0" in contents
                assert "voice_pipeline_ready=0" in contents
                timestamps = [struct.unpack("!I", packet[4:8])[0] for packet in packets]
                assert all((b - a) % 2**32 == 160 for a, b in zip(timestamps, timestamps[1:]))
                decode = audioop.alaw2lin if codec == 8 else audioop.ulaw2lin
                received = decode(b"".join(packet[12:] for packet in packets), 2)
                actual, relative = align_pcm(received, reference)
                assert relative < 0.04, relative
                with wave.open(str(case / "synthetic-received-closing.wav"), "wb") as wav:
                    wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                    wav.writeframes(actual)
                metrics.update(
                    codec=name,
                    rtp_packets=len(packets),
                    mean_packet_ms=1000 * (arrivals[-1] - arrivals[0]) / (len(packets) - 1),
                    closing_relative_rms_error=relative,
                )
                assert 17 < metrics["mean_packet_ms"] < 23
                results.append(metrics)
            finally:
                peer.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--turn-model-dir", type=Path)
    parser.add_argument("--asr-port", type=int, default=15071)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "gpu.csv").open("w") as log:
        monitor = subprocess.Popen(
            [
                "nvidia-smi",
                "--query-gpu=timestamp,memory.used",
                "--format=csv,noheader,nounits",
                "-lms",
                "100",
            ],
            stdout=log,
        )
        try:
            results = validate(args.output, args.turn_model_dir, args.asr_port)
        finally:
            monitor.terminate()
            monitor.wait(timeout=2)
    peak = max(
        int(line.rsplit(",", 1)[1]) for line in (args.output / "gpu.csv").read_text().splitlines()
    )
    report = {
        "cases": results,
        "sampled_host_peak_mib": peak,
        "scope": (
            "real loopback SIP/RTP + CPU turn detection + CUDA ASR/EMA; adaptive boundary and fixed response, no agent or carrier"
            if args.turn_model_dir
            else "real loopback SIP/RTP + CUDA ASR/EMA; scripted capture boundary and fixed response, no agent or carrier"
        ),
    }
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
