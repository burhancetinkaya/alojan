-- Opaque provider references; key material is encrypted outside PostgreSQL.
CREATE TABLE provider_connections (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    provider text NOT NULL CHECK(provider='openrouter'),
    label text NOT NULL CHECK(length(label) BETWEEN 1 AND 80),
    ciphertext bytea NOT NULL CHECK(octet_length(ciphertext) BETWEEN 32 AND 8192),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope_id,id)
);
ALTER TABLE provider_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_connections FORCE ROW LEVEL SECURITY;
CREATE POLICY provider_workspace ON provider_connections
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_provider_connection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.id,NEW.scope_id,NEW.provider,NEW.label,NEW.ciphertext,NEW.created_at)
        IS DISTINCT FROM (OLD.id,OLD.scope_id,OLD.provider,OLD.label,OLD.ciphertext,OLD.created_at)
        OR (NOT OLD.enabled AND NEW.enabled) THEN
        RAISE EXCEPTION 'Provider identity is immutable; create a new connection' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_provider_connection BEFORE UPDATE ON provider_connections
    FOR EACH ROW EXECUTE FUNCTION pin_provider_connection();
