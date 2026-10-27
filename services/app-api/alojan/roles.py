"""Provision least-privilege management grants using private migration credentials."""

import argparse
import os

from psycopg import Error, sql

from alojan.auth import connection
from alojan_contracts.routing import node_identifier


def dedicated_role(conn, role, *, secrets=False, telegram=False, mcp=False, http=False):
    account = conn.execute(
        """SELECT oid,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
        FROM pg_roles WHERE rolname=%s""",
        (role,),
    ).fetchone()
    if not account or any(account[1:]):
        raise ValueError("Use an existing unprivileged dedicated role")
    if conn.execute("SELECT 1 FROM pg_auth_members WHERE member=%s", (account[0],)).fetchone():
        raise ValueError("Management role must not inherit or switch to other roles")
    if conn.execute("SELECT 1 FROM pg_class WHERE relowner=%s LIMIT 1", (account[0],)).fetchone():
        raise ValueError("Management role must not own database objects")
    if conn.execute("SELECT 1 FROM pg_database WHERE datdba=%s LIMIT 1", (account[0],)).fetchone():
        raise ValueError("Management role must not own databases")
    schema = conn.execute("SELECT current_schema()").fetchone()[0]
    if conn.execute(
        "SELECT 1 FROM pg_namespace WHERE nspowner=%s LIMIT 1", (account[0],)
    ).fetchone():
        raise ValueError("Management role must not own schemas")
    if (
        not secrets
        and conn.execute(
            "SELECT has_column_privilege(%s,'provider_connections','ciphertext','SELECT')", (role,)
        ).fetchone()[0]
    ):
        raise ValueError("Dedicated role must not read provider credentials")
    if (
        not telegram
        and conn.execute(
            "SELECT has_column_privilege(%s,'telegram_connections','ciphertext','SELECT')", (role,)
        ).fetchone()[0]
    ):
        raise ValueError("Dedicated role must not read Telegram credentials")
    if (
        not mcp
        and conn.execute(
            "SELECT has_column_privilege(%s,'mcp_connections','ciphertext','SELECT')", (role,)
        ).fetchone()[0]
    ):
        raise ValueError("Dedicated role must not read MCP credentials")
    if not mcp:
        for column in ("access_ciphertext", "refresh_ciphertext"):
            if conn.execute(
                "SELECT has_column_privilege(%s,'mcp_oauth_credentials',%s,'SELECT')",
                (role, column),
            ).fetchone()[0]:
                raise ValueError("Dedicated role must not read OAuth credentials")
    if (
        not http
        and conn.execute(
            "SELECT has_column_privilege(%s,'http_connections','ciphertext','SELECT')", (role,)
        ).fetchone()[0]
    ):
        raise ValueError("Dedicated role must not read HTTP credentials")
    if conn.execute(
        "SELECT has_table_privilege(%s,'http_connections','DELETE,TRUNCATE,TRIGGER')", (role,)
    ).fetchone()[0]:
        raise ValueError("Dedicated role must not destroy HTTP connections")
    target = sql.Identifier(role)
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), target))
    return schema, target


