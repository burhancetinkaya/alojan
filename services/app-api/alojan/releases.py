"""Transactional release preparation/publication. No model or media calls."""

import json
import uuid

from psycopg import sql
from psycopg.types.json import Jsonb
from alojan_contracts.assets import speech_identity, validate_manifest
from alojan_contracts.configuration import EnginePreset, canonical_digest
from alojan_contracts.runtime import compile_agent
from alojan_contracts.routing import node_identifier

from alojan.auth import AuthError, audit
from alojan.connections import validate_connection
from alojan.catalog import qualified_model
from alojan.profiles import validate_draft, locked_draft
from alojan.action_grants import publication_grant


def validate_runtime(draft, preset, mcp_grant=None):
    try:
        compile_agent(draft, preset, mcp_grant=mcp_grant)
    except ValueError:
        raise AuthError("unsupported_agent_runtime", 409) from None


def mcp_authorization(conn, scope, profile, draft, *, previous=None):
    if not draft.mcp_tools and previous is None:
        return None
    from alojan.mcp_grants import publication_grant as mcp_grant

    return mcp_grant(conn, scope, profile, draft, previous=previous)


def prepared_assets(conn, scope, speech_digest, draft, preset):
    row = conn.execute(
        "SELECT manifest,manifest_digest FROM prepared_voice_assets WHERE scope_id=%s AND speech_digest=%s",
        (scope, speech_digest),
    ).fetchone()
    if not row:
        raise AuthError("voice_assets_pending", 409)
    try:
        manifest = validate_manifest(row[0], draft, preset)
        if canonical_digest(manifest.model_dump()) != row[1]:
            raise ValueError("Asset manifest digest mismatch")
    except ValueError:
        raise AuthError("invalid_voice_assets", 409) from None
    return manifest.model_dump()


