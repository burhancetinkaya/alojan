-- Additive configuration storage. Runtime consumers are introduced separately.
CREATE TABLE recipient_scopes (
    id uuid PRIMARY KEY,
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 100),
    enabled boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE assistant_profiles (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    label text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 100),
    enabled boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_id, id)
);

CREATE TABLE assistant_profile_revisions (
    scope_id uuid NOT NULL,
    profile_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    owner_display_name text NOT NULL CHECK (
        length(owner_display_name) BETWEEN 1 AND 100 AND
        owner_display_name = btrim(owner_display_name) AND
        owner_display_name !~ '[[:cntrl:]]'
    ),
    agent_name text NOT NULL CHECK (
        length(agent_name) BETWEEN 1 AND 100 AND agent_name = btrim(agent_name) AND
        agent_name !~ '[[:cntrl:]]'
    ),
    owner_address text NOT NULL CHECK (length(btrim(owner_address)) BETWEEN 1 AND 120),
    owner_dative text NOT NULL CHECK (length(btrim(owner_dative)) BETWEEN 1 AND 120),
    owner_genitive text NOT NULL CHECK (length(btrim(owner_genitive)) BETWEEN 1 AND 120),
    language text NOT NULL DEFAULT 'tr' CHECK (language = 'tr'),
    role_description text NOT NULL CHECK (length(btrim(role_description)) BETWEEN 1 AND 2000),
    tone_description text NOT NULL CHECK (length(btrim(tone_description)) BETWEEN 1 AND 2000),
    business_context text NOT NULL DEFAULT '' CHECK (length(business_context) <= 6000),
    greeting_template text NOT NULL CHECK (length(btrim(greeting_template)) BETWEEN 1 AND 1000),
    availability_text text NOT NULL CHECK (length(btrim(availability_text)) BETWEEN 1 AND 1000),
    response_max_sentences smallint NOT NULL DEFAULT 2 CHECK (response_max_sentences BETWEEN 1 AND 5),
    response_max_chars integer NOT NULL DEFAULT 400 CHECK (response_max_chars BETWEEN 1 AND 1000),
    response_max_questions smallint NOT NULL DEFAULT 1 CHECK (response_max_questions BETWEEN 0 AND 3),
    offer_further_help boolean NOT NULL DEFAULT true,
    further_help_once boolean NOT NULL DEFAULT true,
    further_help_text text NOT NULL DEFAULT 'Başka yardımcı olabileceğim bir konu var mı?',
    clarification_text text NOT NULL DEFAULT 'Son söylediğinizi net anlayamadım, tekrar eder misiniz?',
    silence_reminder_text text NOT NULL DEFAULT 'Buradayım, sizi dinliyorum.',
    silence_timeout_text text NOT NULL DEFAULT 'Sesinizi alamıyorum. Dilerseniz daha sonra tekrar arayabilirsiniz. Hoşça kalın.',
    farewell_text text NOT NULL DEFAULT 'Rica ederim, iyi günler.',
    explicit_stop_text text NOT NULL DEFAULT 'Hoşça kalın.',
    note_ack_template text NOT NULL DEFAULT 'Talebinizi {owner_dative} iletmek üzere not aldım.',
    callback_unknown_template text NOT NULL DEFAULT '{owner_genitive} dönüş zamanı hakkında kesin bir bilgim yok.',
    summary_role_template text NOT NULL DEFAULT 'Write a concise Turkish executive handover for {owner_address}.',
    voice_ref text NOT NULL DEFAULT 'ema-default' CHECK (voice_ref = 'ema-default'),
    policy_version integer NOT NULL DEFAULT 1 CHECK (policy_version = 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_id, revision),
    UNIQUE (scope_id, profile_id, revision),
    FOREIGN KEY (scope_id, profile_id) REFERENCES assistant_profiles(scope_id, id),
    CHECK (length(btrim(further_help_text)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(clarification_text)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(silence_reminder_text)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(silence_timeout_text)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(farewell_text)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(explicit_stop_text)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(note_ack_template)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(callback_unknown_template)) BETWEEN 1 AND 1000),
    CHECK (length(btrim(summary_role_template)) BETWEEN 1 AND 2000)
);

-- A rename creates a revision; existing calls must never observe an edited revision.
CREATE FUNCTION prevent_profile_revision_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Profile revisions are immutable; insert a new revision'
        USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER immutable_profile_revision BEFORE UPDATE OR DELETE
ON assistant_profile_revisions FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();

