-- PostgreSQL 17, AGP-08, after migration 0024. No SQL Server T-SQL.
-- psql -v workspace_id=<existing synthetic workspace UUID> -f this-file
-- Demonstration only: no credential, permission, job, send or lasting write.
BEGIN;
SELECT set_config('alojan.scope_id', :'workspace_id', true);
INSERT INTO http_connections(id,scope_id,label,endpoint,auth_type,enabled)
SELECT 'a1000000-0000-4000-8000-000000000024', id,
       'Synthetic disabled HTTP', 'https://hooks.example.test/calls', 'none', false
FROM recipient_scopes WHERE id=:'workspace_id'::uuid
ON CONFLICT DO NOTHING;
SELECT id,label,auth_type,enabled
FROM http_connections WHERE scope_id=:'workspace_id'::uuid
ORDER BY created_at,id LIMIT 100;
-- Status only: never disclose projected call data, request body/query or credentials.
SELECT id,status,attempts,retry_generation,http_status,created_at
FROM action_jobs
WHERE scope_id=:'workspace_id'::uuid AND action->>'adapter'='http_request.v1'
ORDER BY created_at DESC,id LIMIT 20;
-- Author real destinations/grants/retries through authenticated owner APIs, not SQL.
ROLLBACK;
