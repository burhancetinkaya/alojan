"""Live acceptance must validate evidence paths and preserve worker deadlines."""

import asyncio

import pytest
from agents import Runner

import test_agent_summary_live as legacy
import test_declared_outputs_live as extraction
import test_managed_summary_live as managed


@pytest.mark.parametrize(
    "function,args,variable",
    [
        (
            legacy.test_final_meaning_through_real_summary_and_database,
            (None, None, None),
            "ALOJAN_SUMMARY_EVIDENCE_DIR",
        ),
        (
            managed.test_final_meaning_through_real_managed_worker,
            (None, None, None, None, None),
            "ALOJAN_SUMMARY_EVIDENCE_DIR",
        ),
        (
            extraction.test_real_scoped_summary_extracts_pinned_fields,
            (None, None, None, None, None),
            "ALOJAN_OUTPUTS_EVIDENCE_DIR",
        ),
    ],
)
def test_evidence_path_checked_before_call_recording_or_inference(
    monkeypatch, tmp_path, function, args, variable
):
    # None collaborators ensure call setup/inference cannot succeed silently.
    monkeypatch.delenv(variable, raising=False)
    with pytest.raises(KeyError, match=variable):
        function(*args)
    destination = tmp_path / "file"
    destination.write_text("not a directory")
    monkeypatch.setenv(variable, str(destination))
    with pytest.raises(OSError):
        function(*args)


def test_request_spacing_does_not_consume_worker_deadline(monkeypatch):
    delays = []
    monkeypatch.setattr(legacy.time, "sleep", delays.append)

    async def model(*args, **kwargs):
        return "synthetic result"

    monkeypatch.setattr(Runner, "run", model)
    legacy.provider_diagnostics.__wrapped__(monkeypatch)
    assert delays == [6]

    async def run():
        async with asyncio.timeout(0.1):
            assert await Runner.run(None, "synthetic input") == "synthetic result"

    asyncio.run(run())
    assert delays == [6]
