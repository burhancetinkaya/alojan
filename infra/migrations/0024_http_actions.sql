-- AGP-08: additive immutable HTTP destinations and typed action job targets.
CREATE TABLE http_connections (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    label text NOT NULL CHECK(length(label) BETWEEN 1 AND 80),
    endpoint text NOT NULL CHECK(length(endpoint) BETWEEN 10 AND 2048),
    auth_type text NOT NULL CHECK(auth_type IN ('none','bearer')),
    ciphertext bytea,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope_id,id),
    CHECK((auth_type='none' AND ciphertext IS NULL) OR
          (auth_type='bearer' AND octet_length(ciphertext) BETWEEN 32 AND 8192 AND ciphertext IS NOT NULL))
);
ALTER TABLE http_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE http_connections FORCE ROW LEVEL SECURITY;
CREATE POLICY http_connection_scope ON http_connections
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_http_connection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' OR (to_jsonb(NEW)-'enabled') IS DISTINCT FROM (to_jsonb(OLD)-'enabled')
        OR (NOT OLD.enabled AND NEW.enabled) THEN
        RAISE EXCEPTION 'HTTP connection is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_http_connection BEFORE UPDATE OR DELETE ON http_connections
    FOR EACH ROW EXECUTE FUNCTION pin_http_connection();
ALTER TABLE action_jobs DROP CONSTRAINT action_jobs_scope_id_connection_id_fkey;
ALTER TABLE action_jobs ADD COLUMN telegram_target_id uuid GENERATED ALWAYS AS
    (CASE WHEN action->>'adapter'='telegram.send_message.v1' THEN connection_id END) STORED;
ALTER TABLE action_jobs ADD COLUMN http_target_id uuid GENERATED ALWAYS AS
    (CASE WHEN action->>'adapter'='http_request.v1' THEN connection_id END) STORED;
ALTER TABLE action_jobs ADD CHECK(coalesce(action->>'adapter' IN ('telegram.send_message.v1','http_request.v1'),false));
ALTER TABLE action_jobs ADD FOREIGN KEY(scope_id,telegram_target_id) REFERENCES telegram_connections(scope_id,id);
ALTER TABLE action_jobs ADD FOREIGN KEY(scope_id,http_target_id) REFERENCES http_connections(scope_id,id);
ALTER TABLE action_jobs ADD COLUMN http_status integer CHECK(http_status BETWEEN 200 AND 299);
ALTER TABLE action_jobs DROP CONSTRAINT action_jobs_check2;
ALTER TABLE action_jobs ADD CHECK(
    CASE WHEN action->>'adapter'='http_request.v1' THEN
        remote_message_id IS NULL AND (status='sent')=(http_status IS NOT NULL)
    ELSE http_status IS NULL AND (status='sent')=(remote_message_id IS NOT NULL) END);
-- Generated targets are derived from immutable action/connection_id; BEFORE triggers
-- see their NEW values before calculation, so exclude them from the JSON comparison.
CREATE OR REPLACE FUNCTION pin_action_job() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW)-ARRAY['status','attempts','claim_token','lease_until','next_attempt_at',
         'failure_code','remote_message_id','http_status','telegram_target_id','http_target_id','updated_at','retry_generation']) IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['status','attempts','claim_token','lease_until','next_attempt_at',
         'failure_code','remote_message_id','http_status','telegram_target_id','http_target_id','updated_at','retry_generation']) THEN
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
-- No default destinations, grants, sends or historical replay.

-- Two JSON string layers can expand a 64 KiB request fourfold; leave bounded
-- room for URL/action/job metadata too. Outgoing request limits are unchanged.
ALTER TABLE action_retry_requests DROP CONSTRAINT action_retry_requests_review_check;
ALTER TABLE action_retry_requests ADD CHECK(jsonb_typeof(review)='object' AND octet_length(review::text)<=327680);
