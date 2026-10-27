-- Read-only diagnostics for an authenticated/operator-selected workspace.
-- Production requests use the versioned HTTP API, which enforces quotas and role checks.
BEGIN;
SELECT set_config('alojan.scope_id', :'scope_id', true);
SELECT j.id, j.preparation_id, p.draft_version, j.attempt, j.status,
       j.failure_code, j.created_at, j.updated_at
FROM voice_preparation_jobs j
JOIN agent_preparations p ON (p.scope_id,p.id)=(j.scope_id,j.preparation_id)
WHERE j.scope_id=:'scope_id'::uuid
ORDER BY j.created_at DESC, j.id DESC
LIMIT 50;
COMMIT;
-- Never INSERT a fake ready asset or force a preparing job back to queued.
-- Interrupted recovery requires fresh admission/worker receipts; see voice-preparer/README.md.
