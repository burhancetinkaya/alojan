"""Private operator record of already established carrier ownership/routing evidence."""

import argparse
import os
import re
import uuid

import psycopg

from alojan.auth import AuthError, audit, connection
from alojan.numbers import locked_number


def evidence(value, length=160):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0," + str(length - 1) + "}", value
    ):
        raise ValueError("Use an opaque evidence reference, not credentials or a transcript")
    return value


def decide(dsn, scope, number, version, operator, *, ownership=None, routing=None, reason=None):
    scope, number = uuid.UUID(str(scope)), uuid.UUID(str(number))
    operator = evidence(operator, 80)
    decision = "revoked" if reason is not None else "verified"
    if decision == "verified":
        ownership, routing = evidence(ownership), evidence(routing)
    else:
        reason = evidence(reason)
    try:
        with connection(dsn) as conn:
            authority = conn.execute(
                "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user"
            ).fetchone()
            if not authority or not authority[0]:
                raise AuthError("operator_authority_required", 403)
            conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))
            did = conn.execute(
                "SELECT e164 FROM phone_numbers WHERE scope_id=%s AND id=%s", (scope, number)
            ).fetchone()
            if not did:
                raise AuthError("not_found", 404)
            # Serialize ownership decisions across competing claims, without reserving guesses.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,714207))", did)
            locked_number(conn, scope, number, version)
            if decision == "verified":
                if not conn.execute(
                    "SELECT 1 FROM recipient_scopes WHERE id=%s AND enabled FOR SHARE", (scope,)
                ).fetchone():
                    raise AuthError("workspace_disabled", 409)
                active = conn.execute(
                    """SELECT 1 FROM call_route_snapshots s JOIN calls c ON c.id=s.call_id
                    WHERE s.called_e164=%s AND c.ended_at IS NULL LIMIT 1""",
                    did,
                ).fetchone()
                if active:
                    raise AuthError("number_calls_not_drained", 409)
            verification = uuid.uuid4()
            conn.execute(
                """INSERT INTO number_verifications(id,scope_id,number_id,operator_ref,decision,
                ownership_evidence_ref,routing_evidence_ref,reason_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (verification, scope, number, operator, decision, ownership, routing, reason),
            )
            conn.execute(
                """UPDATE phone_numbers SET status=%s,verification_id=%s,enabled=false,
                version=version+1,updated_at=now() WHERE scope_id=%s AND id=%s""",
                (decision, verification, scope, number),
            )
            audit(conn, None, "number." + decision, scope=scope, target=number)
    except psycopg.errors.UniqueViolation:
        raise AuthError("number_ownership_conflict", 409) from None
    return {"id": str(number), "version": version + 1, "status": decision, "enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["verify", "revoke"])
    parser.add_argument("--scope", type=uuid.UUID, required=True)
    parser.add_argument("--number", type=uuid.UUID, required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--ownership-evidence")
    parser.add_argument("--routing-evidence")
    parser.add_argument("--reason")
    args = parser.parse_args()
    if (
        args.operation == "verify"
        and (not args.ownership_evidence or not args.routing_evidence or args.reason)
    ) or (
        args.operation == "revoke"
        and (not args.reason or args.ownership_evidence or args.routing_evidence)
    ):
        parser.error("Verify needs both evidence references; revoke needs only a reason reference")
    try:
        decide(
            os.environ["ALOJAN_DATABASE_URL"],
            args.scope,
            args.number,
            args.version,
            args.operator,
            ownership=args.ownership_evidence,
            routing=args.routing_evidence,
            reason=args.reason,
        )
    except (ValueError, AuthError, psycopg.Error):
        raise SystemExit(
            "Number decision failed; check evidence, version, ownership and drained calls"
        ) from None
    print(
        "Number decision recorded; routing remains disabled until an owner binds a ready release."
    )


if __name__ == "__main__":
    main()
