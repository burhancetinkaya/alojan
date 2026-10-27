-- MCP-02/04 diagnostic examples for PostgreSQL, not Microsoft T-SQL.
-- Run only as an authorized operator in a disposable fixture or with a scoped role.
-- Personal tokens must be created by the application; never seed plaintext secrets.
BEGIN;
SET LOCAL statement_timeout = '3s';
-- Synthetic workspace UUID. Replace through a trusted operator workflow.
SELECT set_config('alojan.scope_id', '00000000-0000-4000-8000-000000000001', true);
SELECT name, permissions, expires_at, revoked_at, last_used_at
FROM personal_access_tokens
WHERE scope_id = current_setting('alojan.scope_id')::uuid
ORDER BY created_at DESC LIMIT 20;
SELECT operation_key, status, created_at, result IS NULL AS compacted
FROM management_operations
WHERE scope_id = current_setting('alojan.scope_id')::uuid
ORDER BY created_at DESC LIMIT 20;
SELECT kind, expires_at, connection_id IS NOT NULL AS complete
FROM management_connection_setups
WHERE scope_id = current_setting('alojan.scope_id')::uuid
ORDER BY created_at DESC LIMIT 20;
ROLLBACK;
