-- AGP-05: durable, immutable intent; uncertain external writes are never retried automatically.
ALTER TABLE call_finalizations ADD UNIQUE(scope_id,call_id,release_id);
ALTER TABLE agent_releases ADD UNIQUE(scope_id,profile_id,id,action_grant_id);
CREATE TABLE action_jobs (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    call_id uuid NOT NULL,
    release_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    grant_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    event_type text NOT NULL DEFAULT 'call.finalized.v1' CHECK(event_type='call.finalized.v1'),
    alias text NOT NULL CHECK(alias ~ '^[a-z][a-z0-9_]{0,39}$'),
    action jsonb NOT NULL CHECK(jsonb_typeof(action)='object' AND octet_length(action::text)<=8192),
    payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536),
    status text NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','leased','sending','sent','failed','paused','delivery_unknown')),
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 5),
    claim_token uuid,
    lease_until timestamptz,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    failure_code text CHECK(failure_code IN ('authority_revoked','invalid_intent','credential_unavailable',
        'connect_failed','rate_limited','rejected','invalid_response','send_uncertain','attempts_exhausted')),
    remote_message_id bigint CHECK(remote_message_id>0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope_id,call_id,event_type,alias),
    FOREIGN KEY(scope_id,call_id,release_id) REFERENCES call_finalizations(scope_id,call_id,release_id),
    FOREIGN KEY(scope_id,profile_id,grant_id) REFERENCES action_grants(scope_id,profile_id,id),
    FOREIGN KEY(scope_id,profile_id,release_id,grant_id)
        REFERENCES agent_releases(scope_id,profile_id,id,action_grant_id),
    FOREIGN KEY(scope_id,connection_id) REFERENCES telegram_connections(scope_id,id),
    CHECK((status IN ('leased','sending'))=(claim_token IS NOT NULL)),
    CHECK((claim_token IS NULL)=(lease_until IS NULL)),
    CHECK((status='sent')=(remote_message_id IS NOT NULL))
);
CREATE INDEX action_jobs_due ON action_jobs(scope_id,next_attempt_at,created_at,id) WHERE status='pending';
CREATE INDEX action_jobs_expired ON action_jobs(lease_until,id) WHERE status IN ('leased','sending');
CREATE FUNCTION pin_action_job() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW)-ARRAY['status','attempts','claim_token','lease_until','next_attempt_at',
         'failure_code','remote_message_id','updated_at']) IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['status','attempts','claim_token','lease_until','next_attempt_at',
         'failure_code','remote_message_id','updated_at']) THEN
        RAISE EXCEPTION 'Action intent is immutable' USING ERRCODE='23514';
    END IF;
    IF NOT ((OLD.status='pending' AND NEW.status='leased')
         OR (OLD.status='leased' AND NEW.status IN ('sending','pending','paused','failed'))
         OR (OLD.status='sending' AND NEW.status IN ('sent','pending','failed','delivery_unknown'))
         OR (OLD.status=NEW.status AND OLD.status IN ('leased','sending')
             AND OLD.claim_token=NEW.claim_token AND NEW.lease_until<=OLD.lease_until)
         OR (NEW IS NOT DISTINCT FROM OLD)) THEN
        RAISE EXCEPTION 'Invalid action transition' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_action_job BEFORE UPDATE ON action_jobs FOR EACH ROW EXECUTE FUNCTION pin_action_job();
CREATE TRIGGER preserve_action_job BEFORE DELETE ON action_jobs
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();
ALTER TABLE action_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY action_job_workspace ON action_jobs
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
-- Tiny scheduler rows keep round-robin selection/rate gates independent of queue depth.
CREATE TABLE action_dispatch_scopes (
    scope_id uuid PRIMARY KEY REFERENCES recipient_scopes(id),
    last_claim_at timestamptz NOT NULL DEFAULT '-infinity',
    next_dispatch_at timestamptz NOT NULL DEFAULT '-infinity'
);
ALTER TABLE action_dispatch_scopes ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_dispatch_scopes FORCE ROW LEVEL SECURITY;
CREATE POLICY action_dispatch_workspace ON action_dispatch_scopes
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE TABLE action_dispatch_clock (
    provider text PRIMARY KEY CHECK(provider='telegram'),
    next_dispatch_at timestamptz NOT NULL DEFAULT '-infinity'
);
INSERT INTO action_dispatch_clock(provider) VALUES('telegram');
-- No historical replay, credentials, grants or destinations are seeded.
