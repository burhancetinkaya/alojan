"""Paired synthetic tool-proposal timing; never executes tools or loads call data."""

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import statistics
import time

from openai import AsyncOpenAI

CASES = [
    "Bugünkü oturum sayısını getir.",
    "Bugünkü maliyeti kontrol et.",
    "Dünkü oturumları say.",
    "Bu haftanın toplam maliyetini getir.",
    "Kullanıcı bazında bugünkü oturum sayılarını getir.",
]


def tool(dynamic):
    properties = {
        "metric": {"type": "string", "enum": ["sessions", "cost", "users"]},
        "period": {"type": "string", "enum": ["today", "yesterday", "week"]},
    }
    if dynamic:
        properties["interim_text"] = {
            "type": ["string", "null"],
            "description": "Optional short Turkish waiting sentence describing this lookup, with no result, ETA or promise. May be null.",
        }
    return {
        "type": "function",
        "name": "synthetic_lookup",
        "description": "Propose a read-only aggregate lookup.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


def summary(rows, variant):
    group = [r for r in rows if r["variant"] == variant]
    times = sorted(r["elapsed_ms"] for r in group if r["status"] == "completed")
    return {
        "attempted": len(group),
        "completed": len(times),
        "p50_ms": statistics.median(times) if times else None,
        "p95_ms": times[math.ceil(len(times) * 0.95) - 1] if times else None,
        "with_candidate": sum(r.get("has_candidate", False) for r in group),
    }


async def run(output, rounds):
    rows = []
    async with AsyncOpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        timeout=15,
        max_retries=0,
    ) as client:
        for repetition in range(rounds):
            for index, utterance in enumerate(CASES):
                order = (False, True) if (repetition + index) % 2 == 0 else (True, False)
                for dynamic in order:
                    row = {
                        "repetition": repetition,
                        "case": index,
                        "variant": "metadata" if dynamic else "baseline",
                        "status": "failed",
                    }
                    started = time.monotonic()
                    try:
                        response = await client.responses.create(
                            model="openai/gpt-oss-120b",
                            input=utterance,
                            instructions="Choose the requested aggregate and time period. Today is fixed for this synthetic test. Do not invent results.",
                            tools=[tool(dynamic)],
                            tool_choice={"type": "function", "name": "synthetic_lookup"},
                            parallel_tool_calls=False,
                            reasoning={"effort": "medium"},
                            temperature=0.2,
                            max_output_tokens=4096,
                            store=False,
                            extra_body={
                                "provider": {"only": ["cerebras"], "allow_fallbacks": False}
                            },
                        )
                        calls = [item for item in response.output if item.type == "function_call"]
                        assert len(calls) == 1 and calls[0].name == "synthetic_lookup"
                        args = json.loads(calls[0].arguments)
                        assert set(args) == set(tool(dynamic)["parameters"]["properties"])
                        assert args["metric"] in ("sessions", "cost", "users")
                        assert args["period"] in ("today", "yesterday", "week")
                        row.update(
                            status="completed",
                            has_candidate=bool(args.get("interim_text")),
                            output_tokens=response.usage.output_tokens if response.usage else None,
                        )
                    except Exception as error:
                        row["error_type"] = type(error).__name__
                    row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
                    rows.append(row)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(
                        json.dumps(
                            {
                                "scope": "Synthetic forced tool proposals; no tool execution, ASR, TTS or RTP",
                                "rows": rows,
                                "summary": {v: summary(rows, v) for v in ("baseline", "metadata")},
                            },
                            indent=2,
                        )
                        + "\n"
                    )
    print(json.dumps({v: summary(rows, v) for v in ("baseline", "metadata")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=5, choices=range(1, 11))
    args = parser.parse_args()
    asyncio.run(run(args.output, args.rounds))