class Releases:
    def __init__(self, accounts, node_id=None):
        self.accounts = accounts
        self.node_id = node_identifier(node_id) if node_id else None

    def prepare(self, token, scope, profile, version):
        with self.accounts.workspace(token, scope, roles=("owner", "editor")) as (conn, user):
            current, draft = locked_draft(conn, scope, profile)
            if current != version:
                raise AuthError("stale_version", 412)
            model = qualified_model(conn, draft.model)
            preset = EnginePreset.model_validate(model["preset"])
            validate_runtime(draft, preset, mcp_authorization(conn, scope, profile, draft))
            identity = speech_identity(draft, preset)
            row = conn.execute(
                """SELECT id FROM agent_preparations WHERE scope_id=%s AND profile_id=%s
                AND draft_version=%s AND model_id=%s AND model_revision=%s""",
                (scope, profile, version, draft.model, model["revision"]),
            ).fetchone()
            if row:
                preparation = row[0]
            else:
                count = conn.execute(
                    "SELECT count(*) FROM agent_preparations WHERE scope_id=%s AND profile_id=%s",
                    (scope, profile),
                ).fetchone()[0]
                if count >= 1000:
                    raise AuthError("preparation_limit", 409)
                preparation = uuid.uuid4()
                conn.execute(
                    """INSERT INTO agent_preparations(id,scope_id,profile_id,draft_version,
                    requested_by,model_id,model_revision,content,content_digest,speech_digest)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        preparation,
                        scope,
                        profile,
                        version,
                        user["id"],
                        draft.model,
                        model["revision"],
                        Jsonb(draft.model_dump()),
                        draft.digest(),
                        identity,
                    ),
                )
                audit(conn, user["id"], "agent.prepared", scope=scope, target=profile)
            try:
                prepared_assets(
                    conn, scope, identity, draft, EnginePreset.model_validate(model["preset"])
                )
                readiness = "ready_to_publish"
            except AuthError as exc:
                if exc.code != "voice_assets_pending":
                    raise
                readiness = "voice_assets_pending"
            return {
                "id": str(preparation),
                "draft_version": version,
                "speech_digest": identity,
                "readiness": readiness,
            }

    def list(self, token, scope, profile):
        with self.accounts.workspace(token, scope) as (conn, _):
            if not conn.execute(
                "SELECT 1 FROM agent_drafts WHERE scope_id=%s AND profile_id=%s", (scope, profile)
            ).fetchone():
                raise AuthError("not_found", 404)
            publication = conn.execute(
                "SELECT release_id,version FROM agent_publications WHERE scope_id=%s AND profile_id=%s",
                (scope, profile),
            ).fetchone()
            rows = conn.execute(
                """SELECT id,revision,manifest_digest,rollback_of FROM agent_releases
                WHERE scope_id=%s AND profile_id=%s ORDER BY revision DESC LIMIT 100""",
                (scope, profile),
            ).fetchall()
        return {
            "version": publication[1] if publication else 0,
            "current_release": str(publication[0]) if publication else None,
            "releases": [
                {
                    "id": str(r[0]),
                    "revision": r[1],
                    "digest": r[2],
                    "rollback_of": str(r[3]) if r[3] else None,
                }
                for r in rows
            ],
        }

    def status(self, token, scope, profile, release):
        with self.accounts.workspace(token, scope) as (conn, _):
            row = conn.execute(
                """SELECT p.release_id=r.id, a.checked_at, a.valid_until,
                a.ready AND a.manifest_digest=r.manifest_digest
                    AND a.acknowledged_at<=clock_timestamp()
                    AND a.valid_until>clock_timestamp()
                FROM agent_releases r
                LEFT JOIN agent_publications p ON p.scope_id=r.scope_id AND p.profile_id=r.profile_id
                LEFT JOIN release_readiness a ON a.scope_id=r.scope_id AND a.release_id=r.id AND a.node_id=%s
                WHERE r.scope_id=%s AND r.profile_id=%s AND r.id=%s""",
                (self.node_id, scope, profile, release),
            ).fetchone()
            if row is None:
                raise AuthError("not_found", 404)
        ready = bool(row[3])
        return {
            "release_id": str(release),
            "agent_id": str(profile),
            "current_publication": bool(row[0]),
            "node_ready": ready,
            "status": "node_not_configured"
            if self.node_id is None
            else "awaiting_node"
            if row[1] is None
            else "ready"
            if ready
            else "not_ready",
            "checked_at": row[1].isoformat() if row[1] else None,
            "valid_until": row[2].isoformat() if row[2] else None,
            "retry_after_seconds": 5 if not ready else None,
        }

    def publish(self, token, scope, profile, preparation, publication_version):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            version, draft = locked_draft(conn, scope, profile)
            row = conn.execute(
                """SELECT draft_version,content_digest,model_revision,speech_digest
                FROM agent_preparations WHERE scope_id=%s AND profile_id=%s AND id=%s""",
                (scope, profile, preparation),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
            if row[0] != version or row[1] != draft.digest():
                raise AuthError("stale_preparation", 409)
            model = qualified_model(conn, draft.model, row[2])
            preset = EnginePreset.model_validate(model["preset"])
            assets = prepared_assets(conn, scope, row[3], draft, preset)
            manifest = {
                "schema_version": 1,
                "content": draft.model_dump(),
                "model": model,
                "voice_assets": assets,
            }
            return self._publish(
                conn, user, scope, profile, preparation, manifest, publication_version
            )

    def rollback(self, token, scope, profile, release, publication_version):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            locked_draft(conn, scope, profile)
            row = conn.execute(
                """SELECT preparation_id,manifest,manifest_digest FROM agent_releases
                WHERE scope_id=%s AND profile_id=%s AND id=%s""",
                (scope, profile, release),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
            manifest = row[1]
            if canonical_digest(manifest) != row[2]:
                raise AuthError("invalid_release", 409)
            draft = validate_draft(manifest["content"])
            model = qualified_model(conn, draft.model, manifest["model"]["revision"])
            if model != manifest["model"]:
                raise AuthError("invalid_release", 409)
            prepared_assets(
                conn,
                scope,
                manifest["voice_assets"]["speech_digest"],
                draft,
                EnginePreset.model_validate(model["preset"]),
            )
            return self._publish(
                conn,
                user,
                scope,
                profile,
                row[0],
                manifest,
                publication_version,
                rollback_of=release,
            )

    def _publish(
        self, conn, user, scope, profile, preparation, manifest, version, rollback_of=None
    ):
        current = conn.execute(
            "SELECT version FROM agent_publications WHERE scope_id=%s AND profile_id=%s",
            (scope, profile),
        ).fetchone()
        if (current[0] if current else 0) != version:
            raise AuthError("stale_publication", 412)
        revision = conn.execute(
            "SELECT coalesce(max(revision),0)+1 FROM assistant_profile_revisions WHERE scope_id=%s AND profile_id=%s",
            (scope, profile),
        ).fetchone()[0]
        if revision > 1000:
            raise AuthError("release_limit", 409)
        draft = validate_draft(manifest["content"])
        validate_connection(conn, scope, draft.model_connection)
        if rollback_of and draft.post_call_actions and "action_grant" not in manifest:
            raise AuthError("invalid_action_grant", 409)
        authorization = publication_grant(
            conn,
            scope,
            profile,
            draft,
            previous=manifest.get("action_grant") if rollback_of else None,
        )
        if rollback_of and draft.mcp_tools and "mcp_grant" not in manifest:
            raise AuthError("invalid_mcp_grant", 409)
        mcp_grant = mcp_authorization(
            conn,
            scope,
            profile,
            draft,
            previous=manifest.get("mcp_grant") if rollback_of else None,
        )
        manifest = dict(manifest)
        if authorization:
            manifest.update(schema_version=2, action_grant=authorization)
        if mcp_grant:
            manifest.update(schema_version=3, mcp_grant=mcp_grant)
        if draft.outputs:
            manifest["schema_version"] = 4
        if any(a.condition != "answered" for a in draft.post_call_actions):
            manifest["schema_version"] = 5
        if any(getattr(a, "transcript_policy", None) for a in draft.post_call_actions):
            manifest["schema_version"] = 6
        if any(a.condition in ("no_answer", "interrupted") for a in draft.post_call_actions):
            manifest["schema_version"] = 7
        if mcp_grant and mcp_grant["review"]["schema_version"] == 2:
            manifest["schema_version"] = 8
        if mcp_grant and mcp_grant["review"]["schema_version"] == 3:
            manifest["schema_version"] = 9
        if draft.prompt_template is not None:
            manifest["schema_version"] = 10
        # Stay below the existing JSONB/preload budget, including PostgreSQL formatting.
        if len(json.dumps(manifest, ensure_ascii=False).encode()) > 131072 or (
            mcp_grant
            and conn.execute("SELECT octet_length(%s::jsonb::text)", (Jsonb(manifest),)).fetchone()[
                0
            ]
            > 131072
        ):
            raise AuthError("release_manifest_limit", 409)
        preset = manifest["model"]["preset"]
        validate_runtime(draft, EnginePreset.model_validate(preset), mcp_grant)
        fields = {
            key: getattr(draft, key)
            for key in (
                "owner_display_name",
                "agent_name",
                "owner_address",
                "owner_dative",
                "owner_genitive",
                "language",
                "role_description",
                "tone_description",
                "business_context",
                "availability_text",
                "offer_further_help",
                "further_help_text",
                "clarification_text",
                "silence_reminder_text",
                "silence_timeout_text",
                "farewell_text",
                "explicit_stop_text",
                "note_ack_template",
                "callback_unknown_template",
                "summary_role_template",
            )
        }
        fields.update(
            scope_id=scope,
            profile_id=profile,
            revision=revision,
            greeting_template=draft.greeting(),
            voice_ref=draft.voice,
            response_max_sentences=preset["reply_max_sentences"],
            response_max_chars=preset["reply_max_chars"],
            response_max_questions=preset["reply_max_questions"],
        )
        conn.execute(
            sql.SQL("INSERT INTO assistant_profile_revisions ({}) VALUES ({})").format(
                sql.SQL(",").join(map(sql.Identifier, fields)),
                sql.SQL(",").join(sql.Placeholder() for _ in fields),
            ),
            tuple(fields.values()),
        )
        release = uuid.uuid4()
        digest = canonical_digest(manifest)
        conn.execute(
            """INSERT INTO agent_releases(id,scope_id,profile_id,revision,preparation_id,
            speech_digest,manifest,manifest_digest,published_by,rollback_of,action_grant_id,mcp_grant_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                release,
                scope,
                profile,
                revision,
                preparation,
                manifest["voice_assets"]["speech_digest"],
                Jsonb(manifest),
                digest,
                user["id"],
                rollback_of,
                authorization["id"] if authorization else None,
                mcp_grant["id"] if mcp_grant else None,
            ),
        )
        conn.execute(
            """INSERT INTO agent_publications(scope_id,profile_id,release_id,version,node_id)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (profile_id) DO UPDATE
            SET release_id=excluded.release_id,version=excluded.version,
                node_id=coalesce(excluded.node_id,agent_publications.node_id)""",
            (scope, profile, release, version + 1, self.node_id),
        )
        audit(
            conn,
            user["id"],
            "agent.rolled_back" if rollback_of else "agent.published",
            scope=scope,
            target=release,
        )
        return {
            "id": str(release),
            "revision": revision,
            "version": version + 1,
            "digest": digest,
            "status": "published",
            **({"deployment_status": "requires_delivery_worker"} if authorization else {}),
        }
