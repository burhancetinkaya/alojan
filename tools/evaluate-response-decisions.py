"""Synthetic-only Jev shadow evaluation. Never loads agents, private calls or tools."""

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/agent"))
from alojan_agent.decisions import Decisions, MODEL, SNAPSHOT, recent_dialogue  # noqa: E402


async def evaluate(output, cases_path=None, compare_history=False):
    cases = json.loads(
        (cases_path or ROOT / "tests/fixtures/response-experience/decisions-tr.json").read_text()
    )
    client = Decisions()
    rows = []
    try:
        for index, case in enumerate(cases):
            variants = ["with_history", "without_history"] if compare_history else ["with_history"]
            if index % 2:
                variants.reverse()
            for variant in variants:
                expected = (
                    case.get("without_history_expected", case["expected"])
                    if variant == "without_history"
                    else case["expected"]
                )
                history = (
                    recent_dialogue(
                        case.get("history", []) + [{"role": "user", "content": case["utterance"]}],
                        case["utterance"],
                    )
                    if variant == "with_history"
                    else []
                )
                decision = await client.decide(
                    case["utterance"],
                    credential=os.environ["OPENROUTER_API_KEY"],
                    identity=("synthetic-evaluation", "operator"),
                    history=history,
                )
                rows.append(
                    {
                        "id": case["id"],
                        "split": variant if compare_history else case["split"],
                        "expected": expected,
                        **asdict(decision),
                        "correct": decision.choice == expected,
                    }
                )
    finally:
        await client.close()
    report = {"model": MODEL, "qualified_snapshot": SNAPSHOT, "rows": rows, "summary": {}}
    for split in sorted({row["split"] for row in rows}):
        group = [row for row in rows if row["split"] == split]
        times = sorted(row["elapsed_ms"] for row in group if row["status"] == "observed")
        report["summary"][split] = {
            "attempted": len(group),
            "observed": len(times),
            "correct": sum(row["correct"] for row in group),
            "unknown": sum(row["choice"] == "unknown" for row in group),
            "median_http_ms": statistics.median(times) if times else None,
            "max_http_ms": max(times) if times else None,
            "unsafe_nonunknown": sum(
                row["expected"] == "unknown" and row["choice"] not in (None, "unknown")
                for row in group
            ),
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--compare-history", action="store_true")
    args = parser.parse_args()
    asyncio.run(evaluate(args.output, args.cases, args.compare_history))
