"""Commit a scoped HTTP mutation and its retry result in the same transaction."""

import hashlib
import json
import uuid

from psycopg.types.json import Jsonb

from alojan.auth import AuthError, _management_transaction


def execute(accounts, credential, request, body, handle):
    with accounts.workspace(credential, credential.scope):
        pass
    try:
        key = uuid.UUID(request.headers.get("idempotency-key", ""))
    except (ValueError, TypeError):
        raise AuthError("operation_key_required", 428) from None
    digest = hashlib.sha256(
        json.dumps(
            {
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "version": request.headers.get("if-match"),
                "body": body,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).digest()
    with accounts.workspace(credential, credential.scope) as (conn, user):
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,714206))",
            (f"{user['id']}:{credential.scope}:{key}",),
        )
        row = conn.execute(
            """SELECT request_digest,result,status,created_at>=now()-interval '7 days'
            FROM management_operations
            WHERE user_id=%s AND scope_id=%s AND operation_key=%s""",
            (user["id"], credential.scope, key),
        ).fetchone()
        if row:
            if bytes(row[0]) != digest:
                raise AuthError("operation_key_conflict", 409)
            if row[1] is None or not row[3]:
                raise AuthError("operation_result_expired", 410)
            return row[1], None, row[2]
        # Retain retry identities permanently; lazily discard bounded batches of old payloads.
        conn.execute(
            """UPDATE management_operations SET result=NULL WHERE user_id=%s AND scope_id=%s
            AND operation_key IN (SELECT operation_key FROM management_operations
                WHERE user_id=%s AND scope_id=%s AND created_at<now()-interval '7 days'
                AND result IS NOT NULL ORDER BY created_at LIMIT 100)""",
            (user["id"], credential.scope, user["id"], credential.scope),
        )
        marker = _management_transaction.set((accounts.dsn, conn))
        try:
            payload, cookie, status = handle()
        finally:
            _management_transaction.reset(marker)
        if cookie is not None or not 200 <= status < 300:
            raise AuthError("invalid_management_result", 500)
        conn.execute(
            """INSERT INTO management_operations
            (user_id,scope_id,operation_key,request_digest,result,status) VALUES (%s,%s,%s,%s,%s,%s)""",
            (user["id"], credential.scope, key, digest, Jsonb(payload), status),
        )
        return payload, None, status
