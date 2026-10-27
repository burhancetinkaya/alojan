-- AGP-05: explicit owner consent for an exact agent/action/destination/data scope.
CREATE TABLE action_grants (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    review jsonb NOT NULL CHECK(jsonb_typeof(review)='object' AND octet_length(review::text)<=16384),
    review_digest text NOT NULL CHECK(review_digest ~ '^[0-9a-f]{64}$'),
    granted_by uuid NOT NULL REFERENCES users(id),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope_id,profile_id,id),
    FOREIGN KEY(scope_id,profile_id) REFERENCES assistant_profiles(scope_id,id),
    CHECK((review->>'scope_id') IS NOT DISTINCT FROM scope_id::text
        AND (review->>'profile_id') IS NOT DISTINCT FROM profile_id::text)
);
CREATE UNIQUE INDEX action_grants_active ON action_grants(scope_id,profile_id,review_digest) WHERE enabled;
ALTER TABLE action_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY action_grant_workspace ON action_grants
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_action_grant() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW)-'enabled') IS DISTINCT FROM (to_jsonb(OLD)-'enabled')
        OR (NOT OLD.enabled AND NEW.enabled) THEN
        RAISE EXCEPTION 'Action grant is immutable; request new owner consent' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_action_grant BEFORE UPDATE ON action_grants
    FOR EACH ROW EXECUTE FUNCTION pin_action_grant();
CREATE TRIGGER preserve_action_grant BEFORE DELETE ON action_grants
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();
ALTER TABLE agent_releases ADD COLUMN action_grant_id uuid;
ALTER TABLE agent_releases ADD FOREIGN KEY(scope_id,profile_id,action_grant_id)
    REFERENCES action_grants(scope_id,profile_id,id);
ALTER TABLE agent_releases ADD CHECK(
    (manifest->'action_grant'->>'id')::uuid IS NOT DISTINCT FROM action_grant_id
);
ALTER TABLE agent_releases ADD CHECK(action_grant_id IS NULL OR (
    manifest#>>'{action_grant,review,scope_id}' IS NOT NULL
    AND manifest#>>'{action_grant,review,profile_id}' IS NOT NULL
    AND manifest#>>'{action_grant,review,scope_id}'=scope_id::text
    AND manifest#>>'{action_grant,review,profile_id}'=profile_id::text
));
-- No default grants, delivery jobs or historical replay.
