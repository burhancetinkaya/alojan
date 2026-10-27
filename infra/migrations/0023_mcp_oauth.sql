-- AGP-07: pre-registered OAuth identities are immutable; only their tokens rotate.
ALTER TABLE mcp_connections DROP CONSTRAINT mcp_connections_auth_type_check;
ALTER TABLE mcp_connections DROP CONSTRAINT mcp_connections_check;
ALTER TABLE mcp_connections ADD CHECK(auth_type IN ('none','bearer','oauth'));
ALTER TABLE mcp_connections ADD CHECK(
    (auth_type IN ('none','oauth') AND ciphertext IS NULL) OR
    (auth_type='bearer' AND ciphertext IS NOT NULL AND octet_length(ciphertext) BETWEEN 32 AND 8192));

CREATE TABLE mcp_oauth_flows (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    user_id uuid NOT NULL REFERENCES users(id),
    session_hash text NOT NULL CHECK(length(session_hash)=64),
    state_hash text NOT NULL UNIQUE CHECK(length(state_hash)=64),
    verifier bytea NOT NULL CHECK(octet_length(verifier) BETWEEN 32 AND 8192),
    label text NOT NULL CHECK(length(label) BETWEEN 1 AND 80),
    provider jsonb NOT NULL CHECK(jsonb_typeof(provider)='object' AND octet_length(provider::text)<=8192),
    redirect_uri text NOT NULL CHECK(length(redirect_uri)<=2048),
    status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','exchanging','complete','failed')),
    code_hash text CHECK(length(code_hash)=64),
    connection_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '10 minutes',
    FOREIGN KEY(scope_id,connection_id) REFERENCES mcp_connections(scope_id,id),
    CHECK((status='complete')=(connection_id IS NOT NULL)),
    CHECK(expires_at<=created_at+interval '10 minutes'),
    UNIQUE(scope_id,id)
);
CREATE INDEX mcp_oauth_flow_scope ON mcp_oauth_flows(scope_id,created_at);
ALTER TABLE mcp_oauth_flows ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_oauth_flows FORCE ROW LEVEL SECURITY;
CREATE POLICY mcp_oauth_flow_scope ON mcp_oauth_flows
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_mcp_oauth_flow() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.id,NEW.scope_id,NEW.user_id,NEW.session_hash,NEW.state_hash,NEW.verifier,NEW.label,
        NEW.provider,NEW.redirect_uri,NEW.created_at,NEW.expires_at)
        IS DISTINCT FROM
        (OLD.id,OLD.scope_id,OLD.user_id,OLD.session_hash,OLD.state_hash,OLD.verifier,OLD.label,
        OLD.provider,OLD.redirect_uri,OLD.created_at,OLD.expires_at)
        OR OLD.status IN ('complete','failed')
        OR (OLD.status='pending' AND NEW.status NOT IN ('exchanging','failed'))
        OR (OLD.status='exchanging' AND NEW.status NOT IN ('complete','failed'))
        OR (OLD.code_hash IS NOT NULL AND NEW.code_hash IS DISTINCT FROM OLD.code_hash) THEN
        RAISE EXCEPTION 'Invalid OAuth flow transition' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_mcp_oauth_flow BEFORE UPDATE ON mcp_oauth_flows
    FOR EACH ROW EXECUTE FUNCTION pin_mcp_oauth_flow();

CREATE TABLE mcp_oauth_credentials (
    connection_id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    authorized_by uuid NOT NULL REFERENCES users(id),
    provider jsonb NOT NULL CHECK(jsonb_typeof(provider)='object' AND octet_length(provider::text)<=8192),
    access_ciphertext bytea NOT NULL CHECK(octet_length(access_ciphertext) BETWEEN 32 AND 16384),
    refresh_ciphertext bytea CHECK(octet_length(refresh_ciphertext) BETWEEN 32 AND 16384),
    expires_at timestamptz NOT NULL,
    refresh_after timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','refreshing','reauth_required')),
    generation integer NOT NULL DEFAULT 1 CHECK(generation BETWEEN 1 AND 2147483646),
    claim_token uuid,
    lease_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(scope_id,connection_id) REFERENCES mcp_connections(scope_id,id),
    CHECK((status='refreshing')=(lease_until IS NOT NULL)),
    CHECK((status='refreshing')=(claim_token IS NOT NULL)),
    UNIQUE(scope_id,connection_id)
);
CREATE INDEX mcp_oauth_refresh ON mcp_oauth_credentials(refresh_after,connection_id) WHERE status='active';
CREATE INDEX mcp_oauth_leases ON mcp_oauth_credentials(lease_until) WHERE status='refreshing';
ALTER TABLE mcp_oauth_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_oauth_credentials FORCE ROW LEVEL SECURITY;
CREATE POLICY mcp_oauth_credential_scope ON mcp_oauth_credentials
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_mcp_oauth_credentials() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.connection_id,NEW.scope_id,NEW.authorized_by,NEW.provider,NEW.created_at)
        IS DISTINCT FROM (OLD.connection_id,OLD.scope_id,OLD.authorized_by,OLD.provider,OLD.created_at)
        OR OLD.status='reauth_required'
        OR (OLD.status='active' AND NEW.status NOT IN ('refreshing','reauth_required'))
        OR (OLD.status='refreshing' AND NEW.status NOT IN ('active','reauth_required'))
        OR (NEW.status='active' AND NEW.generation<>OLD.generation+1)
        OR (NEW.status<>'active' AND (NEW.access_ciphertext,NEW.refresh_ciphertext,NEW.expires_at,NEW.refresh_after,NEW.generation)
            IS DISTINCT FROM (OLD.access_ciphertext,OLD.refresh_ciphertext,OLD.expires_at,OLD.refresh_after,OLD.generation)) THEN
        RAISE EXCEPTION 'Invalid OAuth credential transition' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_mcp_oauth_credentials BEFORE UPDATE ON mcp_oauth_credentials
    FOR EACH ROW EXECUTE FUNCTION pin_mcp_oauth_credentials();
