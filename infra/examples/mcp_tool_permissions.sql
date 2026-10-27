-- PostgreSQL 17, after migration 0022. Read-only diagnostics; never seed approvals.
-- psql -v workspace_id=<existing synthetic workspace UUID> -f this-file.sql
BEGIN;
SELECT set_config('alojan.scope_id', :'workspace_id', true);
SELECT id,connection_id,tool_name,tool_digest,capability,enabled
FROM mcp_tool_reviews WHERE scope_id=:'workspace_id'::uuid
ORDER BY created_at DESC,id LIMIT 100;
SELECT id,profile_id,review_digest,enabled
FROM mcp_tool_grants WHERE scope_id=:'workspace_id'::uuid
ORDER BY created_at DESC,id LIMIT 100;
SELECT id,profile_id,mcp_grant_id,revision FROM agent_releases
WHERE scope_id=:'workspace_id'::uuid AND mcp_grant_id IS NOT NULL
ORDER BY revision DESC LIMIT 100;
SELECT id,release_id,ordinal,turn,alias,status,failure_code,started_at,completed_at
FROM mcp_tool_executions WHERE scope_id=:'workspace_id'::uuid
ORDER BY started_at DESC,id LIMIT 100;
-- Operator capability review and workspace-owner consent are separate operations.
-- Use the private review CLI and authenticated /agents/{id}/mcp-review + /mcp-grants.
-- No credentials, fixed values, caller content, grant creation or execution here.
ROLLBACK;
