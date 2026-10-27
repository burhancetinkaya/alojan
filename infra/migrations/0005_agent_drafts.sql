-- AGP-02: optimistic editing; published profile revisions remain immutable.
CREATE TABLE agent_drafts (
    scope_id uuid NOT NULL,
    profile_id uuid PRIMARY KEY,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object' AND octet_length(content::text) <= 65536),
    updated_by uuid NOT NULL REFERENCES users(id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (scope_id,profile_id) REFERENCES assistant_profiles(scope_id,id),
    UNIQUE (scope_id,profile_id)
);
ALTER TABLE agent_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_drafts FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_drafts_scope ON agent_drafts
    USING (scope_id = nullif(current_setting('alojan.scope_id',true),'')::uuid)
    WITH CHECK (scope_id = nullif(current_setting('alojan.scope_id',true),'')::uuid);

-- RLS for legacy profile storage is activated with the compatible runtime rollout,
-- not here: the single-profile production agent has not set a workspace context.
