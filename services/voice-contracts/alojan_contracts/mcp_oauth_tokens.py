"""Credential reads outside the turn path; original OAuth owner must remain eligible."""

ACCESS_SQL = """SELECT o.connection_id,o.access_ciphertext,extract(epoch FROM o.expires_at-now())
    FROM mcp_oauth_credentials o
    JOIN mcp_connections c ON (c.scope_id,c.id)=(o.scope_id,o.connection_id) AND c.enabled AND c.auth_type='oauth'
    JOIN recipient_scopes s ON s.id=o.scope_id AND s.enabled
    JOIN users u ON u.id=o.authorized_by AND u.enabled
    JOIN workspace_memberships m ON m.scope_id=o.scope_id AND m.user_id=u.id AND m.role='owner'
    WHERE o.scope_id=%s AND o.connection_id=ANY(%s::uuid[]) AND o.status IN ('active','refreshing')
    AND o.expires_at>now()+interval '30 seconds'"""

READY_SQL = ACCESS_SQL.replace("o.access_ciphertext,", "")


def oauth_ready(conn, scope, reference):
    return bool(conn.execute(READY_SQL, (scope, [reference])).fetchone())
