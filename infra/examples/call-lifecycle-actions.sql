-- PostgreSQL 17: read-only examples. Use owned connections and exact owner consent.
-- These SELECTs do not publish, enqueue, replay or send anything.
SELECT jsonb_build_object(
    'alias', 'missed_call', 'adapter', 'http_request.v1',
    'event', 'call.finalized.v1', 'condition', 'no_answer',
    'connection_id', '00000000-0000-4000-8000-000000000001',
    'method', 'POST', 'headers', '{}'::jsonb, 'query', '{}'::jsonb,
    'body', jsonb_build_object(
        'call_id', jsonb_build_object('kind','source','source','call_id','on_missing','fail'),
        'summary_state', jsonb_build_object('kind','source','source','summary_status','on_missing','fail')
    )
) AS unanswered_action;
-- An answered remote hangup (including an ordinary farewell) or native failure qualifies.
SELECT jsonb_build_object(
    'alias', 'ended_by_caller_or_failure', 'adapter', 'http_request.v1',
    'event', 'call.finalized.v1', 'condition', 'interrupted',
    'connection_id', '00000000-0000-4000-8000-000000000001',
    'method', 'POST', 'headers', '{}'::jsonb, 'query', '{}'::jsonb,
    'body', jsonb_build_object(
        'call_id', jsonb_build_object('kind','source','source','call_id','on_missing','fail'),
        'outcome', jsonb_build_object('kind','source','source','outcome','on_missing','fail')
    )
) AS interrupted_action;
