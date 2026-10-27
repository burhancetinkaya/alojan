-- AGP-02: native accounts and revocable sessions, independent of live voice.
CREATE TABLE users (
    id uuid PRIMARY KEY,
    login text UNIQUE NOT NULL CHECK (login ~ '^[a-z0-9][a-z0-9_.-]{2,63}$'),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 100),
    password_hash text NOT NULL CHECK (length(password_hash) BETWEEN 100 AND 256),
    enabled boolean NOT NULL DEFAULT true,
    password_version integer NOT NULL DEFAULT 1 CHECK (password_version > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE workspace_memberships (
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    user_id uuid NOT NULL REFERENCES users(id),
    role text NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_id, user_id)
);
CREATE INDEX memberships_user ON workspace_memberships(user_id, scope_id);
CREATE TABLE auth_sessions (
    token_hash bytea PRIMARY KEY CHECK (octet_length(token_hash) = 32),
    user_id uuid NOT NULL REFERENCES users(id),
    password_version integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '12 hours'
);
CREATE INDEX auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX auth_sessions_expiry ON auth_sessions(expires_at);
CREATE TABLE auth_rate_limits (
    key_hash bytea PRIMARY KEY CHECK (octet_length(key_hash) = 32),
    attempts integer NOT NULL CHECK (attempts > 0),
    expires_at timestamptz NOT NULL
);
CREATE INDEX auth_rate_limits_expiry ON auth_rate_limits(expires_at);
CREATE TABLE workspace_invitations (
    token_hash bytea PRIMARY KEY CHECK (octet_length(token_hash) = 32),
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    login text NOT NULL CHECK (login ~ '^[a-z0-9][a-z0-9_.-]{2,63}$'),
    role text NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '24 hours',
    consumed_at timestamptz
);
CREATE INDEX workspace_invitations_expiry ON workspace_invitations(expires_at);
CREATE TABLE management_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id uuid REFERENCES users(id),
    scope_id uuid REFERENCES recipient_scopes(id),
    event text NOT NULL CHECK (length(event) BETWEEN 1 AND 100),
    target_id uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);
-- No seeded users, memberships, credentials, routes or external grants.
