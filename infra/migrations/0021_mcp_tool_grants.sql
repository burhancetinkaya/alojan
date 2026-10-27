-- AGP-07: operator-reviewed read capabilities and exact per-agent owner consent.
ALTER TABLE mcp_discovery_jobs ADD UNIQUE(scope_id,connection_id,id);
CREATE TABLE mcp_tool_reviews (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    discovery_id uuid NOT NULL,
    tool_name text NOT NULL CHECK(tool_name ~ '^[A-Za-z0-9_.-]{1,128}$'),
    tool_digest text NOT NULL CHECK(tool_digest ~ '^[0-9a-f]{64}$'),
    tool jsonb NOT NULL CHECK(jsonb_typeof(tool)='object' AND octet_length(tool::text)<=65536),
    capability text NOT NULL CHECK(capability='read'),
    reviewed_by text NOT NULL CHECK(length(reviewed_by) BETWEEN 1 AND 100),
    evidence text NOT NULL CHECK(length(evidence) BETWEEN 1 AND 1000),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope_id,connection_id,id),
    FOREIGN KEY(scope_id,connection_id) REFERENCES mcp_connections(scope_id,id),
    FOREIGN KEY(scope_id,connection_id,discovery_id) REFERENCES mcp_discovery_jobs(scope_id,connection_id,id),
    CHECK((tool->>'name') IS NOT DISTINCT FROM tool_name
        AND (tool->>'digest') IS NOT DISTINCT FROM tool_digest)
);
CREATE UNIQUE INDEX mcp_tool_review_active ON mcp_tool_reviews(scope_id,connection_id,tool_digest) WHERE enabled;
ALTER TABLE mcp_tool_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_tool_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY mcp_tool_review_workspace ON mcp_tool_reviews
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE TRIGGER pin_mcp_tool_review BEFORE UPDATE ON mcp_tool_reviews
    FOR EACH ROW EXECUTE FUNCTION pin_action_grant();
CREATE TRIGGER preserve_mcp_tool_review BEFORE DELETE ON mcp_tool_reviews
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();

CREATE TABLE mcp_tool_grants (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    review jsonb NOT NULL CHECK(jsonb_typeof(review)='object' AND octet_length(review::text)<=524288),
    review_digest text NOT NULL CHECK(review_digest ~ '^[0-9a-f]{64}$'),
    granted_by uuid NOT NULL REFERENCES users(id),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope_id,profile_id,id),
    FOREIGN KEY(scope_id,profile_id) REFERENCES assistant_profiles(scope_id,id),
    CHECK((review->>'scope_id') IS NOT DISTINCT FROM scope_id::text
        AND (review->>'profile_id') IS NOT DISTINCT FROM profile_id::text)
);
CREATE UNIQUE INDEX mcp_tool_grant_active ON mcp_tool_grants(scope_id,profile_id,review_digest) WHERE enabled;
ALTER TABLE mcp_tool_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_tool_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY mcp_tool_grant_workspace ON mcp_tool_grants
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE TRIGGER pin_mcp_tool_grant BEFORE UPDATE ON mcp_tool_grants
    FOR EACH ROW EXECUTE FUNCTION pin_action_grant();
CREATE TRIGGER preserve_mcp_tool_grant BEFORE DELETE ON mcp_tool_grants
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();
-- No seed permissions and no executable releases. Runtime/admission integration follows.
