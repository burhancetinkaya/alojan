-- AGP-07: immutable release grants and bounded, scoped read-tool execution journal.
ALTER TABLE agent_releases ADD COLUMN mcp_grant_id uuid;
ALTER TABLE agent_releases ADD FOREIGN KEY(scope_id,profile_id,mcp_grant_id)
    REFERENCES mcp_tool_grants(scope_id,profile_id,id);
ALTER TABLE agent_releases ADD CHECK(
    (manifest->'mcp_grant'->>'id')::uuid IS NOT DISTINCT FROM mcp_grant_id
);
ALTER TABLE agent_releases ADD CHECK(mcp_grant_id IS NULL OR (
    manifest#>>'{mcp_grant,review,scope_id}' IS NOT NULL
    AND manifest#>>'{mcp_grant,review,profile_id}' IS NOT NULL
    AND manifest#>>'{mcp_grant,review,scope_id}'=scope_id::text
    AND manifest#>>'{mcp_grant,review,profile_id}'=profile_id::text
));
CREATE TABLE mcp_tool_executions (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    call_id uuid NOT NULL,
    release_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK(ordinal BETWEEN 1 AND 8),
    turn integer NOT NULL CHECK(turn BETWEEN 1 AND 1000),
    alias text NOT NULL CHECK(alias ~ '^mcp_[a-z][a-z0-9_]{0,35}$'),
    status text NOT NULL DEFAULT 'started' CHECK(status IN ('started','succeeded','failed','cancelled')),
    failure_code text CHECK(failure_code IN ('unavailable','invalid_result','cancelled','timeout')),
    output jsonb CHECK(jsonb_typeof(output)='object' AND octet_length(output::text)<=16384),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(scope_id,call_id,ordinal),
    FOREIGN KEY(scope_id,call_id,release_id) REFERENCES call_route_snapshots(scope_id,call_id,release_id),
    CHECK((status='succeeded')=(output IS NOT NULL)),
    CHECK((status='started')=(completed_at IS NULL)),
    CHECK((status IN ('failed','cancelled'))=(failure_code IS NOT NULL))
);
ALTER TABLE mcp_tool_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_tool_executions FORCE ROW LEVEL SECURITY;
CREATE POLICY mcp_execution_workspace ON mcp_tool_executions
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_mcp_execution() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status<>'started' OR NEW.status='started'
        OR (to_jsonb(NEW)-ARRAY['status','failure_code','output','completed_at'])
        IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','failure_code','output','completed_at']) THEN
        RAISE EXCEPTION 'MCP execution is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_mcp_execution BEFORE UPDATE ON mcp_tool_executions
    FOR EACH ROW EXECUTE FUNCTION pin_mcp_execution();
CREATE TRIGGER preserve_mcp_execution BEFORE DELETE ON mcp_tool_executions
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();
-- No calls, grants, notifications or default endpoints are created.
