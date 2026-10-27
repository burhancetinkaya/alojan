-- AGP-03/05 foundation: derive record ownership from the immutable call route.
ALTER TABLE call_route_snapshots ADD UNIQUE(scope_id,call_id,release_id);
ALTER TABLE summary_jobs ADD COLUMN scope_id uuid;
ALTER TABLE summary_jobs ADD COLUMN release_id uuid;
ALTER TABLE summary_jobs ADD COLUMN claim_token uuid;
ALTER TABLE summary_jobs ADD COLUMN lease_until timestamptz;
ALTER TABLE summary_jobs DROP CONSTRAINT summary_jobs_status_check;
ALTER TABLE summary_jobs ADD CHECK(status IN ('pending','processing','done','failed'));
ALTER TABLE summary_jobs ADD CHECK ((scope_id IS NULL) = (release_id IS NULL));
ALTER TABLE summary_jobs ADD CHECK ((claim_token IS NULL) = (lease_until IS NULL));
ALTER TABLE summary_jobs ADD CHECK ((status='processing') = (claim_token IS NOT NULL));
ALTER TABLE summary_jobs ADD FOREIGN KEY(scope_id,call_id,release_id)
    REFERENCES call_route_snapshots(scope_id,call_id,release_id);
UPDATE summary_jobs j SET scope_id=s.scope_id,release_id=s.release_id
    FROM call_route_snapshots s WHERE s.call_id=j.call_id;
CREATE FUNCTION pin_summary_job() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE route record;
BEGIN
    IF TG_OP='UPDATE' AND (NEW.call_id,NEW.scope_id,NEW.release_id)
        IS DISTINCT FROM (OLD.call_id,OLD.scope_id,OLD.release_id) THEN
        RAISE EXCEPTION 'Summary ownership is immutable' USING ERRCODE='23514';
    END IF;
    SELECT scope_id,release_id INTO route FROM call_route_snapshots WHERE call_id=NEW.call_id;
    IF FOUND THEN
        IF (NEW.scope_id IS NOT NULL AND NEW.scope_id<>route.scope_id) OR
           (NEW.release_id IS NOT NULL AND NEW.release_id<>route.release_id) THEN
            RAISE EXCEPTION 'Summary ownership mismatch' USING ERRCODE='23514';
        END IF;
        NEW.scope_id := route.scope_id;
        NEW.release_id := route.release_id;
    ELSIF NEW.scope_id IS NOT NULL THEN
        RAISE EXCEPTION 'Summary route missing' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_summary_job BEFORE INSERT OR UPDATE ON summary_jobs
    FOR EACH ROW EXECUTE FUNCTION pin_summary_job();
CREATE INDEX scoped_summary_due ON summary_jobs(status,lease_until,call_id) WHERE scope_id IS NOT NULL;
CREATE TABLE call_finalizations (
    call_id uuid PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    scope_id uuid NOT NULL,
    release_id uuid NOT NULL,
    event_type text NOT NULL DEFAULT 'call.finalized.v1' CHECK(event_type='call.finalized.v1'),
    summary_status text NOT NULL CHECK(summary_status IN ('done','failed')),
    payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(scope_id,call_id,release_id) REFERENCES call_route_snapshots(scope_id,call_id,release_id)
);
CREATE TRIGGER immutable_finalization BEFORE UPDATE ON call_finalizations
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();
DO $$
DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['calls','utterances','notes','call_events','call_summaries',
                                    'action_items','notification_outbox','summary_jobs','call_finalizations'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY call_workspace ON %I USING (EXISTS '
            '(SELECT 1 FROM call_route_snapshots s WHERE s.call_id=%I.%I '
            'AND s.scope_id=nullif(current_setting(''alojan.scope_id'',true),'''')::uuid))',
            relation,relation,CASE WHEN relation='calls' THEN 'id' ELSE 'call_id' END);
    END LOOP;
END;
$$;
-- The legacy global destination must never receive routed call output.
CREATE FUNCTION reject_routed_legacy_notification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM call_route_snapshots WHERE call_id=NEW.call_id) THEN
        RAISE EXCEPTION 'Routed calls require configured actions' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER reject_routed_legacy_notification BEFORE INSERT OR UPDATE ON notification_outbox
    FOR EACH ROW EXECUTE FUNCTION reject_routed_legacy_notification();
