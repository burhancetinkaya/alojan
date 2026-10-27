-- AGP-03: verified Netgsm number ownership, immutable bindings and call snapshots.
CREATE TABLE phone_numbers (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    e164 text NOT NULL CHECK (e164 ~ '^\+90850[0-9]{7}$'),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','verified','revoked')),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    verification_id uuid,
    active_binding_id uuid,
    enabled boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_id,id),
    UNIQUE (scope_id,id,e164),
    UNIQUE (scope_id,e164),
    CHECK (status <> 'verified' OR verification_id IS NOT NULL),
    CHECK (NOT enabled OR (status='verified' AND active_binding_id IS NOT NULL))
);
-- Unverified guesses must not reserve another customer's number globally.
CREATE UNIQUE INDEX verified_number_owner ON phone_numbers(e164) WHERE status='verified';
CREATE TABLE number_verifications (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    number_id uuid NOT NULL,
    operator_ref text NOT NULL CHECK (operator_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$'),
    decision text NOT NULL CHECK (decision IN ('verified','revoked')),
    reason_ref text CHECK (reason_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'),
    ownership_evidence_ref text CHECK (ownership_evidence_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'),
    routing_evidence_ref text CHECK (routing_evidence_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_id,number_id,id),
    CHECK ((decision='verified' AND ownership_evidence_ref IS NOT NULL AND routing_evidence_ref IS NOT NULL)
        OR (decision='revoked' AND reason_ref IS NOT NULL)),
    FOREIGN KEY (scope_id,number_id) REFERENCES phone_numbers(scope_id,id)
);
ALTER TABLE phone_numbers ADD FOREIGN KEY (scope_id,id,verification_id)
    REFERENCES number_verifications(scope_id,number_id,id);
ALTER TABLE agent_releases ADD UNIQUE (scope_id,profile_id,id,manifest_digest);
CREATE FUNCTION protect_number_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.id,NEW.scope_id,NEW.e164) IS DISTINCT FROM (OLD.id,OLD.scope_id,OLD.e164) THEN
        RAISE EXCEPTION 'Number identity is immutable; provision a new scoped claim'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER immutable_number_identity BEFORE UPDATE ON phone_numbers
    FOR EACH ROW EXECUTE FUNCTION protect_number_identity();
CREATE TABLE release_readiness (
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    release_id uuid NOT NULL,
    node_id text NOT NULL CHECK (node_id ~ '^[a-z0-9][a-z0-9-]{0,63}$'),
    manifest_digest text NOT NULL CHECK (manifest_digest ~ '^[0-9a-f]{64}$'),
    ready boolean NOT NULL DEFAULT false,
    acknowledged_at timestamptz NOT NULL DEFAULT now(),
    valid_until timestamptz NOT NULL,
    CHECK (valid_until > acknowledged_at AND valid_until <= acknowledged_at+interval '30 seconds'),
    checked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_id,release_id,node_id),
    FOREIGN KEY (scope_id,profile_id,release_id,manifest_digest)
        REFERENCES agent_releases(scope_id,profile_id,id,manifest_digest)
);
-- Readiness is a short-lived consumer acknowledgement, never a user claim.
CREATE TABLE number_bindings (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    number_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    profile_id uuid NOT NULL,
    release_id uuid NOT NULL,
    node_id text NOT NULL CHECK (node_id ~ '^[a-z0-9][a-z0-9-]{0,63}$'),
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_id,number_id,id),
    UNIQUE (scope_id,number_id,revision),
    UNIQUE (scope_id,number_id,id,profile_id,release_id,node_id),
    FOREIGN KEY (scope_id,number_id) REFERENCES phone_numbers(scope_id,id),
    FOREIGN KEY (scope_id,profile_id,release_id) REFERENCES agent_releases(scope_id,profile_id,id)
);
ALTER TABLE phone_numbers ADD FOREIGN KEY (scope_id,id,active_binding_id)
    REFERENCES number_bindings(scope_id,number_id,id);
CREATE TABLE call_route_snapshots (
    call_id uuid PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    scope_id uuid NOT NULL,
    number_id uuid NOT NULL,
    binding_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    release_id uuid NOT NULL,
    node_id text NOT NULL,
    called_e164 text NOT NULL CHECK (called_e164 ~ '^\+90850[0-9]{7}$'),
    called_source text NOT NULL CHECK (called_source IN ('request_uri','to')),
    manifest_digest text NOT NULL CHECK (manifest_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (scope_id,number_id,binding_id,profile_id,release_id,node_id)
        REFERENCES number_bindings(scope_id,number_id,id,profile_id,release_id,node_id),
    FOREIGN KEY (scope_id,number_id,called_e164) REFERENCES phone_numbers(scope_id,id,e164),
    FOREIGN KEY (scope_id,profile_id,release_id,manifest_digest)
        REFERENCES agent_releases(scope_id,profile_id,id,manifest_digest)
);
CREATE INDEX call_route_number ON call_route_snapshots(number_id,call_id);
CREATE TRIGGER immutable_call_route BEFORE UPDATE ON call_route_snapshots
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();
DO $$
DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['number_verifications','number_bindings'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_definition BEFORE UPDATE OR DELETE ON %I '
                       'FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation()',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['phone_numbers','number_verifications','release_readiness',
                                    'number_bindings','call_route_snapshots'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY workspace_isolation ON %I USING '
            '(scope_id = nullif(current_setting(''alojan.scope_id'',true),'''')::uuid) '
            'WITH CHECK (scope_id = nullif(current_setting(''alojan.scope_id'',true),'''')::uuid)',relation);
    END LOOP;
END;
$$;
-- Existing calls are deliberately unscoped. No account claim or historical send.
