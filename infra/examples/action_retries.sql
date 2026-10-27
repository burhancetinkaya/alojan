-- Read-only PostgreSQL inspection; retry consent is created by the reviewed owner API only.
BEGIN;
SELECT set_config('alojan.scope_id','00000000-0000-4000-8000-000000000001',true);
SELECT j.id,j.profile_id,j.status,j.retry_generation,j.attempts,
       r.id AS request_id,r.generation,r.created_at,r.consumed_at,
       r.review#>>'{job,status}' AS previous_status
FROM action_jobs j LEFT JOIN action_retry_requests r ON (r.scope_id,r.job_id)=(j.scope_id,j.id)
WHERE j.scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid
ORDER BY j.created_at DESC,j.id,r.generation LIMIT 100;
ROLLBACK;
-- No payload/review text, credentials, queue resets, seeded consent or external writes.
