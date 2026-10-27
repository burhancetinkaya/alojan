"""Private provisioning of the discovery-only worker identity."""

import argparse
import os

from psycopg import sql
from alojan.auth import connection
from alojan.roles import dedicated_role


def grant_discovery(dsn, role):
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role, mcp=True)
        for table, permissions in {
            "mcp_oauth_credentials": "SELECT, UPDATE(status,claim_token,lease_until,access_ciphertext,refresh_ciphertext,expires_at,refresh_after,generation)",
            "recipient_scopes": "SELECT(id,enabled)",
            "workspace_memberships": "SELECT(scope_id,user_id,role)",
            "users": "SELECT(id,enabled)",
            "mcp_connections": "SELECT, UPDATE(id)",
            "mcp_discovery_jobs": "SELECT, UPDATE(status,claim_token,lease_until,failure_code,manifest,completed_at)",
        }.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(permissions), sql.Identifier(schema), sql.Identifier(table), target
                )
            )
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
        for command in ("SELECT", "UPDATE"):
            name = sql.Identifier("mcp_directory_" + command.lower() + "_" + str(oid))
            relation = sql.Identifier(schema, "mcp_discovery_jobs")
            clause = "USING (true)" + (" WITH CHECK (true)" if command == "UPDATE" else "")
            conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(name, relation))
            conn.execute(
                sql.SQL("CREATE POLICY {} ON {} FOR {} TO {} {}").format(
                    name, relation, sql.SQL(command), target, sql.SQL(clause)
                )
            )
        for command in ("SELECT", "UPDATE"):
            name = sql.Identifier("mcp_oauth_directory_" + command.lower() + "_" + str(oid))
            relation = sql.Identifier(schema, "mcp_oauth_credentials")
            clause = "USING (true)" + (" WITH CHECK (true)" if command == "UPDATE" else "")
            conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(name, relation))
            conn.execute(
                sql.SQL("CREATE POLICY {} ON {} FOR {} TO {} {}").format(
                    name, relation, sql.SQL(command), target, sql.SQL(clause)
                )
            )
        for table, permission in (
            ("mcp_oauth_flows", "SELECT"),
            ("mcp_oauth_credentials", "INSERT"),
            ("mcp_oauth_credentials", "DELETE"),
            ("mcp_tool_reviews", "DELETE"),
            ("mcp_tool_grants", "DELETE"),
            ("mcp_tool_reviews", "INSERT"),
            ("mcp_tool_reviews", "UPDATE"),
            ("mcp_tool_grants", "INSERT"),
            ("mcp_tool_grants", "UPDATE"),
            ("mcp_connections", "INSERT"),
            ("mcp_connections", "DELETE"),
            ("mcp_discovery_jobs", "INSERT"),
            ("mcp_discovery_jobs", "DELETE"),
            ("users", "UPDATE"),
            ("auth_sessions", "SELECT"),
            ("calls", "SELECT"),
            ("recipient_scopes", "UPDATE"),
            ("workspace_memberships", "UPDATE"),
            ("utterances", "SELECT"),
            ("notes", "SELECT"),
            ("agent_releases", "UPDATE"),
            ("action_grants", "INSERT"),
            ("action_jobs", "UPDATE"),
        ):
            check = "has_table_privilege" if permission == "DELETE" else "has_any_column_privilege"
            if conn.execute(
                f"SELECT {check}(%s,%s,%s)",
                (role, sql.Identifier(schema, table).as_string(conn), permission),
            ).fetchone()[0]:
                raise ValueError("MCP worker has unexpected privileges")
        if conn.execute(
            "SELECT has_column_privilege(%s,'users','password_hash','SELECT')", (role,)
        ).fetchone()[0]:
            raise ValueError("MCP worker must not read passwords")
        for table, columns in {
            "mcp_oauth_credentials": (
                "connection_id",
                "scope_id",
                "authorized_by",
                "provider",
                "created_at",
            ),
            "mcp_connections": (
                "scope_id",
                "label",
                "endpoint",
                "auth_type",
                "ciphertext",
                "enabled",
                "created_at",
            ),
            "mcp_discovery_jobs": ("id", "scope_id", "connection_id", "created_at"),
        }.items():
            for column in columns:
                if conn.execute(
                    "SELECT has_column_privilege(%s,%s,%s,'UPDATE')",
                    (role, sql.Identifier(schema, table).as_string(conn), column),
                ).fetchone()[0]:
                    raise ValueError("MCP worker can change connection identity")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True)
    grant_discovery(os.environ["ALOJAN_DATABASE_URL"], parser.parse_args().role)
