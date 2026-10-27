-- AGP-06: durable, bounded audio requests; only a private worker changes state.
CREATE TABLE voice_preparation_jobs (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    preparation_id uuid NOT NULL,
    attempt integer NOT NULL CHECK (attempt BETWEEN 1 AND 3),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','preparing','ready','failed')),
    failure_code text CHECK (failure_code IN ('superseded','generation_failed','interrupted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (preparation_id,attempt),
    FOREIGN KEY (scope_id,profile_id,preparation_id)
        REFERENCES agent_preparations(scope_id,profile_id,id)
);
CREATE UNIQUE INDEX one_active_voice_preparation ON voice_preparation_jobs(preparation_id)
    WHERE status IN ('queued','preparing');
CREATE INDEX pending_voice_preparations ON voice_preparation_jobs(created_at,id)
    WHERE status IN ('queued','preparing');
ALTER TABLE voice_preparation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_preparation_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON voice_preparation_jobs
    USING (scope_id = nullif(current_setting('alojan.scope_id',true),'')::uuid)
    WITH CHECK (scope_id = nullif(current_setting('alojan.scope_id',true),'')::uuid);
