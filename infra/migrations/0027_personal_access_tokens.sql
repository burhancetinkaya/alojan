-- MCP-02: personal management credentials; no tokens or permissions are seeded.
CREATE TABLE personal_access_tokens (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 80),
    secret_hash bytea NOT NULL CHECK (octet_length(secret_hash) = 32),
    permissions text[] NOT NULL CHECK (cardinality(permissions) BETWEEN 1 AND 12),
    password_version integer NOT NULL CHECK (password_version > 0),
    audience text NOT NULL DEFAULT 'alojan-management' CHECK (audience = 'alojan-management'),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    last_used_at timestamptz,
    CHECK (expires_at > created_at AND expires_at <= created_at + interval '90 days')
);
CREATE INDEX personal_tokens_owner ON personal_access_tokens(user_id, scope_id, created_at DESC);
ALTER TABLE management_audit ADD COLUMN personal_token_id uuid REFERENCES personal_access_tokens(id);