def grant_management(dsn, role):
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role)
        grants = {
            "management_connection_setups": "SELECT, INSERT, UPDATE(connection_id)",
            "management_operations": "SELECT, INSERT, UPDATE(result)",
            "personal_access_tokens": "SELECT, INSERT, UPDATE(revoked_at,last_used_at)",
            "http_connections": "SELECT(id,scope_id,label,endpoint,auth_type,enabled,created_at), INSERT, UPDATE(enabled)",
            "mcp_oauth_flows": "SELECT, INSERT, UPDATE(status,code_hash,connection_id), DELETE",
            "mcp_oauth_credentials": "SELECT(connection_id,scope_id,authorized_by,status,expires_at), INSERT",
            "mcp_tool_executions": "SELECT(id,scope_id,call_id,release_id,ordinal,turn,alias,status,failure_code,started_at,completed_at)",
            "mcp_tool_reviews": "SELECT, UPDATE(id)",
            "mcp_tool_grants": "SELECT, INSERT, UPDATE(enabled)",
            "mcp_connections": "SELECT(id,scope_id,label,endpoint,auth_type,enabled,created_at), INSERT, UPDATE(enabled)",
            "mcp_discovery_jobs": "SELECT, INSERT(id,scope_id,connection_id)",
            "call_latency": "SELECT",
            "utterances": "SELECT(id,call_id,speaker,text,is_final,created_at,audio_sent_start_ms,audio_sent_end_ms,source_generation_id)",
            "calls": "SELECT(id,status,started_at,answered_at,ended_at,duration_ms,hangup_reason,failure_code,from_number_e164,from_number_source)",
            "call_route_snapshots": "SELECT(call_id,scope_id,profile_id,release_id,called_e164,created_at)",
            "call_finalizations": "SELECT(call_id,scope_id,summary_status,payload)",
            "summary_jobs": "SELECT(call_id,status)",
            "notes": "SELECT(call_id,text,confirmed,note_version)",
            "voice_preparation_jobs": "SELECT, INSERT(id,scope_id,profile_id,preparation_id,attempt)",
            "action_grants": "SELECT, INSERT, UPDATE(enabled)",
            # PostgreSQL row locks need UPDATE on a column; immutable id cannot actually change.
            "action_jobs": "SELECT, UPDATE(id)",
            "action_retry_requests": "SELECT, INSERT(id,scope_id,profile_id,job_id,generation,requested_by,review,review_digest)",
            "telegram_connections": "SELECT(id,scope_id,label,chat_id,enabled,created_at), INSERT, UPDATE(enabled)",
            "provider_connections": "SELECT(id,scope_id,provider,label,enabled,created_at), INSERT, UPDATE(enabled)",
            "users": "SELECT, INSERT, UPDATE(password_hash,password_version)",
            "recipient_scopes": "SELECT, INSERT, UPDATE(display_name)",
            "workspace_memberships": "SELECT, INSERT, UPDATE(created_at)",
            "auth_sessions": "SELECT, INSERT, UPDATE, DELETE",
            "auth_rate_limits": "SELECT, INSERT, UPDATE, DELETE",
            "workspace_invitations": "SELECT, DELETE",
            "management_audit": "INSERT",
            "assistant_profiles": "SELECT, INSERT, UPDATE(label)",
            "agent_drafts": "SELECT, INSERT, UPDATE(content,version,updated_by,updated_at)",
            "assistant_profile_revisions": "SELECT, INSERT",
            "engine_presets": "SELECT",
            "model_catalog": "SELECT",
            # PostgreSQL row-share locks require UPDATE on at least one column.
            "model_catalog_status": "SELECT, UPDATE(updated_at)",
            "agent_preparations": "SELECT, INSERT",
            "prepared_voice_assets": "SELECT",
            "agent_releases": "SELECT, INSERT",
            "agent_publications": "SELECT, INSERT, UPDATE(release_id,version,node_id)",
            "schema_migrations": "SELECT",
            "phone_numbers": "SELECT, INSERT, UPDATE(active_binding_id,enabled,version,updated_at)",
            "number_bindings": "SELECT, INSERT",
            "release_readiness": "SELECT, UPDATE(checked_at)",
        }
        for table, permissions in grants.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(permissions),
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    target,
                )
            )
        conn.execute(
            sql.SQL("GRANT USAGE ON SEQUENCE {}.management_audit_id_seq TO {}").format(
                sql.Identifier(schema),
                target,
            )
        )
        # Detect inherited/PUBLIC or previously granted privileges before accepting the role.
        for table, privilege in (
            ("mcp_tool_executions", "INSERT"),
            ("mcp_tool_executions", "UPDATE"),
            ("mcp_tool_executions", "DELETE"),
            ("mcp_tool_reviews", "DELETE"),
            ("number_verifications", "INSERT"),
            ("release_readiness", "INSERT"),
            ("call_route_snapshots", "SELECT"),
            ("model_catalog", "INSERT"),
            ("model_catalog_status", "INSERT"),
            ("engine_presets", "INSERT"),
            ("prepared_voice_assets", "INSERT"),
            ("agent_releases", "UPDATE"),
            ("calls", "SELECT"),
            ("system_settings", "UPDATE"),
        ):
            relation = sql.Identifier(schema, table).as_string(conn)
            check = (
                "has_any_column_privilege"
                if table == "mcp_tool_executions" and privilege in {"INSERT", "UPDATE"}
                else "has_table_privilege"
            )
            if conn.execute(f"SELECT {check}(%s,%s,%s)", (role, relation, privilege)).fetchone()[0]:
                raise ValueError("Management role has unexpected existing privileges")
        for table, column in (
            *(
                ("action_jobs", column)
                for column in (
                    "status",
                    "attempts",
                    "claim_token",
                    "lease_until",
                    "next_attempt_at",
                    "failure_code",
                    "remote_message_id",
                    "updated_at",
                    "retry_generation",
                )
            ),
            ("voice_preparation_jobs", "status"),
            ("mcp_discovery_jobs", "status"),
            ("mcp_discovery_jobs", "manifest"),
            ("voice_preparation_jobs", "failure_code"),
            ("action_retry_requests", "consumed_at"),
            ("phone_numbers", "status"),
            ("phone_numbers", "verification_id"),
            ("release_readiness", "ready"),
            ("release_readiness", "consumer_id"),
            ("release_readiness", "valid_until"),
            ("release_readiness", "acknowledged_at"),
            ("model_catalog_status", "enabled"),
            ("assistant_profiles", "enabled"),
            ("users", "enabled"),
            ("workspace_memberships", "role"),
        ):
            relation = sql.Identifier(schema, table).as_string(conn)
            if conn.execute(
                "SELECT has_column_privilege(%s,%s,%s,'UPDATE')", (role, relation, column)
            ).fetchone()[0]:
                raise ValueError("Management role can change operator-controlled state")
        for column in (
            "id",
            "scope_id",
            "connection_id",
            "discovery_id",
            "tool_name",
            "tool_digest",
            "tool",
            "capability",
            "reviewed_by",
            "evidence",
            "enabled",
            "created_at",
        ):
            for privilege in ("INSERT",) if column == "id" else ("INSERT", "UPDATE"):
                if conn.execute(
                    "SELECT has_column_privilege(%s,'mcp_tool_reviews',%s,%s)",
                    (role, column, privilege),
                ).fetchone()[0]:
                    raise ValueError("Management role can forge MCP capability reviews")
        for column in (
            "status",
            "claim_token",
            "lease_until",
            "failure_code",
            "manifest",
            "created_at",
            "completed_at",
        ):
            if conn.execute(
                "SELECT has_column_privilege(%s,'mcp_discovery_jobs',%s,'INSERT')", (role, column)
            ).fetchone()[0]:
                raise ValueError("Management role can forge MCP discovery results")


