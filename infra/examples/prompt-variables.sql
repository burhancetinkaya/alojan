-- PostgreSQL example; no production mutation. Merge these fields into a full
-- AgentDraft through the authenticated HTTP/MCP API with its current version.
-- Do not update immutable release JSON directly or store credentials here.
SELECT jsonb_build_object(
    'instructions', 'You are {{agent_name}}, assisting {{owner_name}} for {{team}}. Now: {{current_datetime}}.',
    'prompt_template', jsonb_build_object(
        'version', 1,
        'timezone', 'Europe/Istanbul',
        'variables', jsonb_build_array(jsonb_build_object('name', 'team', 'value', 'Example team'))
    )
) AS draft_fields;

-- Operator diagnostics: inspect only presence/version, never variable values.
SELECT manifest->>'schema_version' AS release_schema_version,
       manifest->'content'->'prompt_template'->>'version' AS template_version,
       count(*) AS release_count
FROM agent_releases
GROUP BY 1, 2;
