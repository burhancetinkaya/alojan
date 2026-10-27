"""Read immutable, operator-qualified presets without exposing tuning controls."""

from pydantic import ValidationError
from alojan_contracts.configuration import EnginePreset, canonical_digest

from alojan.auth import AuthError


def qualified_model(conn, model_id, revision=None):
    row = conn.execute(
        """SELECT c.revision,c.display_name,c.preset_id,c.preset_revision,
        p.configuration,p.digest FROM model_catalog_status s
        JOIN model_catalog c ON (c.id,c.revision)=(s.model_id,s.model_revision)
        JOIN engine_presets p ON (p.id,p.revision)=(c.preset_id,c.preset_revision)
        WHERE s.model_id=%s AND s.enabled FOR SHARE OF s""",
        (model_id,),
    ).fetchone()
    if not row or (revision is not None and row[0] != revision):
        raise AuthError("model_not_qualified", 409)
    try:
        preset = EnginePreset.model_validate(row[4])
        if canonical_digest(preset.model_dump()) != row[5]:
            raise ValueError("Preset digest mismatch")
    except (ValidationError, ValueError):
        raise AuthError("invalid_engine_preset", 503) from None
    return {
        "id": model_id,
        "revision": row[0],
        "display_name": row[1],
        "preset_id": row[2],
        "preset_revision": row[3],
        "preset": preset.model_dump(),
        "preset_digest": row[5],
    }


def available_models(accounts, token, scope):
    with accounts.workspace(token, scope) as (conn, _):
        rows = conn.execute(
            """SELECT c.id,c.revision,c.display_name FROM model_catalog c
            JOIN model_catalog_status s ON (s.model_id,s.model_revision)=(c.id,c.revision)
            WHERE s.enabled ORDER BY c.id LIMIT 100"""
        ).fetchall()
        return [{"id": row[0], "revision": row[1], "name": row[2]} for row in rows]
