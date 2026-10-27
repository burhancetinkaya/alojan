"""Explicit owner consent for immutable post-call destinations and output fields."""

import re
import uuid

from psycopg.types.json import Jsonb
from alojan_contracts.actions import ActionReview, ActionAuthorization
from alojan_contracts.http_actions import ReviewedHTTPAction, synthetic_preview

from alojan.auth import AuthError, audit
from alojan.profiles import locked_draft, validate_output_tools
from alojan_contracts.outputs import selected_outputs, output_tools
from alojan.telegram_connections import action_connections


def review_actions(conn, scope, profile, draft):
    if not draft.post_call_actions:
        raise AuthError("no_post_call_actions", 409)
    targets = action_connections(conn, scope, draft.post_call_actions)
    if draft.outputs:
        validate_output_tools(conn, scope, draft)
    actions = []
    for action in draft.post_call_actions:
        item = action.model_dump() | targets[action.connection_id]
        definitions = selected_outputs(draft.outputs, action.fields)
        if definitions:
            item.update(
                outputs=[d.model_dump() for d in definitions],
                output_tools=output_tools(definitions, draft.mcp_tools),
            )
        actions.append(item)
    try:
        review = ActionReview(
            schema_version=6
            if any(a.condition in ("no_answer", "interrupted") for a in draft.post_call_actions)
            else 5
            if any(getattr(a, "transcript_policy", None) for a in draft.post_call_actions)
            else 4
            if any(a.condition != "answered" for a in draft.post_call_actions)
            else 3
            if any(a.get("outputs") for a in actions)
            else 2
            if any(a.adapter == "http_request.v1" for a in draft.post_call_actions)
            else 1,
            scope_id=str(scope),
            profile_id=str(profile),
            actions=actions,
        )
        # Target metadata and URL encoding can exceed bounds even for a valid draft.
        for action in review.actions:
            if isinstance(action, ReviewedHTTPAction):
                synthetic_preview(action)
        return review
    except ValueError:
        raise AuthError("invalid_action_intent", 400) from None


def live_grant(conn, scope, profile, *, reference=None, digest=None):
    row = conn.execute(
        """SELECT g.id,g.review,g.review_digest FROM action_grants g
        JOIN users u ON u.id=g.granted_by AND u.enabled
        JOIN workspace_memberships m ON m.scope_id=g.scope_id AND m.user_id=g.granted_by AND m.role='owner'
        WHERE g.scope_id=%s AND g.profile_id=%s AND g.enabled
        AND (%s::uuid IS NULL OR g.id=%s) AND (%s::text IS NULL OR g.review_digest=%s)
        FOR SHARE OF g""",
        (scope, profile, reference, reference, digest, digest),
    ).fetchone()
    if not row:
        raise AuthError("action_grant_required", 409)
    try:
        authorization = ActionAuthorization(id=str(row[0]), review=row[1])
        if authorization.review.digest() != row[2]:
            raise ValueError()
    except ValueError:
        raise AuthError("invalid_action_grant", 409) from None
    return authorization


def publication_grant(conn, scope, profile, draft, *, previous=None):
    if not draft.post_call_actions:
        if previous is not None:
            raise AuthError("invalid_action_grant", 409)
        return None
    review = review_actions(conn, scope, profile, draft)
    if previous is not None:
        try:
            previous = ActionAuthorization.model_validate(previous)
        except ValueError:
            raise AuthError("invalid_action_grant", 409) from None
        if previous.review != review:
            raise AuthError("invalid_action_grant", 409)
    authorization = live_grant(
        conn,
        scope,
        profile,
        reference=previous.id if previous else None,
        digest=review.digest(),
    )
    if authorization.review != review:
        raise AuthError("invalid_action_grant", 409)
    return authorization.model_dump()


class ActionGrants:
    def __init__(self, accounts):
        self.accounts = accounts

    def review(self, token, scope, profile):
        with self.accounts.workspace(token, scope) as (conn, _):
            version, draft = locked_draft(conn, scope, profile)
            review = review_actions(conn, scope, profile, draft)
        return {
            "draft_version": version,
            "review_digest": review.digest(),
            "review": review.model_dump(),
            "delivery_available": True,
            "synthetic_previews": {
                a.alias: synthetic_preview(a)
                for a in review.actions
                if isinstance(a, ReviewedHTTPAction)
            },
        }

    def authorize(self, token, scope, profile, body):
        if (
            body.keys() != {"draft_version", "review_digest"}
            or type(body["draft_version"]) is not int
            or not 1 <= body["draft_version"] <= 999999999
            or not isinstance(body["review_digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", body["review_digest"])
        ):
            raise AuthError("invalid_action_authorization", 400)
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            version, draft = locked_draft(conn, scope, profile)
            if version != body["draft_version"]:
                raise AuthError("stale_version", 412)
            review = review_actions(conn, scope, profile, draft)
            if review.digest() != body["review_digest"]:
                raise AuthError("stale_action_review", 409)
            existing = conn.execute(
                "SELECT id FROM action_grants WHERE scope_id=%s AND profile_id=%s AND review_digest=%s AND enabled",
                (scope, profile, review.digest()),
            ).fetchone()
            if existing:
                reference = live_grant(conn, scope, profile, reference=existing[0]).id
            else:
                if (
                    conn.execute(
                        "SELECT count(*) FROM action_grants WHERE scope_id=%s AND profile_id=%s",
                        (scope, profile),
                    ).fetchone()[0]
                    >= 1000
                ):
                    raise AuthError("action_grant_limit", 409)
                reference = uuid.uuid4()
                conn.execute(
                    """INSERT INTO action_grants(id,scope_id,profile_id,review,review_digest,granted_by)
                    VALUES(%s,%s,%s,%s,%s,%s)""",
                    (
                        reference,
                        scope,
                        profile,
                        Jsonb(review.model_dump()),
                        review.digest(),
                        user["id"],
                    ),
                )
                audit(conn, user["id"], "action.authorized", scope=scope, target=reference)
        return {"id": str(reference), "review_digest": review.digest(), "enabled": True}

    def list(self, token, scope, profile):
        with self.accounts.workspace(token, scope) as (conn, _):
            locked_draft(conn, scope, profile)
            rows = conn.execute(
                "SELECT id,review_digest,enabled FROM action_grants WHERE scope_id=%s AND profile_id=%s ORDER BY created_at DESC,id LIMIT 1000",
                (scope, profile),
            ).fetchall()
        return [dict(id=str(r[0]), review_digest=r[1], enabled=r[2]) for r in rows]

    def revoke(self, token, scope, profile, reference):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if not conn.execute(
                "UPDATE action_grants SET enabled=false WHERE scope_id=%s AND profile_id=%s AND id=%s RETURNING id",
                (scope, profile, reference),
            ).fetchone():
                raise AuthError("not_found", 404)
            audit(conn, user["id"], "action.revoked", scope=scope, target=reference)
        return {"status": "revoked"}
