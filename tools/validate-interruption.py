"""Real loopback SIP/RTP + CPU interruption + resident CUDA EMA and updated CUDA ASR."""

import argparse
import audioop
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/sip-integration"))
from test_sip import Peer, connect, run_gateway  # noqa: E402
from test_speech import align_pcm, drive  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "speech_validation", ROOT / "tools/validate-gateway-speech.py"
)
speech = importlib.util.module_from_spec(spec)
spec.loader.exec_module(speech)


def validate(output, asr_port):
    source = speech.load_fixture(ROOT / "assets/asr/tr-v1", "phone.wav")
    reference = speech.load_fixture(ROOT / "assets/prompts/tr-v3-ema", "unavailable.wav")
    results = []
    for codec, name in [(8, "pcma"), (0, "pcmu")]:
        case = output / name
        case.mkdir()
        config = {
            "speech_profile": True,
            "answer_delay_ms": 0,
            "max_call_seconds": 60,
            "speech_options": [
                "--turn-model-dir",
                str(ROOT / ".local/turn-models"),
                "--barge-in",
                "1",
                "--asr-port",
                str(asr_port),
            ],
        }
        with contextmanager(run_gateway)(case, config) as (port, log, _):
            peer = Peer(port, codec)
            try:
                media = connect(peer)
                drive(
                    peer,
                    media,
                    log,
                    source=source,
                    duration=20,
                    until="event=speech_speaking call=1 generation=turn-1",
                )
                assert "event=speech_speaking call=1 generation=turn-1" in log.read_text()
                began = time.monotonic()
                packets, arrivals, ended = drive(peer, media, log, source=source, duration=35)
                contents = log.read_text()
                assert ended and "event=speech_fallback" not in contents, contents
                assert "interruptions=1" in contents
                event = next(
                    line
                    for line in contents.splitlines()
                    if line.startswith("event=speech_interrupted")
                )
                metrics = {key: int(value) for key, value in re.findall(r"(\w+)=(-?\d+)", event)}
                histories = [
                    line for line in contents.splitlines() if line.startswith("event=sent_speech")
                ]
                assert len(histories) == 2 and "aligned_text_bytes=0 interrupted=1" in histories[0]
                assert (
                    "interrupted=0" in histories[1]
                    and f"sent_audio_ms={len(reference) // 16}" in histories[1]
                )
                assert int(re.search(r"aligned_text_bytes=(\d+)", histories[1])[1]) > 0
                decode = audioop.alaw2lin if codec == 8 else audioop.ulaw2lin
                received = decode(b"".join(packet[12:] for packet in packets), 2)
                _, relative = align_pcm(received, reference)
                assert relative < 0.04, relative
                # The repeated reply must be separated by sustained silence after invalidation.
                decision = metrics["decision_ms"] / 1000
                gap = [
                    decode(packet[12:], 2)
                    for packet, at in zip(packets, arrivals)
                    if decision + 0.1 < at < decision + 0.5
                ]
                assert len(gap) >= 15 and max(audioop.rms(frame, 2) for frame in gap) < 100
                results.append(
                    {
                        "codec": name,
                        "synthetic_input_start_to_decision_ms": round(
                            metrics["decision_ms"] - began * 1000, 2
                        ),
                        "last_output_port_minus_decision_ms": metrics["last_sent_ms"]
                        - metrics["decision_ms"],
                        "post_interrupt_silence_frames": len(gap),
                        "second_response_relative_rms_error": relative,
                        "history": histories,
                    }
                )
            finally:
                peer.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asr-port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "scope": "Synthetic local calls, real CPU/CUDA models; no agent or carrier acceptance",
        "gateway_sha256": hashlib.sha256(
            (ROOT / "build/local/voice-gateway").read_bytes()
        ).hexdigest(),
        "cases": validate(args.output, args.asr_port),
    }
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
