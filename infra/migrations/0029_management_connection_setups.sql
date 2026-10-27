-- MCP-04: authenticated browser handoffs, without storing plaintext credentials.
CREATE TABLE management_connection_setups (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    personal_token_id uuid NOT NULL REFERENCES personal_access_tokens(id),
    kind text NOT NULL CHECK(kind IN ('provider','telegram','http','mcp')),
    configuration jsonb NOT NULL CHECK(jsonb_typeof(configuration)='object'),
    connection_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '30 minutes'
);
CREATE INDEX management_setups_owner ON management_connection_setups(scope_id,user_id,created_at);
ALTER TABLE management_connection_setups ENABLE ROW LEVEL SECURITY;
ALTER TABLE management_connection_setups FORCE ROW LEVEL SECURITY;
CREATE POLICY management_setups_scope ON management_connection_setups
USING(scope_id=NULLIF(current_setting('alojan.scope_id',true),'')::uuid)
WITH CHECK(scope_id=NULLIF(current_setting('alojan.scope_id',true),'')::uuid);
