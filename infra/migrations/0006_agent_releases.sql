-- AGP-02/06: immutable catalog definitions, preparation requests and releases.
CREATE TABLE engine_presets (
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9-]{0,79}$'),
    revision integer NOT NULL CHECK (revision > 0),
    configuration jsonb NOT NULL CHECK (jsonb_typeof(configuration) = 'object'
        AND octet_length(configuration::text) <= 16384),
    digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, revision)
);
CREATE TABLE model_catalog (
    id text NOT NULL CHECK (id ~ '^[a-z][a-z0-9-]{0,79}$'),
    revision integer NOT NULL CHECK (revision > 0),
    display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 100),
    preset_id text NOT NULL,
    preset_revision integer NOT NULL,
    PRIMARY KEY (id,revision),
    FOREIGN KEY (preset_id,preset_revision) REFERENCES engine_presets(id,revision)
);
-- Qualification/revocation is separate from immutable historical definitions.
CREATE TABLE model_catalog_status (
    model_id text PRIMARY KEY,
    model_revision integer NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    qualification_ref text NOT NULL CHECK (length(btrim(qualification_ref)) BETWEEN 1 AND 200),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (model_id,model_revision) REFERENCES model_catalog(id,revision)
);
CREATE TABLE agent_preparations (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    draft_version integer NOT NULL CHECK (draft_version > 0),
    requested_by uuid NOT NULL REFERENCES users(id),
    model_id text NOT NULL,
    model_revision integer NOT NULL,
    content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object' AND octet_length(content::text) <= 65536),
    content_digest text NOT NULL CHECK (content_digest ~ '^[0-9a-f]{64}$'),
    speech_digest text NOT NULL CHECK (speech_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_id,profile_id,id),
    UNIQUE (scope_id,profile_id,draft_version,model_id,model_revision),
    FOREIGN KEY (scope_id,profile_id) REFERENCES assistant_profiles(scope_id,id),
    FOREIGN KEY (model_id,model_revision) REFERENCES model_catalog(id,revision)
);
CREATE TABLE prepared_voice_assets (
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    speech_digest text NOT NULL CHECK (speech_digest ~ '^[0-9a-f]{64}$'),
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest) = 'object' AND octet_length(manifest::text) <= 8192),
    manifest_digest text NOT NULL CHECK (manifest_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_id,speech_digest)
);
CREATE TABLE agent_releases (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    preparation_id uuid NOT NULL,
    speech_digest text NOT NULL,
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest) = 'object' AND octet_length(manifest::text) <= 131072),
    manifest_digest text NOT NULL CHECK (manifest_digest ~ '^[0-9a-f]{64}$'),
    published_by uuid NOT NULL REFERENCES users(id),
    rollback_of uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_id,profile_id,id),
    UNIQUE (scope_id,profile_id,revision),
    FOREIGN KEY (scope_id,profile_id,preparation_id) REFERENCES agent_preparations(scope_id,profile_id,id),
    FOREIGN KEY (scope_id,speech_digest) REFERENCES prepared_voice_assets(scope_id,speech_digest),
    FOREIGN KEY (scope_id,profile_id,revision) REFERENCES assistant_profile_revisions(scope_id,profile_id,revision),
    FOREIGN KEY (scope_id,profile_id,rollback_of) REFERENCES agent_releases(scope_id,profile_id,id)
);
CREATE TABLE agent_publications (
    scope_id uuid NOT NULL,
    profile_id uuid PRIMARY KEY,
    release_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    FOREIGN KEY (scope_id,profile_id,release_id) REFERENCES agent_releases(scope_id,profile_id,id)
);
DO $$
DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['engine_presets','model_catalog','agent_preparations',
                                    'prepared_voice_assets','agent_releases'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_definition BEFORE UPDATE OR DELETE ON %I '
                       'FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation()', relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['agent_preparations','prepared_voice_assets','agent_releases','agent_publications'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', relation);
        EXECUTE format('CREATE POLICY workspace_isolation ON %I USING '
                       '(scope_id = nullif(current_setting(''alojan.scope_id'',true),'''')::uuid) '
                       'WITH CHECK (scope_id = nullif(current_setting(''alojan.scope_id'',true),'''')::uuid)', relation);
    END LOOP;
END;
$$;
-- Definition and asset writes are restricted to operator/worker roles at deployment.
-- Nothing is qualified, published, routed or sent by this migration.
