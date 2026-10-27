-- Read-only PostgreSQL example. No connection, permission, job or send is created.
-- Sharing is off unless this policy AND the two mapped fields are selected.
-- Saving changes the greeting text; prepare fresh audio and review exact consent.
SELECT jsonb_build_object(
    'alias', 'handover',
    'adapter', 'http_request.v1',
    'connection_id', '00000000-0000-4000-8000-000000000001',
    'method', 'POST',
    'transcript_policy', 'bounded_text.v1',
    'body', jsonb_build_object(
        'transcript_text', jsonb_build_object('kind', 'source', 'source', 'transcript.text', 'on_missing', 'null'),
        'transcript_status', jsonb_build_object('kind', 'source', 'source', 'transcript.status', 'on_missing', 'fail')
    )
) AS action_example;
