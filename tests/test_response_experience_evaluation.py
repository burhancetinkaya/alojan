"""Evaluation reports must distinguish missing/failed observations from fast success."""

import importlib.util
from pathlib import Path


def test_metadata_report_excludes_failures_from_timings_without_hiding_attempts():
    path = Path(__file__).resolve().parents[1] / "tools/benchmark-interim-metadata.py"
    spec = importlib.util.spec_from_file_location("interim_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [
        {"variant": "metadata", "status": "failed", "elapsed_ms": 1},
        {"variant": "metadata", "status": "completed", "elapsed_ms": 100, "has_candidate": True},
        {"variant": "baseline", "status": "completed", "elapsed_ms": 20},
    ]
    assert module.summary(rows, "metadata") == {
        "attempted": 2,
        "completed": 1,
        "p50_ms": 100,
        "p95_ms": 100,
        "with_candidate": 1,
    }
    assert module.summary([], "baseline")["p95_ms"] is None


def test_ema_report_rejects_partial_failed_or_missing_measurements():
    import copy
    import pytest

    path = Path(__file__).resolve().parents[1] / "tools/report-waiting-ema.py"
    spec = importlib.util.spec_from_file_location("ema_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = [
        {
            "position": i,
            "enabled": i in (1, 2),
            "waiting": [
                {"generation": f"turn-{j}-p0", "endpoint_to_audio_ms": "1820"}
                for j in (3, 4, 5, 7, 10, 11, 12, 14)
            ]
            if i in (1, 2)
            else [],
            "rows": [
                {
                    "generation": f"turn-{j}",
                    "status": "completed",
                    "error": "0",
                    **{field: str(130 if i in (1, 2) else 100) for field in module.FIELDS},
                }
                for j in range(1, 15)
            ],
        }
        for i in range(4)
    ]
    result = module.report(calls)
    assert result["turns"] == 56 and result["cohort_useful_answer_p95_delta_ms"] == 30
    assert result["observed_cohort_p95_within_50ms"] and not result["full_product_acceptance"]
    for mode in ("missing", "failed", "partial", "order", "missing_wait", "duplicate_wait"):
        changed = copy.deepcopy(calls)
        if mode == "missing":
            changed[1]["rows"][0]["pcm_to_output_ms"] = "-1"
        elif mode == "failed":
            changed[1]["rows"][0]["status"] = "failed"
        elif mode == "partial":
            changed[1]["rows"].pop()
        elif mode == "order":
            changed[1]["rows"][0]["generation"] = "turn-2"
        elif mode == "missing_wait":
            changed[1]["waiting"].pop()
        else:
            changed[1]["waiting"].append(changed[1]["waiting"][0])
        with pytest.raises(ValueError):
            module.report(changed)
    for row in calls[1]["rows"]:
        row["endpoint_to_audio_ms"] = "200"
    assert not module.report(calls)["observed_cohort_p95_within_50ms"]