def grant_routing(dsn, role):
    """Dedicated private admission role; no authentication or notification access."""
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role)
        grants = {
            "phone_numbers": "SELECT, UPDATE(updated_at)",
            "recipient_scopes": "SELECT, UPDATE(created_at)",
            "number_bindings": "SELECT",
            "agent_releases": "SELECT",
            "model_catalog_status": "SELECT, UPDATE(updated_at)",
            "release_readiness": "SELECT, UPDATE(checked_at)",
            "call_route_snapshots": "SELECT, INSERT",
            "summary_jobs": "INSERT",
            "calls": "SELECT(id,sip_call_id,status,from_number_e164,ended_at,started_at), INSERT, UPDATE(status,ended_at,hangup_reason)",
        }
        for table, permissions in grants.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(permissions),
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    target,
                )
            )
        # Admission discovers scope from the verified DID, never from caller input.
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
        for table, predicate in (
            ("phone_numbers", "status='verified'"),
            ("call_route_snapshots", "true"),
            ("calls", "true"),
        ):
            policy = sql.Identifier("routing_directory_" + str(oid))
            relation = sql.Identifier(schema, table)
            conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(policy, relation))
            conn.execute(
                sql.SQL("CREATE POLICY {} ON {} FOR SELECT TO {} USING ({})").format(
                    policy,
                    relation,
                    target,
                    sql.SQL(predicate),
                )
            )
        # Cancellation tombstones precede a scoped route; admission is a trusted private writer.
        for command in ("INSERT", "UPDATE"):
            policy = sql.Identifier("routing_" + command.lower() + "_" + str(oid))
            relation = sql.Identifier(schema, "calls")
            conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(policy, relation))
            clause = (
                "WITH CHECK (true)" if command == "INSERT" else "USING (true) WITH CHECK (true)"
            )
            conn.execute(
                sql.SQL("CREATE POLICY {} ON {} FOR {} TO {} {}").format(
                    policy, relation, sql.SQL(command), target, sql.SQL(clause)
                )
            )
        for table, privilege in (
            ("users", "SELECT"),
            ("number_bindings", "INSERT"),
            ("number_verifications", "INSERT"),
            ("release_readiness", "INSERT"),
            ("notification_outbox", "INSERT"),
        ):
            if conn.execute(
                "SELECT has_table_privilege(%s,%s,%s)",
                (role, sql.Identifier(schema, table).as_string(conn), privilege),
            ).fetchone()[0]:
                raise ValueError("Routing role has unexpected privileges")
        for table, column in (
            *(
                ("action_jobs", column)
                for column in (
                    "status",
                    "attempts",
                    "claim_token",
                    "lease_until",
                    "next_attempt_at",
                    "failure_code",
                    "remote_message_id",
                    "updated_at",
                    "retry_generation",
                )
            ),
            ("action_retry_requests", "consumed_at"),
            ("phone_numbers", "status"),
            ("phone_numbers", "enabled"),
            ("release_readiness", "ready"),
            ("release_readiness", "consumer_id"),
            ("release_readiness", "valid_until"),
            ("release_readiness", "acknowledged_at"),
            ("model_catalog_status", "enabled"),
        ):
            if conn.execute(
                "SELECT has_column_privilege(%s,%s,%s,'UPDATE')",
                (role, sql.Identifier(schema, table).as_string(conn), column),
            ).fetchone()[0]:
                raise ValueError("Routing role can override admission controls")


