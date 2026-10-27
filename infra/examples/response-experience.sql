-- PostgreSQL example only: merge into a full version-checked AgentDraft through
-- authenticated HTTP/MCP. Never mutate immutable release JSON or embed credentials.
-- Prepare a new EMA pack and publish it before activating an enabled draft.
SELECT jsonb_build_object(
    'response_experience', jsonb_build_object(
        'schema_version', 1,
        'enabled', true,
        'style', 'concise',
        'waiting_text', NULL
    )
) AS draft_fields;

-- Operator-only aggregate diagnostics; no phone numbers or conversation content.
SELECT coalesce(manifest->'content'->'response_experience'->>'enabled', 'false') AS waiting_enabled,
       count(*) AS release_count
FROM agent_releases
GROUP BY 1;
