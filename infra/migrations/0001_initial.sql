CREATE TABLE calls (
    id uuid PRIMARY KEY,
    sip_call_id text NOT NULL,
    direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    status text NOT NULL,
    from_number_e164 text,
    from_number_source text NOT NULL DEFAULT 'unknown',
    to_number_e164 text,
    redirecting_number text,
    started_at timestamptz NOT NULL DEFAULT now(),
    answered_at timestamptz,
    ended_at timestamptz,
    duration_ms bigint CHECK (duration_ms >= 0),
    codec text,
    hangup_reason text,
    failure_code text
);
CREATE TABLE utterances (
    id uuid PRIMARY KEY,
    call_id uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    speaker text NOT NULL CHECK (speaker IN ('caller', 'assistant')),
    text text NOT NULL,
    is_final boolean NOT NULL DEFAULT false,
    confirmed boolean NOT NULL DEFAULT false,
    audio_sent_start_ms bigint CHECK (audio_sent_start_ms >= 0),
    audio_sent_end_ms bigint CHECK (audio_sent_end_ms >= audio_sent_start_ms),
    source_generation_id text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE call_events (
    id uuid PRIMARY KEY,
    call_id uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    timestamp timestamptz NOT NULL DEFAULT now(),
    generation_id text,
    duration_ms bigint CHECK (duration_ms >= 0),
    value double precision,
    metadata_jsonb jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE call_summaries (
    call_id uuid PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    caller_name text,
    subject text NOT NULL,
    summary text NOT NULL,
    urgency text NOT NULL CHECK (urgency IN ('low', 'medium', 'high')),
    requested_action text,
    confirmation_status text NOT NULL,
    json_schema_version integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE action_items (
    id uuid PRIMARY KEY,
    call_id uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    type text NOT NULL,
    description text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'done')),
    owner_approved_at timestamptz
);
CREATE TABLE notes (
    id uuid PRIMARY KEY,
    call_id uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    note_version integer NOT NULL CHECK (note_version > 0),
    text text NOT NULL,
    confirmed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (call_id, note_version)
);
CREATE TABLE notification_outbox (
    id uuid PRIMARY KEY,
    call_id uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    target text NOT NULL,
    payload_jsonb jsonb NOT NULL,
    retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    last_error text
);
CREATE INDEX utterances_call ON utterances(call_id, created_at);
CREATE INDEX call_events_call ON call_events(call_id, timestamp);
CREATE INDEX outbox_due ON notification_outbox(next_attempt_at) WHERE delivered_at IS NULL;