def grant_call_records(dsn, role, *, summaries=False):
    """Trusted private writers; workspace context comes only from pinned routes/claimed jobs."""
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role)
        grants = (
            {
                "call_route_snapshots": "SELECT",
                "calls": "SELECT, UPDATE(status,answered_at,ended_at,duration_ms,hangup_reason,failure_code)",
                "utterances": "SELECT, INSERT, UPDATE(text)",
                "notes": "SELECT, INSERT, UPDATE(confirmed)",
                "call_events": "INSERT",
                "summary_jobs": "SELECT, INSERT",
                "agent_releases": "SELECT",
            }
            if not summaries
            else {
                "call_route_snapshots": "SELECT",
                "calls": "SELECT",
                "utterances": "SELECT",
                "notes": "SELECT",
                "agent_releases": "SELECT",
                "call_finalizations": "SELECT, INSERT",
                "mcp_tool_executions": "SELECT(scope_id,call_id,release_id,alias,status,ordinal,completed_at,output)",
                "action_jobs": "INSERT",
                "action_dispatch_scopes": "INSERT",
                "call_summaries": "SELECT, INSERT, UPDATE",
                "summary_jobs": "SELECT, UPDATE(status,attempts,failure_code,claim_token,lease_until)",
            }
        )
        for table, permissions in grants.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(permissions), sql.Identifier(schema), sql.Identifier(table), target
                )
            )
        if summaries:
            oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
            for table, command, clause in (
                ("summary_jobs", "SELECT", "USING (scope_id IS NOT NULL)"),
                (
                    "summary_jobs",
                    "UPDATE",
                    "USING (scope_id IS NOT NULL) WITH CHECK (scope_id IS NOT NULL)",
                ),
                ("call_route_snapshots", "SELECT", "USING (true)"),
            ):
                name = sql.Identifier("summary_directory_" + command.lower() + "_" + str(oid))
                relation = sql.Identifier(schema, table)
                conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(name, relation))
                conn.execute(
                    sql.SQL("CREATE POLICY {} ON {} FOR {} TO {} {}").format(
                        name, relation, sql.SQL(command), target, sql.SQL(clause)
                    )
                )
        forbidden = [
            ("users", "SELECT"),
            ("notification_outbox", "INSERT"),
            ("agent_releases", "UPDATE"),
            ("release_readiness", "INSERT"),
            ("phone_numbers", "UPDATE"),
            ("call_route_snapshots", "INSERT"),
        ]
        forbidden += (
            [
                ("calls", "UPDATE"),
                ("notes", "UPDATE"),
                ("notes", "INSERT"),
                ("utterances", "UPDATE"),
                ("utterances", "INSERT"),
                ("summary_jobs", "INSERT"),
            ]
            if summaries
            else [
                ("call_finalizations", "INSERT"),
                ("call_summaries", "INSERT"),
                ("call_summaries", "UPDATE"),
                ("summary_jobs", "UPDATE"),
            ]
        )
        for table, privilege in forbidden:
            if conn.execute(
                "SELECT has_any_column_privilege(%s,%s,%s)",
                (role, sql.Identifier(schema, table).as_string(conn), privilege),
            ).fetchone()[0]:
                raise ValueError("Call worker role has unexpected privileges")


