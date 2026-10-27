-- PostgreSQL 17, AGP-07. Run with psql -v workspace_id=<existing synthetic workspace UUID> -v mcp_endpoint=<private configured endpoint>.
-- Demonstration only: no credentials, discovery job, grant, tool execution or lasting write.
BEGIN;
SELECT set_config('alojan.scope_id', :'workspace_id', true);
INSERT INTO mcp_connections(id,scope_id,label,endpoint,auth_type,enabled)
SELECT 'a1000000-0000-4000-8000-000000000020', id,
       'Synthetic disabled MCP', :'mcp_endpoint', 'none', false
FROM recipient_scopes WHERE id=:'workspace_id'::uuid
ON CONFLICT DO NOTHING;
SELECT id,label,endpoint,auth_type,enabled
FROM mcp_connections WHERE scope_id=:'workspace_id'::uuid;
-- Use authenticated POST /mcp-connections/{id}/discovery to request actual discovery.
-- Never insert completed manifests or execution grants from user-supplied SQL.
ROLLBACK;
