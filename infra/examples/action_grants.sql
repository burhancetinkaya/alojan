-- Read-only inspection. Owner consent is recorded only by the reviewed API flow.
-- Never seed grants or replay historical calls from an initialization script.
BEGIN;
SELECT set_config('alojan.scope_id','00000000-0000-4000-8000-000000000001',true);
SELECT id,profile_id,review_digest,enabled,created_at
FROM action_grants
WHERE scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid;
SELECT id AS release_id,profile_id,action_grant_id,manifest->>'schema_version' AS schema_version
FROM agent_releases
WHERE scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid;
ROLLBACK;
