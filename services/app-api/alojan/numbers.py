"""Owner-controlled bindings; proof and consumer readiness are separate authorities."""

import uuid

import psycopg
from alojan_contracts.routing import canonical_did, node_identifier, validated_release

from alojan.auth import AuthError, audit
from alojan.catalog import qualified_model


def locked_number(conn, scope, number, version):
    row = conn.execute(
        "SELECT version,status,enabled FROM phone_numbers WHERE scope_id=%s AND id=%s FOR UPDATE",
        (scope, number),
    ).fetchone()
    if not row:
        raise AuthError("not_found", 404)
    if row[0] != version:
        raise AuthError("stale_version", 412)
    return row


class Numbers:
    def __init__(self, accounts, node_id=None):
        self.accounts = accounts
        self.node_id = node_identifier(node_id) if node_id is not None else None

    def list(self, token, scope):
        with self.accounts.workspace(token, scope) as (conn, _):
            rows = conn.execute(
                """SELECT n.id,n.e164,n.status,n.version,n.enabled,b.release_id
                FROM phone_numbers n LEFT JOIN number_bindings b ON b.id=n.active_binding_id
                AND b.scope_id=n.scope_id WHERE n.scope_id=%s ORDER BY n.created_at,n.id LIMIT 100""",
                (scope,),
            ).fetchall()
        return [
            {
                "id": str(r[0]),
                "number": r[1],
                "status": r[2],
                "version": r[3],
                "enabled": r[4],
                "release_id": str(r[5]) if r[5] else None,
            }
            for r in rows
        ]

    def create(self, token, scope, value):
        try:
            did = canonical_did(value)
        except ValueError:
            raise AuthError("invalid_number", 400) from None
        number = uuid.uuid4()
        try:
            with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,714206))", (str(scope),)
                )
                if (
                    conn.execute(
                        "SELECT count(*) FROM phone_numbers WHERE scope_id=%s", (scope,)
                    ).fetchone()[0]
                    >= 100
                ):
                    raise AuthError("workspace_number_limit", 409)
                conn.execute(
                    "INSERT INTO phone_numbers(id,scope_id,e164) VALUES (%s,%s,%s)",
                    (number, scope, did),
                )
                audit(conn, user["id"], "number.requested", scope=scope, target=number)
        except psycopg.errors.UniqueViolation:
            raise AuthError("number_already_registered", 409) from None
        return {
            "id": str(number),
            "number": did,
            "version": 1,
            "status": "pending",
            "enabled": False,
        }

    def bind(self, token, scope, number, release, version):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            current = locked_number(conn, scope, number, version)
            if current[1] != "verified":
                raise AuthError("number_not_verified", 409)
            if not self.node_id:
                raise AuthError("voice_node_not_configured", 409)
            row = conn.execute(
                "SELECT profile_id,manifest,manifest_digest FROM agent_releases WHERE scope_id=%s AND id=%s",
                (scope, release),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
            try:
                validated_release(row[1], row[2])
            except ValueError:
                raise AuthError("invalid_release", 409) from None
            model = row[1]["model"]
            if qualified_model(conn, model["id"], model["revision"]) != model:
                raise AuthError("invalid_release", 409)
            ready = conn.execute(
                """SELECT 1 FROM release_readiness WHERE scope_id=%s AND release_id=%s
                AND node_id=%s AND manifest_digest=%s AND ready
                AND acknowledged_at <= clock_timestamp() AND valid_until > clock_timestamp()
                FOR SHARE""",
                (scope, release, self.node_id, row[2]),
            ).fetchone()
            if not ready:
                raise AuthError("release_not_ready_on_node", 409)
            binding = uuid.uuid4()
            conn.execute(
                """INSERT INTO number_bindings(id,scope_id,number_id,revision,profile_id,release_id,node_id,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (binding, scope, number, version + 1, row[0], release, self.node_id, user["id"]),
            )
            conn.execute(
                """UPDATE phone_numbers SET active_binding_id=%s,enabled=true,version=version+1,
                updated_at=now() WHERE scope_id=%s AND id=%s""",
                (binding, scope, number),
            )
            audit(conn, user["id"], "number.bound", scope=scope, target=number)
        return {
            "id": str(number),
            "version": version + 1,
            "enabled": True,
            "release_id": str(release),
            "binding_id": str(binding),
        }

    def deactivate(self, token, scope, number, version):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            locked_number(conn, scope, number, version)
            conn.execute(
                "UPDATE phone_numbers SET enabled=false,version=version+1,updated_at=now() WHERE scope_id=%s AND id=%s",
                (scope, number),
            )
            audit(conn, user["id"], "number.deactivated", scope=scope, target=number)
        return {"id": str(number), "version": version + 1, "enabled": False}
