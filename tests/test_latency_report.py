"""Unknown and failed measurements must never improve a latency percentile."""

from pathlib import Path
import runpy


def test_latency_report_excludes_recovery_failure_and_missing_audio():
    report = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tools/report-latency.py"))
    result = report["summarize"](
        [
            "event=turn_latency status=completed kind=response endpoint_to_audio_ms=200 vad_end_to_audio_estimate_ms=700",
            "event=turn_latency status=completed kind=response endpoint_to_audio_ms=-1 vad_end_to_audio_estimate_ms=-1",
            "event=turn_latency status=failed kind=response endpoint_to_audio_ms=1",
            "event=turn_latency status=cancelled kind=response endpoint_to_audio_ms=2",
            "event=turn_latency status=completed kind=silence_reminder endpoint_to_audio_ms=3",
            "event=agent_latency data=broken",
            'event=agent_latency data={"status":"completed","kind":"response","first_phrase_ms":180}',
        ]
    )
    assert result["gateway"]["endpoint_to_audio_ms"] == {
        "samples": 1,
        "missing": 1,
        "p50_ms": 200,
        "p95_ms": 200,
        "max_ms": 200,
    }
    assert result["gateway_status"] == {"completed": 3, "failed": 1, "cancelled": 1}
    assert result["recovery_turns"] == result["malformed_records"] == 1
    assert not result["full_50_turn_sample"]
    assert result["agent"]["first_phrase_ms"]["p50_ms"] == 180
