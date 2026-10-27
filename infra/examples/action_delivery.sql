-- Read-only PostgreSQL diagnostics. No tokens, payloads, caller data or replay.
BEGIN;
SELECT set_config('alojan.scope_id','00000000-0000-4000-8000-000000000001',true);
SELECT id,call_id,release_id,profile_id,grant_id,alias,status,attempts,
       failure_code,remote_message_id,next_attempt_at,updated_at
FROM action_jobs
WHERE scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid
ORDER BY created_at DESC,id LIMIT 100;
SELECT status,count(*) FROM action_jobs
WHERE scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid GROUP BY status;
ROLLBACK;
-- delivery_unknown requires informed owner reconciliation; never UPDATE it to pending.
