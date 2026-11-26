-- OUT-02/04. Each row is one request, pinned to a verified release binding.
CREATE TABLE outbound_calls (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    requested_by uuid NOT NULL REFERENCES users(id),
    operation_key uuid NOT NULL,
    request_digest bytea NOT NULL CHECK(octet_length(request_digest)=32),
    number_id uuid NOT NULL,
    binding_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    release_id uuid NOT NULL,
    node_id text NOT NULL,
    caller_e164 text NOT NULL,
    destination text NOT NULL CHECK(destination ~ '^\+90[2345][0-9]{9}$'),
    message text CHECK(length(message) BETWEEN 1 AND 2000),
    ring_timeout_seconds integer NOT NULL CHECK(ring_timeout_seconds BETWEEN 1 AND 120),
    post_playback_seconds integer NOT NULL CHECK(post_playback_seconds BETWEEN 0 AND 30),
    status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','preparing','dialing',
        'answered','completed','busy','no_answer','rejected','interrupted','failed','uncertain')),
    queued_at timestamptz NOT NULL DEFAULT now(),
    answered_at timestamptz, ended_at timestamptz, failure_code text,
    FOREIGN KEY(scope_id,number_id,binding_id,profile_id,release_id,node_id)
        REFERENCES number_bindings(scope_id,number_id,id,profile_id,release_id,node_id),
    FOREIGN KEY(scope_id,number_id,caller_e164) REFERENCES phone_numbers(scope_id,id,e164),
    UNIQUE(scope_id,operation_key)
);
CREATE INDEX outbound_history ON outbound_calls(scope_id,queued_at DESC,id DESC);
CREATE INDEX outbound_pending ON outbound_calls(node_id,queued_at,id) WHERE status='queued';
CREATE UNIQUE INDEX outbound_one_active ON outbound_calls(node_id)
    WHERE status IN ('preparing','dialing','answered');
ALTER TABLE outbound_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbound_calls FORCE ROW LEVEL SECURITY;
CREATE POLICY outbound_scope ON outbound_calls
USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid)
WITH CHECK(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);

-- Minimal replay receipt survives erasure of the call and its private metadata.
CREATE TABLE outbound_receipts (
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    operation_key uuid NOT NULL,
    id uuid NOT NULL,
    request_digest bytea NOT NULL CHECK(octet_length(request_digest)=32),
    PRIMARY KEY(scope_id,operation_key)
);
ALTER TABLE outbound_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbound_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY outbound_receipt_scope ON outbound_receipts
USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid)
WITH CHECK(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
