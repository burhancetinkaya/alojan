-- AGP-03/05: PostgreSQL read-only inspection in an authorized workspace.
-- Replace this synthetic UUID with an operator-authorized workspace ID.
-- This setting selects row visibility; it is NOT authentication or proof of membership.
-- Runtime code derives it from a verified call route or a claimed summary job.
BEGIN;
SELECT set_config('alojan.scope_id','00000000-0000-4000-8000-000000000001',true);
SELECT c.id, c.status, c.answered_at, c.ended_at, c.duration_ms,
       s.profile_id, s.release_id, j.status AS summary_status, j.attempts,
       f.event_type, f.summary_status AS finalized_summary_status
FROM calls c
JOIN call_route_snapshots s ON s.call_id=c.id
LEFT JOIN summary_jobs j ON j.call_id=c.id
LEFT JOIN call_finalizations f ON f.call_id=c.id
WHERE s.scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid
ORDER BY c.started_at DESC
LIMIT 20;
ROLLBACK;
-- Do not insert jobs/events by hand: CallRecords.end and CallSummaries.finish
-- enforce atomic transitions, claim fencing and immutable release ownership.
-- This example intentionally excludes names, numbers, notes and summary bodies.
