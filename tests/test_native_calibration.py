"""Operator preset validation, historical digest stability and native transport."""

import json
from pathlib import Path
import re

import pytest
from pydantic import ValidationError
from alojan_contracts.configuration import (
    AgentDraft,
    EnginePreset,
    NativeCalibration,
    canonical_digest,
)


def test_historical_preset_digest_and_native_defaults_do_not_change():
    source = (Path(__file__).resolve().parents[1] / "infra/examples/agent_catalog.sql").read_text()
    raw, digest = re.search(r"'({.*})'::jsonb,'([a-f0-9]{64})'", source).groups()
    original = json.loads(raw)
    engine = EnginePreset.model_validate(original)
    assert engine.model_dump() == original
    assert engine.model_dump_json() and canonical_digest(engine.model_dump()) == digest
    assert engine.calibration is None
    calibration = engine.gateway_configuration().calibration
    # Historical v1 behavior is a compatibility fixture, not a tunable class default.
    expected = dict(
        schema_version=1,
        partial_hint=False,
        vad_percent=50,
        candidate_ms=250,
        yes_no_ms=350,
        open_ms=500,
        uncertain_ms=1200,
        incomplete_ms=2200,
        silence_reminder_ms=7000,
        interrupt_vad_percent=50,
        interrupt_min_voice_ms=192,
        interrupt_sustained_voice_ms=640,
        interrupt_max_quiet_ms=800,
        interrupt_sustained_quiet_ms=160,
    )
    assert {field: getattr(calibration, field) for field in expected} == expected


def test_new_preset_is_immutable_explicit_and_roundtrips_all_native_fields():
    values = NativeCalibration(
        partial_hint=True,
        vad_percent=30,
        candidate_ms=400,
        yes_no_ms=700,
        open_ms=900,
        uncertain_ms=1600,
        incomplete_ms=3000,
        silence_reminder_ms=9000,
        interrupt_vad_percent=40,
        interrupt_min_voice_ms=320,
        interrupt_sustained_voice_ms=960,
        interrupt_max_quiet_ms=1000,
        interrupt_sustained_quiet_ms=240,
    ).model_dump()
    engine = EnginePreset(calibration=values)
    digest = canonical_digest(engine.model_dump())
    values["open_ms"] = 1500
    restored = EnginePreset.model_validate_json(engine.model_dump_json())
    assert restored == engine and canonical_digest(restored.model_dump()) == digest
    assert engine.gateway_configuration().ByteSize() <= 256
    native = engine.gateway_configuration().calibration
    for key, value in engine.calibration.model_dump().items():
        assert getattr(native, key) == value
    with pytest.raises(ValidationError):
        engine.calibration.open_ms = 1500
    native.open_ms = 1500
    assert engine.gateway_configuration().calibration.open_ms == 900


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 2},
        {"partial_hint": 1},
        {"vad_percent": 19},
        {"vad_percent": 91},
        {"candidate_ms": 99},
        {"candidate_ms": 501},
        {"yes_no_ms": 349},
        {"yes_no_ms": 1001},
        {"open_ms": 499},
        {"open_ms": 1501},
        {"uncertain_ms": 1199},
        {"uncertain_ms": 2001},
        {"incomplete_ms": 2199},
        {"incomplete_ms": 5001},
        {"silence_reminder_ms": 2999},
        {"silence_reminder_ms": 15001},
        {"silence_reminder_ms": 7001},
        {"interrupt_vad_percent": 19},
        {"interrupt_vad_percent": 91},
        {"interrupt_min_voice_ms": 128},
        {"interrupt_min_voice_ms": 352},
        {"interrupt_min_voice_ms": 193},
        {"interrupt_sustained_voice_ms": 288},
        {"interrupt_sustained_voice_ms": 1312},
        {"interrupt_sustained_voice_ms": 641},
        {"interrupt_max_quiet_ms": 380},
        {"interrupt_max_quiet_ms": 1220},
        {"interrupt_max_quiet_ms": 801},
        {"interrupt_sustained_quiet_ms": 60},
        {"interrupt_sustained_quiet_ms": 340},
        {"interrupt_sustained_quiet_ms": 161},
        {"candidate_ms": 500},
        {"yes_no_ms": 900},
        {"open_ms": 1500},
        {"interrupt_min_voice_ms": 320, "interrupt_sustained_voice_ms": 320},
        {"caller_override": True},
    ],
)
def test_invalid_calibration_cannot_enter_a_preset(changes):
    with pytest.raises(ValidationError):
        EnginePreset(calibration=changes)


def test_users_cannot_supply_technical_calibration():
    from test_agent_drafts import content

    with pytest.raises(ValidationError):
        AgentDraft(**content(), calibration=NativeCalibration().model_dump())
