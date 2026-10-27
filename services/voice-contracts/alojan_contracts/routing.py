"""Exact number and pinned-release contracts; no SIP headers are trusted here."""

import json
import re
from dataclasses import dataclass

from alojan_contracts.assets import validate_manifest
from alojan_contracts.actions import ActionAuthorization
from alojan_contracts.configuration import AgentDraft, EnginePreset, canonical_digest


def canonical_did(value):
    if not isinstance(value, str) or not re.fullmatch(r"\+90850[0-9]{7}", value):
        raise ValueError("A canonical Netgsm 0850 DID is required")
    return value


def node_identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value):
        raise ValueError("Invalid voice node identifier")
    return value


def validated_release(value, digest):
    required = {
        "schema_version",
        "content",
        "model",
        "voice_assets",
    }
    if not isinstance(value, dict) or set(value) not in (
        required,
        required | {"action_grant"},
        required | {"mcp_grant"},
        required | {"action_grant", "mcp_grant"},
    ):
        raise ValueError("Invalid release manifest")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        or canonical_digest(value) != digest
    ):
        raise ValueError("Unsupported or corrupt release")
    draft = AgentDraft.model_validate(value["content"])
    if draft.post_call_actions:
        if "action_grant" not in value:
            raise ValueError("Action release requires explicit authorization")
        ActionAuthorization.model_validate(value["action_grant"]).review.check_draft(draft)
    elif "action_grant" in value:
        raise ValueError("Unexpected action authorization")
    if draft.mcp_tools:
        from alojan_contracts.mcp_release import authorization

        authorization(value.get("mcp_grant"), draft)
        if value.get("action_grant") and any(
            value["action_grant"]["review"][key] != value["mcp_grant"]["review"][key]
            for key in ("scope_id", "profile_id")
        ):
            raise ValueError("Release grant ownership mismatch")
    elif "mcp_grant" in value:
        raise ValueError("Unexpected MCP authorization")
    expected = (
        10
        if draft.prompt_template is not None
        else 9
        if value.get("mcp_grant", {}).get("review", {}).get("schema_version") == 3
        else 8
        if value.get("mcp_grant", {}).get("review", {}).get("schema_version") == 2
        else 7
        if any(a.condition in ("no_answer", "interrupted") for a in draft.post_call_actions)
        else 6
        if any(getattr(a, "transcript_policy", None) for a in draft.post_call_actions)
        else 5
        if any(a.condition != "answered" for a in draft.post_call_actions)
        else 4
        if draft.outputs
        else (3 if draft.mcp_tools else (2 if draft.post_call_actions else 1))
    )
    if value["schema_version"] != expected:
        raise ValueError("Release capability version mismatch")
    from alojan_contracts.outputs import validate_tools

    validate_tools(draft.outputs, value.get("mcp_grant", {}).get("review", {}).get("tools", []))
    model = value["model"]
    if not isinstance(model, dict) or set(model) != {
        "id",
        "revision",
        "display_name",
        "preset_id",
        "preset_revision",
        "preset",
        "preset_digest",
    }:
        raise ValueError("Invalid model definition")
    preset = EnginePreset.model_validate(model["preset"])
    if (
        model["id"] != draft.model
        or type(model["revision"]) is not int
        or model["revision"] < 1
        or canonical_digest(preset.model_dump()) != model["preset_digest"]
    ):
        raise ValueError("Invalid model/preset identity")
    validate_manifest(value["voice_assets"], draft, preset)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class PinnedRoute:
    call_id: str
    scope_id: str
    number_id: str
    binding_id: str
    profile_id: str
    release_id: str
    node_id: str
    manifest_digest: str
    # Immutable serialized bytes/text; each consumer creates its own mutable objects.
    manifest_json: str
