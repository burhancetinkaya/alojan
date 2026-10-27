-- Optional next immutable revision; never mutates/activates the historical v1 example.
-- Native calibration is operator-owned. Qualify before enabling; publish a new release.
INSERT INTO engine_presets(id,revision,configuration,digest)
VALUES ('initial-voice-v1',2,'{"allow_fallbacks": false, "answer_delay_ms": 3000, "asset_max_duration_ms": 30000, "asset_sample_rate_hz": 8000, "base_url": "https://openrouter.ai/api/v1", "calibration": {"candidate_ms": 250, "incomplete_ms": 2200, "interrupt_max_quiet_ms": 800, "interrupt_min_voice_ms": 192, "interrupt_sustained_quiet_ms": 160, "interrupt_sustained_voice_ms": 640, "interrupt_vad_percent": 50, "open_ms": 500, "partial_hint": true, "schema_version": 1, "silence_reminder_ms": 7000, "uncertain_ms": 1200, "vad_percent": 50, "yes_no_ms": 350}, "closing_delay_ms": 3000, "greeting_pad_ms": 400, "history_max_bytes": 12000, "llm_max_retries": 0, "llm_timeout_seconds": 15, "max_call_seconds": 120, "max_call_turns": 16, "max_tokens": 4096, "media_drain_ms": 150, "model": "openai/gpt-oss-120b", "model_steps_per_turn": 5, "parallel_tool_calls": false, "provider": "cerebras", "provider_store": false, "raw_recording_enabled": false, "reasoning": "medium", "reply_max_chars": 400, "reply_max_questions": 1, "reply_max_sentences": 2, "routing": "default", "schema_version": 1, "summary_input_max_bytes": 12000, "temperature": 0.2, "tracing_enabled": false, "turn_timeout_seconds": 20, "voice_model_revision": "e7c96f2fc0ba843cd0f86e02786655bb56f50df8"}'::jsonb,'bbc7de58993cb56824e6690a3877408be6b08620c6f9e72da348f996a1cbc4c1')
ON CONFLICT DO NOTHING;
INSERT INTO model_catalog(id,revision,display_name,preset_id,preset_revision)
VALUES ('gpt-oss-120b-cerebras',2,'GPT OSS 120B · Cerebras','initial-voice-v1',2)
ON CONFLICT DO NOTHING;
INSERT INTO model_catalog_status(model_id,model_revision,enabled,qualification_ref)
VALUES ('gpt-oss-120b-cerebras',2,false,'pending-native-calibration-and-performance-qualification')
ON CONFLICT DO NOTHING;
