-- Content-free gateway observations, imported outside the live media path.
CREATE TABLE call_latency (
    scope_id uuid NOT NULL,
    call_id uuid NOT NULL,
    release_id uuid NOT NULL,
    generation text NOT NULL CHECK (generation ~ '^[A-Za-z0-9_-]{1,142}$'),
    status text NOT NULL CHECK (status IN ('completed','failed','cancelled','interrupted')),
    kind text NOT NULL CHECK (kind IN ('response','recovery')),
    error_code integer NOT NULL CHECK (error_code BETWEEN 0 AND 1000),
    endpoint_silence_audio_ms integer CHECK (endpoint_silence_audio_ms BETWEEN 0 AND 600000),
    asr_finalize_ms integer CHECK (asr_finalize_ms BETWEEN 0 AND 600000),
    agent_first_phrase_ms integer CHECK (agent_first_phrase_ms BETWEEN 0 AND 600000),
    tts_first_chunk_ms integer CHECK (tts_first_chunk_ms BETWEEN 0 AND 600000),
    pcm_to_output_ms integer CHECK (pcm_to_output_ms BETWEEN 0 AND 600000),
    endpoint_to_audio_ms integer CHECK (endpoint_to_audio_ms BETWEEN 0 AND 600000),
    vad_end_to_audio_estimate_ms integer CHECK (vad_end_to_audio_estimate_ms BETWEEN 0 AND 600000),
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(call_id,generation),
    FOREIGN KEY(scope_id,call_id,release_id) REFERENCES call_route_snapshots(scope_id,call_id,release_id)
);
ALTER TABLE call_latency ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_latency FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON call_latency FOR SELECT USING
    (scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE TRIGGER immutable_call_latency BEFORE UPDATE ON call_latency
    FOR EACH ROW EXECUTE FUNCTION prevent_profile_revision_mutation();
