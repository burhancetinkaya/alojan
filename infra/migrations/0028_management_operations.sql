-- MCP-04: transactionally durable identities for management mutations.
CREATE TABLE management_operations (
    user_id uuid NOT NULL REFERENCES users(id),
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    operation_key uuid NOT NULL,
    request_digest bytea NOT NULL CHECK (octet_length(request_digest)=32),
    -- NULL is a compact tombstone: an old key must never execute a second mutation.
    result jsonb,
    status integer NOT NULL CHECK (status BETWEEN 200 AND 299),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id,scope_id,operation_key)
);
CREATE INDEX management_operations_expiry ON management_operations(created_at);
ALTER TABLE management_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE management_operations FORCE ROW LEVEL SECURITY;
CREATE POLICY management_operations_scope ON management_operations
USING (scope_id=NULLIF(current_setting('alojan.scope_id',true),'')::uuid)
WITH CHECK (scope_id=NULLIF(current_setting('alojan.scope_id',true),'')::uuid);
