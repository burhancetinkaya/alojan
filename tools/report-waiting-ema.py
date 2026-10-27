"""Summarize the opt-in ABBA EMA/SIP benchmark without claiming ASR/model acceptance."""

import argparse
import json
import math
from pathlib import Path
import statistics
import random

FIELDS = ("endpoint_to_audio_ms", "pcm_to_output_ms", "agent_first_phrase_ms", "tts_first_chunk_ms")


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "p50": None, "p95": None, "max": None}
    return {
        "count": len(ordered),
        "p50": statistics.median(ordered),
        "p95": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "max": ordered[-1],
    }


def paired_bootstrap(pairs):
    # Descriptive only: turns within the four calls are correlated; no rollout qualification.
    rng = random.Random(20261027)
    differences = {"p50": [], "p95": []}
    for _ in range(5000):
        sample = rng.choices(pairs, k=len(pairs))
        a, b = distribution([x[0] for x in sample]), distribution([x[1] for x in sample])
        for metric in differences:
            differences[metric].append(b[metric] - a[metric])
    return {
        metric: {"lower_95_ms": sorted(values)[124], "upper_95_ms": sorted(values)[4874]}
        for metric, values in differences.items()
    }


def report(calls):
    if len(calls) != 4 or [c["position"] for c in calls] != list(range(4)):
        raise ValueError("Four complete ABBA calls are required")
    if [c["enabled"] for c in calls] != [False, True, True, False]:
        raise ValueError("ABBA order required")
    for call in calls:
        rows = call["rows"]
        if len(rows) != 14 or [r["generation"] for r in rows] != [
            f"turn-{i}" for i in range(1, 15)
        ]:
            raise ValueError("Fourteen unique ordered turns per call required")
        if any(r["status"] != "completed" or int(r["error"]) != 0 for r in rows):
            raise ValueError("Incomplete or failed turns cannot qualify latency")
        if any(int(r[f]) < 0 for r in rows for f in FIELDS):
            raise ValueError("Missing measurements cannot count as zero latency")
        expected = [f"turn-{i}-p0" for i in (3, 4, 5, 7, 10, 11, 12, 14)] if call["enabled"] else []
        if [r["generation"] for r in call["waiting"]] != expected:
            raise ValueError("Waiting speech must occur exactly once in each slow turn only")
        if any(int(r["endpoint_to_audio_ms"]) < 0 for r in call["waiting"]):
            raise ValueError("Waiting latency must be measured")
    variants = {}
    for enabled, name in [(False, "baseline"), (True, "prepared_waiting")]:
        selected = [c for c in calls if c["enabled"] == enabled]
        variants[name] = {
            f: distribution([int(r[f]) for c in selected for r in c["rows"]]) for f in FIELDS
        }
        variants[name]["waiting_segments"] = sum(len(c["waiting"]) for c in selected)
        variants[name]["waiting_endpoint_to_audio_ms"] = distribution(
            [int(r["endpoint_to_audio_ms"]) for c in selected for r in c["waiting"]]
        )
    paired = {}
    for field in FIELDS:
        values = []
        for baseline, candidate in [(calls[0], calls[1]), (calls[3], calls[2])]:
            values.extend(
                int(b[field]) - int(a[field]) for a, b in zip(baseline["rows"], candidate["rows"])
            )
        paired[field] = distribution(values)
    p95_delta = (
        variants["prepared_waiting"]["endpoint_to_audio_ms"]["p95"]
        - variants["baseline"]["endpoint_to_audio_ms"]["p95"]
    )
    pairs = [
        (int(a["endpoint_to_audio_ms"]), int(b["endpoint_to_audio_ms"]))
        for first, second in [(calls[0], calls[1]), (calls[3], calls[2])]
        for a, b in zip(first["rows"], second["rows"])
    ]
    return {
        "descriptive_paired_bootstrap": paired_bootstrap(pairs),
        "confidence_limit": "Exploratory turn-pair bootstrap only; four correlated calls do not establish rollout confidence",
        "scope": "Real resident EMA and native loopback SIP/RTP; scripted ASR, tool delays and answers; capacity one",
        "turns": 56,
        "variants": variants,
        "paired_candidate_minus_baseline_ms": paired,
        "cohort_useful_answer_p95_delta_ms": p95_delta,
        "observed_cohort_p95_within_50ms": p95_delta <= 50,
        "full_product_acceptance": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = report([json.loads((args.directory / f"call-{i}.json").read_text()) for i in range(4)])
    (args.directory / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
