"""Summarize content-free gateway/agent timings; never print caller data or IDs."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    samples = sorted(value for value in values if isinstance(value, (int, float)) and value >= 0)
    return {
        "samples": len(samples),
        "missing": len(values) - len(samples),
        "p50_ms": statistics.median(samples) if samples else None,
        "p95_ms": samples[math.ceil(0.95 * len(samples)) - 1] if samples else None,
        "max_ms": max(samples) if samples else None,
    }


def summarize(lines):
    agent, gateway = [], []
    malformed = 0
    for line in lines:
        try:
            if line.startswith("event=agent_latency data="):
                record = json.loads(line.split("data=", 1)[1])
                if not isinstance(record, dict) or "status" not in record:
                    raise ValueError("invalid timing record")
                agent.append(record)
            elif line.startswith("event=turn_latency "):
                fields = dict(item.split("=", 1) for item in line.split())
                record = {
                    key: int(value) if key.endswith("_ms") else value
                    for key, value in fields.items()
                }
                if "status" not in record:
                    raise ValueError("invalid timing record")
                gateway.append(record)
        except (ValueError, TypeError):
            malformed += 1

    def eligible(rows):
        return [r for r in rows if r["status"] == "completed" and r.get("kind") == "response"]

    result = {
        "scope": "server output timings, not handset arrival; music and recovery excluded",
        "malformed_records": malformed,
        "agent_status": dict(Counter(r["status"] for r in agent)),
        "gateway_status": dict(Counter(r["status"] for r in gateway)),
        "recovery_turns": sum(r.get("kind") != "response" for r in gateway),
    }
    for name, rows, fields in [
        (
            "agent",
            eligible(agent),
            ["db_ready_ms", "first_delta_ms", "first_spoken_delta_ms", "first_phrase_ms"],
        ),
        (
            "gateway",
            eligible(gateway),
            [
                "endpoint_silence_audio_ms",
                "asr_finalize_ms",
                "agent_first_phrase_ms",
                "tts_first_chunk_ms",
                "pcm_to_output_ms",
                "endpoint_to_audio_ms",
                "vad_end_to_audio_estimate_ms",
            ],
        ),
    ]:
        result[name] = {field: distribution([r.get(field, -1) for r in rows]) for field in fields}
    result["full_50_turn_sample"] = (
        result["gateway"]["vad_end_to_audio_estimate_ms"]["samples"] >= 50
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", type=Path, nargs="+")
    args = parser.parse_args()
    print(
        json.dumps(
            summarize(line for path in args.logs for line in path.read_text().splitlines()),
            indent=2,
        )
    )