def grant_readiness(dsn, role, node_id):
    """Private consumer writer scoped to one deployment node; no calls or user secrets."""
    node_identifier(node_id)
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role)
        for table, privileges in {
            "agent_releases": "SELECT",
            "recipient_scopes": "SELECT",
            "model_catalog_status": "SELECT",
            "agent_publications": "SELECT(scope_id,release_id,node_id)",
            "phone_numbers": "SELECT(scope_id,active_binding_id,status,enabled)",
            "number_bindings": "SELECT(scope_id,id,release_id,node_id)",
            "release_readiness": "SELECT, INSERT, UPDATE(consumer_id,ready,acknowledged_at,valid_until,checked_at)",
        }.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(privileges), sql.Identifier(schema), sql.Identifier(table), target
                )
            )
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
        for table, predicate in (
            ("agent_publications", sql.SQL("node_id={}").format(sql.Literal(node_id))),
            ("number_bindings", sql.SQL("node_id={}").format(sql.Literal(node_id))),
            ("phone_numbers", sql.SQL("enabled AND status='verified'")),
        ):
            directory = sql.Identifier("readiness_directory_" + str(oid))
            relation = sql.Identifier(schema, table)
            conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(directory, relation))
            conn.execute(
                sql.SQL("CREATE POLICY {} ON {} FOR SELECT TO {} USING ({})").format(
                    directory, relation, target, predicate
                )
            )
        policy = sql.Identifier("readiness_node_" + str(oid))
        relation = sql.Identifier(schema, "release_readiness")
        conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(policy, relation))
        conn.execute(
            sql.SQL("""CREATE POLICY {} ON {} AS RESTRICTIVE TO {}
            USING (node_id={}) WITH CHECK (node_id={})""").format(
                policy, relation, target, sql.Literal(node_id), sql.Literal(node_id)
            )
        )
        for table, privilege in (
            ("users", "SELECT"),
            ("calls", "SELECT"),
            ("notes", "INSERT"),
            ("notification_outbox", "INSERT"),
            ("agent_releases", "INSERT"),
            ("agent_releases", "UPDATE"),
            ("phone_numbers", "UPDATE"),
            ("number_bindings", "INSERT"),
            ("model_catalog_status", "UPDATE"),
            ("recipient_scopes", "UPDATE"),
            ("assistant_profiles", "UPDATE"),
        ):
            if conn.execute(
                "SELECT has_any_column_privilege(%s,%s,%s)",
                (role, sql.Identifier(schema, table).as_string(conn), privilege),
            ).fetchone()[0]:
                raise ValueError("Readiness role has unexpected privileges")


def grant_credentials(dsn, role):
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role, secrets=True)
        for table in ("provider_connections", "recipient_scopes"):
            conn.execute(
                sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(table), target
                )
            )
        for table, privilege in (
            ("users", "SELECT"),
            ("calls", "SELECT"),
            ("agent_releases", "SELECT"),
            ("provider_connections", "INSERT"),
            ("provider_connections", "UPDATE"),
            ("provider_connections", "DELETE"),
            ("recipient_scopes", "UPDATE"),
            ("notification_outbox", "INSERT"),
        ):
            check = "has_table_privilege" if privilege == "DELETE" else "has_any_column_privilege"
            if conn.execute(
                f"SELECT {check}(%s,%s,%s)",
                (role, sql.Identifier(schema, table).as_string(conn), privilege),
            ).fetchone()[0]:
                raise ValueError("Credential reader has unexpected privileges")