-- A typed singleton avoids unvalidated key/value configuration and secret storage.
CREATE TABLE system_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    llm_model text NOT NULL DEFAULT 'openai/gpt-oss-120b' CHECK (length(btrim(llm_model)) BETWEEN 1 AND 200),
    llm_base_url text NOT NULL DEFAULT 'https://openrouter.ai/api/v1'
        CHECK (llm_base_url = 'https://openrouter.ai/api/v1'),
    llm_provider text NOT NULL DEFAULT 'cerebras' CHECK (length(btrim(llm_provider)) BETWEEN 1 AND 100),
    llm_allow_fallbacks boolean NOT NULL DEFAULT false CHECK (NOT llm_allow_fallbacks),
    llm_reasoning text NOT NULL DEFAULT 'medium' CHECK (llm_reasoning IN ('low', 'medium', 'high')),
    llm_temperature numeric NOT NULL DEFAULT 0.2 CHECK (llm_temperature BETWEEN 0 AND 2),
    llm_max_tokens integer NOT NULL DEFAULT 4096 CHECK (llm_max_tokens BETWEEN 1 AND 32768),
    llm_routing text NOT NULL DEFAULT 'default' CHECK (llm_routing IN ('default', 'latency', 'sticky', 'latency-sticky')),
    llm_timeout_seconds integer NOT NULL DEFAULT 15 CHECK (llm_timeout_seconds BETWEEN 1 AND 120),
    llm_max_retries smallint NOT NULL DEFAULT 0 CHECK (llm_max_retries BETWEEN 0 AND 5),
    model_steps_per_turn smallint NOT NULL DEFAULT 5 CHECK (model_steps_per_turn BETWEEN 1 AND 20),
    summary_model_steps smallint NOT NULL DEFAULT 1 CHECK (summary_model_steps BETWEEN 1 AND 5),
    max_call_turns integer NOT NULL DEFAULT 16 CHECK (max_call_turns BETWEEN 1 AND 128),
    max_active_agent_turns integer NOT NULL DEFAULT 2 CHECK (max_active_agent_turns BETWEEN 1 AND 50),
    max_retained_call_contexts integer NOT NULL DEFAULT 128 CHECK (max_retained_call_contexts BETWEEN 1 AND 10000),
    history_max_bytes integer NOT NULL DEFAULT 12000 CHECK (history_max_bytes BETWEEN 1024 AND 1000000),
    summary_input_max_bytes integer NOT NULL DEFAULT 12000 CHECK (summary_input_max_bytes BETWEEN 1024 AND 1000000),
    turn_timeout_seconds integer NOT NULL DEFAULT 20 CHECK (turn_timeout_seconds BETWEEN 1 AND 120),
    summary_timeout_seconds integer NOT NULL DEFAULT 20 CHECK (summary_timeout_seconds BETWEEN 1 AND 120),
    input_max_bytes integer NOT NULL DEFAULT 4096 CHECK (input_max_bytes BETWEEN 1 AND 16384),
    output_max_bytes integer NOT NULL DEFAULT 4096 CHECK (output_max_bytes BETWEEN 1 AND 16384),
    context_max_bytes integer NOT NULL DEFAULT 1024 CHECK (context_max_bytes BETWEEN 1 AND 16384),
    grpc_max_message_bytes integer NOT NULL DEFAULT 16384 CHECK (grpc_max_message_bytes BETWEEN 16384 AND 1048576),
    max_call_seconds integer NOT NULL DEFAULT 120 CHECK (max_call_seconds BETWEEN 10 AND 3600),
    answer_delay_ms integer NOT NULL DEFAULT 3000 CHECK (answer_delay_ms BETWEEN 0 AND 30000),
    closing_delay_ms integer NOT NULL DEFAULT 3000 CHECK (closing_delay_ms BETWEEN 0 AND 10000),
    media_drain_ms integer NOT NULL DEFAULT 150 CHECK (media_drain_ms BETWEEN 0 AND 1000),
    note_max_chars integer NOT NULL DEFAULT 1500 CHECK (note_max_chars BETWEEN 1 AND 10000),
    subject_max_chars integer NOT NULL DEFAULT 160 CHECK (subject_max_chars BETWEEN 1 AND 1000),
    summary_max_chars integer NOT NULL DEFAULT 3000 CHECK (summary_max_chars BETWEEN 1 AND 20000),
    db_connect_timeout_seconds integer NOT NULL DEFAULT 3 CHECK (db_connect_timeout_seconds BETWEEN 1 AND 30),
    db_statement_timeout_ms integer NOT NULL DEFAULT 3000 CHECK (db_statement_timeout_ms BETWEEN 100 AND 30000),
    require_ai_disclosure boolean NOT NULL DEFAULT true CHECK (require_ai_disclosure),
    require_durable_note_before_ack boolean NOT NULL DEFAULT true CHECK (require_durable_note_before_ack),
    require_external_write_approval boolean NOT NULL DEFAULT true CHECK (require_external_write_approval),
    require_scope_isolation boolean NOT NULL DEFAULT true CHECK (require_scope_isolation),
    raw_recording_enabled boolean NOT NULL DEFAULT false CHECK (NOT raw_recording_enabled),
    provider_store_enabled boolean NOT NULL DEFAULT false CHECK (NOT provider_store_enabled),
    tracing_enabled boolean NOT NULL DEFAULT false CHECK (NOT tracing_enabled),
    parallel_tool_calls boolean NOT NULL DEFAULT false CHECK (NOT parallel_tool_calls),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (max_active_agent_turns <= max_retained_call_contexts),
    CHECK (llm_timeout_seconds <= turn_timeout_seconds)
);
INSERT INTO system_settings (id) VALUES (1);
