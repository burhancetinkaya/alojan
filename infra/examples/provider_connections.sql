-- Operator diagnostic only. Never INSERT raw tokens, ciphertext or enabled grants here.
-- Credentials are created through the authenticated write-only API using an external key.
BEGIN;
SELECT set_config('alojan.scope_id','00000000-0000-4000-8000-000000000001',true);
SELECT id,provider,label,enabled,created_at
FROM provider_connections
WHERE scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid;
SELECT id AS release_id,manifest->'content'->>'model_connection' AS connection_reference
FROM agent_releases
WHERE scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid;
ROLLBACK;
