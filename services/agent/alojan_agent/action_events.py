"""Bounded projection of pinned final events; invoked inside the summary transaction."""

import uuid

from psycopg.types.json import Jsonb

from alojan_contracts.actions import ActionAuthorization
from alojan_contracts.delivery import project
from alojan_contracts.action_conditions import matches


def enqueue(c, job, event):
    manifest = c.execute(
        "SELECT manifest FROM agent_releases WHERE scope_id=%s AND id=%s",
        (job.scope_id, job.release_id),
    ).fetchone()[0]
    if not manifest.get("action_grant"):
        return
    grant = ActionAuthorization.model_validate(manifest["action_grant"])
    if (grant.review.scope_id, grant.review.profile_id) != (job.scope_id, event["profile_id"]):
        raise ValueError("action ownership mismatch")
    eligible = [a for a in grant.review.actions if matches(a.condition, event)]
    if not eligible:
        return
    for action in eligible:
        c.execute(
            """INSERT INTO action_jobs(id,scope_id,call_id,release_id,profile_id,grant_id,
                connection_id,alias,action,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                uuid.uuid5(job.call_id, "call.finalized.v1:" + action.alias),
                job.scope_id,
                job.call_id,
                job.release_id,
                grant.review.profile_id,
                grant.id,
                action.connection_id,
                action.alias,
                Jsonb(action.model_dump()),
                Jsonb(project(action, event)),
            ),
        )
    c.execute(
        "INSERT INTO action_dispatch_scopes(scope_id) VALUES(%s) ON CONFLICT DO NOTHING",
        (job.scope_id,),
    )
