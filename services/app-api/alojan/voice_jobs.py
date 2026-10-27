"""Scoped audio requests. HTTP never opens admission, contacts TTS or writes assets."""

import uuid

from alojan.auth import AuthError, audit
from alojan.catalog import qualified_model
from alojan.profiles import locked_draft
from alojan.releases import Releases, prepared_assets
from alojan_contracts.assets import speech_identity
from alojan_contracts.configuration import EnginePreset


class VoiceJobs:
    def __init__(self, accounts):
        self.accounts = accounts

    def status(self, token, scope, profile, version):
        with self.accounts.workspace(token, scope) as (conn, _):
            return self._status(conn, scope, profile, version)

    @staticmethod
    def _status(conn, scope, profile, version):
        current, draft = locked_draft(conn, scope, profile)
        if current != version:
            raise AuthError("stale_version", 412)
        model = qualified_model(conn, draft.model)
        preset = EnginePreset.model_validate(model["preset"])
        identity = speech_identity(draft, preset)
        try:
            prepared_assets(conn, scope, identity, draft, preset)
            return {"status": "ready", "attempt": 0, "failure_code": None}
        except AuthError as exc:
            if exc.code != "voice_assets_pending":
                raise
        row = conn.execute(
            """SELECT j.status,j.attempt,j.failure_code FROM voice_preparation_jobs j
            JOIN agent_preparations p ON p.id=j.preparation_id AND p.scope_id=j.scope_id
            WHERE p.scope_id=%s AND p.profile_id=%s AND p.draft_version=%s
              AND p.model_id=%s AND p.model_revision=%s
            ORDER BY j.attempt DESC LIMIT 1""",
            (scope, profile, version, draft.model, model["revision"]),
        ).fetchone()
        return dict(zip(("status", "attempt", "failure_code"), row or ("missing", 0, None)))

    def request(self, token, scope, profile, version):
        preparation = Releases(self.accounts).prepare(token, scope, profile, version)
        with self.accounts.workspace(token, scope, roles=("owner", "editor")) as (conn, user):
            # Serialize quotas across agents in one workspace, before taking the draft lock.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,16))", (str(scope),))
            state = self._status(conn, scope, profile, version)
            if state["status"] in ("ready", "queued", "preparing"):
                return state
            if state["attempt"] >= 3:
                raise AuthError("voice_preparation_limit", 409)
            pending = conn.execute(
                """SELECT count(*) FROM voice_preparation_jobs WHERE scope_id=%s
                AND status IN ('queued','preparing')""",
                (scope,),
            ).fetchone()[0]
            recent = conn.execute(
                """SELECT count(*) FROM voice_preparation_jobs WHERE scope_id=%s
                AND created_at>now()-interval '1 hour'""",
                (scope,),
            ).fetchone()[0]
            if pending >= 4 or recent >= 10:
                raise AuthError("voice_preparation_limit", 429)
            attempt = state["attempt"] + 1
            conn.execute(
                """INSERT INTO voice_preparation_jobs
                (id,scope_id,profile_id,preparation_id,attempt) VALUES (%s,%s,%s,%s,%s)""",
                (uuid.uuid4(), scope, profile, preparation["id"], attempt),
            )
            audit(conn, user["id"], "agent.audio_requested", scope=scope, target=profile)
            return {"status": "queued", "attempt": attempt, "failure_code": None}
