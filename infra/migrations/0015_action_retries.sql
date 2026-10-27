-- AGP-05: immutable, idempotent owner consent for a retry of the original intent.
ALTER TABLE action_jobs ADD COLUMN retry_generation integer NOT NULL DEFAULT 0
    CHECK(retry_generation BETWEEN 0 AND 3);
ALTER TABLE action_jobs ADD UNIQUE(scope_id,profile_id,id);
CREATE INDEX action_jobs_history ON action_jobs(scope_id,profile_id,created_at DESC,id DESC);
CREATE INDEX action_jobs_status_history ON action_jobs(scope_id,profile_id,status,created_at DESC,id DESC);
CREATE TABLE action_retry_requests (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    job_id uuid NOT NULL,
    generation integer NOT NULL CHECK(generation BETWEEN 1 AND 3),
    requested_by uuid NOT NULL REFERENCES users(id),
    review jsonb NOT NULL CHECK(jsonb_typeof(review)='object' AND octet_length(review::text)<=32768),
    review_digest text NOT NULL CHECK(review_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    consumed_at timestamptz,
    UNIQUE(scope_id,job_id,generation),
    FOREIGN KEY(scope_id,profile_id,job_id) REFERENCES action_jobs(scope_id,profile_id,id),
    CHECK((review#>>'{job,id}') IS NOT DISTINCT FROM job_id::text
        AND (review#>>'{job,scope_id}') IS NOT DISTINCT FROM scope_id::text
        AND (review#>>'{job,profile_id}') IS NOT DISTINCT FROM profile_id::text
        AND (review->>'duplicate_warning') IS NOT DISTINCT FROM 'duplicate_delivery_possible'
        AND (review#>>'{job,retry_generation}') IS NOT DISTINCT FROM (generation-1)::text
        AND coalesce(review#>>'{job,status}' IN ('failed','paused','delivery_unknown'),false))
);
ALTER TABLE action_retry_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_retry_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY action_retry_workspace ON action_retry_requests
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE INDEX action_retries_pending ON action_retry_requests(created_at,id) WHERE consumed_at IS NULL;
CREATE FUNCTION pin_action_retry() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' OR (to_jsonb(NEW)-'consumed_at') IS DISTINCT FROM (to_jsonb(OLD)-'consumed_at')
        OR OLD.consumed_at IS NOT NULL OR NEW.consumed_at IS NULL THEN
        RAISE EXCEPTION 'Retry consent is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER preserve_action_retry BEFORE UPDATE OR DELETE ON action_retry_requests
    FOR EACH ROW EXECUTE FUNCTION pin_action_retry();
CREATE OR REPLACE FUNCTION pin_action_job() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW)-ARRAY['status','attempts','claim_token','lease_until','next_attempt_at',
         'failure_code','remote_message_id','updated_at','retry_generation']) IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['status','attempts','claim_token','lease_until','next_attempt_at',
         'failure_code','remote_message_id','updated_at','retry_generation']) THEN
        RAISE EXCEPTION 'Action intent is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.status IN ('failed','paused','delivery_unknown') AND NEW.status='pending'
       AND NEW.retry_generation=OLD.retry_generation+1 AND NEW.attempts=0
       AND NEW.failure_code IS NULL AND NEW.claim_token IS NULL AND NEW.lease_until IS NULL
       AND EXISTS (SELECT 1 FROM action_retry_requests r
           WHERE r.scope_id=OLD.scope_id AND r.profile_id=OLD.profile_id AND r.job_id=OLD.id
           AND r.generation=NEW.retry_generation AND r.consumed_at IS NULL
           AND r.review#>>'{job,status}'=OLD.status
           AND (r.review#>>'{job,attempts}')::integer=OLD.attempts
           AND (r.review#>>'{job,retry_generation}')::integer=OLD.retry_generation) THEN
        RETURN NEW;
    END IF;
    IF NEW.retry_generation<>OLD.retry_generation THEN
        RAISE EXCEPTION 'Retry requires exact owner review' USING ERRCODE='23514';
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
-- No historical retry requests or state resets. A worker consumes only explicit owner consent.
