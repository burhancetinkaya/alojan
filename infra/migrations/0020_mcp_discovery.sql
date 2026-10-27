-- AGP-07a: immutable workspace connections and discovery, not execution grants.
CREATE TABLE mcp_connections (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    label text NOT NULL CHECK(length(label) BETWEEN 1 AND 80),
    endpoint text NOT NULL CHECK(length(endpoint) BETWEEN 1 AND 2048),
    auth_type text NOT NULL CHECK(auth_type IN ('none','bearer')),
    ciphertext bytea,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK((auth_type='none' AND ciphertext IS NULL) OR
          (auth_type='bearer' AND ciphertext IS NOT NULL AND octet_length(ciphertext) BETWEEN 32 AND 8192)),
    UNIQUE(scope_id,id)
);
ALTER TABLE mcp_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_connections FORCE ROW LEVEL SECURITY;
CREATE POLICY mcp_workspace ON mcp_connections
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_mcp_connection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.id,NEW.scope_id,NEW.label,NEW.endpoint,NEW.auth_type,NEW.ciphertext,NEW.created_at)
        IS DISTINCT FROM (OLD.id,OLD.scope_id,OLD.label,OLD.endpoint,OLD.auth_type,OLD.ciphertext,OLD.created_at)
        OR (NOT OLD.enabled AND NEW.enabled) THEN
        RAISE EXCEPTION 'MCP identity is immutable; create a new connection' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_mcp_connection BEFORE UPDATE ON mcp_connections
    FOR EACH ROW EXECUTE FUNCTION pin_mcp_connection();

CREATE TABLE mcp_discovery_jobs (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','ready','failed')),
    claim_token uuid,
    lease_until timestamptz,
    failure_code text CHECK(failure_code IN ('endpoint_not_approved','connection_revoked','discovery_failed','lease_expired')),
    manifest jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE(scope_id,id),
    FOREIGN KEY(scope_id,connection_id) REFERENCES mcp_connections(scope_id,id),
    CHECK((status='running')=(lease_until IS NOT NULL)),
    CHECK((status IN ('ready','failed'))=(completed_at IS NOT NULL)),
    CHECK((status='ready')=(manifest IS NOT NULL)),
    CHECK((status='failed')=(failure_code IS NOT NULL)),
    CHECK(manifest IS NULL OR (jsonb_typeof(manifest)='object' AND octet_length(manifest::text)<=524288))
);
CREATE UNIQUE INDEX mcp_discovery_active ON mcp_discovery_jobs(scope_id,connection_id)
    WHERE status IN ('queued','running');
CREATE INDEX mcp_discovery_queue ON mcp_discovery_jobs(created_at,id) WHERE status='queued';
CREATE INDEX mcp_discovery_leases ON mcp_discovery_jobs(lease_until) WHERE status='running';
CREATE INDEX mcp_discovery_workspace ON mcp_discovery_jobs(scope_id,created_at DESC);
ALTER TABLE mcp_discovery_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_discovery_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY mcp_discovery_workspace ON mcp_discovery_jobs
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_mcp_discovery() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.id,NEW.scope_id,NEW.connection_id,NEW.created_at)
        IS DISTINCT FROM (OLD.id,OLD.scope_id,OLD.connection_id,OLD.created_at)
        OR OLD.status IN ('ready','failed')
        OR (OLD.status='queued' AND NEW.status NOT IN ('running','failed'))
        OR (OLD.status='running' AND NEW.status NOT IN ('ready','failed')) THEN
        RAISE EXCEPTION 'Invalid MCP discovery transition' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_mcp_discovery BEFORE UPDATE ON mcp_discovery_jobs
    FOR EACH ROW EXECUTE FUNCTION pin_mcp_discovery();