def grant_actions(dsn, role):
    """Independent Telegram dispatcher; no provider keys, transcripts or user credentials."""
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role, telegram=True, http=True)
        for table, permissions in {
            "action_jobs": "SELECT, UPDATE(status,attempts,claim_token,lease_until,next_attempt_at,failure_code,remote_message_id,http_status,updated_at,retry_generation)",
            "action_dispatch_scopes": "SELECT, UPDATE(last_claim_at,next_dispatch_at)",
            "action_dispatch_clock": "SELECT, UPDATE(next_dispatch_at)",
            "action_retry_requests": "SELECT, UPDATE(consumed_at)",
            "action_grants": "SELECT",
            "telegram_connections": "SELECT",
            "http_connections": "SELECT",
            "recipient_scopes": "SELECT(id,enabled)",
            "users": "SELECT(id,enabled)",
            "workspace_memberships": "SELECT(scope_id,user_id,role)",
        }.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(permissions), sql.Identifier(schema), sql.Identifier(table), target
                )
            )
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
        for table in ("action_jobs", "action_dispatch_scopes", "action_retry_requests"):
            for command in ("SELECT", "UPDATE"):
                name = sql.Identifier("action_directory_" + command.lower() + "_" + str(oid))
                relation = sql.Identifier(schema, table)
                clause = "USING (true)" + (" WITH CHECK (true)" if command == "UPDATE" else "")
                conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(name, relation))
                conn.execute(
                    sql.SQL("CREATE POLICY {} ON {} FOR {} TO {} {}").format(
                        name, relation, sql.SQL(command), target, sql.SQL(clause)
                    )
                )
        for table, privilege in (
            ("calls", "SELECT"),
            ("utterances", "SELECT"),
            ("notes", "SELECT"),
            ("call_finalizations", "SELECT"),
            ("auth_sessions", "SELECT"),
            ("agent_releases", "UPDATE"),
            ("action_jobs", "INSERT"),
            ("action_retry_requests", "INSERT"),
            ("action_grants", "INSERT"),
            ("action_grants", "UPDATE"),
            ("http_connections", "INSERT"),
            ("http_connections", "UPDATE"),
            ("telegram_connections", "INSERT"),
            ("telegram_connections", "UPDATE"),
            ("recipient_scopes", "UPDATE"),
            ("users", "UPDATE"),
            ("workspace_memberships", "UPDATE"),
            ("notification_outbox", "INSERT"),
        ):
            if conn.execute(
                "SELECT has_any_column_privilege(%s,%s,%s)",
                (role, sql.Identifier(schema, table).as_string(conn), privilege),
            ).fetchone()[0]:
                raise ValueError("Action worker role has unexpected privileges")
        for column in (
            "id",
            "scope_id",
            "profile_id",
            "job_id",
            "generation",
            "requested_by",
            "review",
            "review_digest",
            "created_at",
        ):
            if conn.execute(
                "SELECT has_column_privilege(%s,'action_retry_requests',%s,'UPDATE')",
                (role, column),
            ).fetchone()[0]:
                raise ValueError("Action worker cannot modify retry consent")
        if conn.execute(
            "SELECT has_column_privilege(%s,'users','password_hash','SELECT')", (role,)
        ).fetchone()[0]:
            raise ValueError("Action worker role must not read passwords")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", help="Existing dedicated database role; no password arguments")
    parser.add_argument(
        "--purpose",
        choices=[
            "management",
            "routing",
            "records",
            "summaries",
            "readiness",
            "credentials",
            "actions",
            "legacy-rollback",
        ],
        default="management",
    )
    parser.add_argument("--node-id", help="Required for the private readiness role")
    args = parser.parse_args()
    try:
        if args.purpose == "legacy-rollback":
            from alojan.legacy_roles import grant_legacy_rollback

            grant_legacy_rollback(os.environ["ALOJAN_DATABASE_URL"], args.role)
        elif args.purpose == "actions":
            grant_actions(os.environ["ALOJAN_DATABASE_URL"], args.role)
        elif args.purpose == "credentials":
            grant_credentials(os.environ["ALOJAN_DATABASE_URL"], args.role)
        elif args.purpose == "readiness":
            grant_readiness(os.environ["ALOJAN_DATABASE_URL"], args.role, args.node_id)
        elif args.purpose in {"records", "summaries"}:
            grant_call_records(
                os.environ["ALOJAN_DATABASE_URL"], args.role, summaries=args.purpose == "summaries"
            )
        else:
            grant = grant_management if args.purpose == "management" else grant_routing
            grant(os.environ["ALOJAN_DATABASE_URL"], args.role)
    except (ValueError, Error):
        raise SystemExit(
            "Grant provisioning failed; check dedicated role privileges and database availability"
        ) from None
    print("Database grants applied; no account, credential or number binding changes.")


if __name__ == "__main__":
    main()
