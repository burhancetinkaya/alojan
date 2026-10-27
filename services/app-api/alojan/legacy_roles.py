"""Operator-only compatibility boundary for the preserved pre-platform rollback image."""

from psycopg import sql

from alojan.auth import connection
from alojan.roles import dedicated_role


def grant_legacy_rollback(dsn, role):
    """Permit legacy records only, even when the old consumer omits a scope filter."""
    grants = {
        "schema_migrations": {"SELECT": None},
        "notification_channels": {"SELECT": None},
        # Invoker-rights ownership triggers need these columns; no numbers/manifests are exposed.
        "call_route_snapshots": {"SELECT": ("call_id", "scope_id", "release_id")},
        "calls": {
            "SELECT": None,
            "INSERT": None,
            "UPDATE": (
                "status",
                "answered_at",
                "ended_at",
                "duration_ms",
                "hangup_reason",
                "failure_code",
            ),
        },
        "utterances": {"SELECT": None, "INSERT": None},
        "notes": {"SELECT": None, "INSERT": None, "UPDATE": ("confirmed",)},
        "call_events": {"INSERT": None},
        "call_summaries": {
            "SELECT": None,
            "INSERT": None,
            "UPDATE": (
                "detail_jsonb",
                "summary",
                "caller_name",
                "subject",
                "urgency",
                "requested_action",
                "confirmation_status",
            ),
        },
        "summary_jobs": {
            "SELECT": None,
            "INSERT": None,
            "UPDATE": ("status", "attempts", "failure_code"),
        },
        "notification_outbox": {
            "SELECT": None,
            "INSERT": None,
            "UPDATE": (
                "retry_count",
                "last_error",
                "next_attempt_at",
                "failed_at",
                "delivered_at",
                "provider_message_id",
                "payload_jsonb",
            ),
        },
    }
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role)
        if conn.execute("SELECT has_schema_privilege(%s,%s,'CREATE')", (role, schema)).fetchone()[
            0
        ]:
            raise ValueError("Rollback role must not create schema objects")
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
        for table, permissions in grants.items():
            relation = sql.Identifier(schema, table)
            for command, columns in permissions.items():
                permission = sql.SQL(command)
                if columns is not None:
                    permission += sql.SQL(" ({})").format(
                        sql.SQL(",").join(map(sql.Identifier, columns))
                    )
                conn.execute(sql.SQL("GRANT {} ON {} TO {}").format(permission, relation, target))
            if table in {"schema_migrations", "notification_channels"}:
                continue
            forced = conn.execute(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=%s::regclass",
                (relation.as_string(conn),),
            ).fetchone()[0]
            if not forced:
                raise ValueError("Rollback requires forced record isolation")
            if table == "call_route_snapshots":
                predicate = sql.SQL("true")
                suffix = "directory"
            else:
                key = "id" if table == "calls" else "call_id"
                predicate = sql.SQL("NOT EXISTS (SELECT 1 FROM {} s WHERE s.call_id={}.{})").format(
                    sql.Identifier(schema, "call_route_snapshots"),
                    sql.Identifier(table),
                    sql.Identifier(key),
                )
                if table == "summary_jobs":
                    predicate += sql.SQL(" AND scope_id IS NULL AND release_id IS NULL")
                suffix = "records"
            # Restrictive policy also applies if a caller forges the workspace GUC or another
            # permissive policy is present. Do not rely on a short-circuited OR predicate.
            for mode in ("PERMISSIVE", "RESTRICTIVE"):
                name = sql.Identifier(f"legacy_{suffix}_{mode.lower()}_{oid}")
                conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(name, relation))
                conn.execute(
                    sql.SQL("CREATE POLICY {} ON {} AS {} TO {} USING ({}) WITH CHECK ({})").format(
                        name, relation, sql.SQL(mode), target, predicate, predicate
                    )
                )

        # Reject previous or PUBLIC rights outside the exact allowlist, including column grants.
        for table, column, command in conn.execute(
            "SELECT c.relname,a.attname,p.command FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped "
            "CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('REFERENCES')) p(command) "
            "WHERE n.nspname=%s AND c.relkind IN ('r','p','v','m','f') "
            "AND has_column_privilege(%s,c.oid,a.attnum,p.command)",
            (schema, role),
        ):
            allowed = grants.get(table, {})
            if command not in allowed or (
                allowed[command] is not None and column not in allowed[command]
            ):
                raise ValueError("Rollback role has unexpected column privileges")
        if conn.execute(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND c.relkind IN ('r','p','v','m','f') "
            "AND has_table_privilege(%s,c.oid,'DELETE,TRUNCATE,TRIGGER') LIMIT 1",
            (schema, role),
        ).fetchone():
            raise ValueError("Rollback role has unexpected table privileges")
        if conn.execute(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND CASE WHEN c.relkind='S' "
            "THEN has_sequence_privilege(%s,c.oid,'USAGE,SELECT,UPDATE') ELSE false END LIMIT 1",
            (schema, role),
        ).fetchone():
            raise ValueError("Rollback role has unexpected sequence privileges")
