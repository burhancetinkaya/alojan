-- AGP-08: read-only PostgreSQL examples; no connections, grants, jobs or sends.
-- Replace connection_id with a workspace-owned HTTP connection before saving a draft.
-- Conditions apply only to answered, ended calls after summary finalization.
SELECT jsonb_build_object(
    'alias', condition,
    'adapter', 'http_request.v1',
    'connection_id', '00000000-0000-4000-8000-000000000001',
    'condition', condition,
    'method', 'POST',
    'body', jsonb_build_object(
        'call_id', jsonb_build_object('kind', 'source', 'source', 'call_id', 'on_missing', 'fail'),
        'summary_status', jsonb_build_object('kind', 'source', 'source', 'summary_status', 'on_missing', 'fail')
    )
) AS action_example
FROM (VALUES ('answered'), ('summary_ready'), ('summary_failed')) AS conditions(condition);
