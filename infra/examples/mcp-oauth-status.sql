-- AGP-07, PostgreSQL 16; examples only. T-SQL is not the repository's SQL dialect.
-- Apply versioned migrations with the existing migration runner, not manual seed
-- inserts. Create connections through the owner/session-bound API. Never paste tokens.
-- psql -v workspace_id=<authorized-workspace-uuid> -f infra/examples/mcp-oauth-status.sql
BEGIN;
SELECT set_config('alojan.scope_id', :'workspace_id', true);
SELECT c.id, c.label, c.enabled, o.status, o.expires_at, o.refresh_after, o.generation
FROM mcp_connections c
JOIN mcp_oauth_credentials o ON (o.scope_id,o.connection_id)=(c.scope_id,c.id)
WHERE c.scope_id=:'workspace_id'::uuid
ORDER BY c.created_at DESC;
-- Metadata only: do not select ciphertext, state/code hashes or PKCE verifiers.
SELECT status, count(*) AS attempts
FROM mcp_oauth_flows
WHERE scope_id=:'workspace_id'::uuid
GROUP BY status;
ROLLBACK;
