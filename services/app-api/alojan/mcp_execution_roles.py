"""Private provisioning of MCP permission refresh and execution-journal privileges."""

import argparse
import os

from psycopg import sql

from alojan.auth import connection
from alojan.roles import dedicated_role


def grant_execution(dsn, role):
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role, mcp=True)
        grants = {
            "mcp_oauth_credentials": "SELECT(connection_id,scope_id,authorized_by,access_ciphertext,expires_at,status)",
            "recipient_scopes": "SELECT(id,enabled)",
            "users": "SELECT(id,enabled)",
            "workspace_memberships": "SELECT(scope_id,user_id,role)",
            "mcp_connections": "SELECT",
            "mcp_discovery_jobs": "SELECT",
            "mcp_tool_reviews": "SELECT",
            "mcp_tool_grants": "SELECT",
            "agent_releases": "SELECT(id,scope_id,mcp_grant_id)",
            "call_route_snapshots": "SELECT(call_id,scope_id,profile_id,release_id,manifest_digest)",
            "calls": "SELECT(id,status,answered_at,ended_at)",
            "mcp_tool_executions": "SELECT, INSERT(id,scope_id,call_id,release_id,ordinal,turn,alias), UPDATE(status,failure_code,output,completed_at)",
        }
        for table, privileges in grants.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(privileges), sql.Identifier(schema), sql.Identifier(table), target
                )
            )
        for table in grants.keys() - {"mcp_tool_executions"}:
            for privilege in ("INSERT", "UPDATE", "DELETE"):
                check = (
                    "has_table_privilege" if privilege == "DELETE" else "has_any_column_privilege"
                )
                if conn.execute(
                    f"SELECT {check}(%s,%s,%s)",
                    (role, sql.Identifier(schema, table).as_string(conn), privilege),
                ).fetchone()[0]:
                    raise ValueError("MCP executor can change authorization or call state")
        if conn.execute(
            "SELECT has_column_privilege(%s,'mcp_oauth_credentials','refresh_ciphertext','SELECT')",
            (role,),
        ).fetchone()[0]:
            raise ValueError("MCP executor must not read refresh tokens")
        for table in (
            "mcp_oauth_flows",
            "auth_sessions",
            "utterances",
            "notes",
            "action_grants",
            "action_jobs",
        ):
            if conn.execute(
                "SELECT has_any_column_privilege(%s,%s,'SELECT,INSERT,UPDATE') OR has_table_privilege(%s,%s,'DELETE,TRUNCATE,TRIGGER')",
                (
                    role,
                    sql.Identifier(schema, table).as_string(conn),
                    role,
                    sql.Identifier(schema, table).as_string(conn),
                ),
            ).fetchone()[0]:
                raise ValueError("MCP executor has unrelated privileges")
        for table, column in (("users", "password_hash"), ("calls", "from_number_e164")):
            if conn.execute(
                "SELECT has_column_privilege(%s,%s,%s,'SELECT')", (role, table, column)
            ).fetchone()[0]:
                raise ValueError("MCP executor can read private account/caller fields")
        for column in ("status", "failure_code", "output", "completed_at", "started_at"):
            if conn.execute(
                "SELECT has_column_privilege(%s,'mcp_tool_executions',%s,'INSERT')", (role, column)
            ).fetchone()[0]:
                raise ValueError("MCP executor can forge terminal inserts")
        for column in (
            "id",
            "scope_id",
            "call_id",
            "release_id",
            "ordinal",
            "turn",
            "alias",
            "started_at",
        ):
            if conn.execute(
                "SELECT has_column_privilege(%s,'mcp_tool_executions',%s,'UPDATE')", (role, column)
            ).fetchone()[0]:
                raise ValueError("MCP executor can change execution identity")
        if conn.execute(
            "SELECT has_table_privilege(%s,'mcp_tool_executions','DELETE')", (role,)
        ).fetchone()[0]:
            raise ValueError("MCP executor can delete evidence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True)
    grant_execution(os.environ["ALOJAN_DATABASE_URL"], parser.parse_args().role)
