-- Optional repeatable development example. No live qualification or routing.
INSERT INTO engine_presets(id,revision,configuration,digest)
VALUES ('initial-voice-v1',1,'{"allow_fallbacks": false, "answer_delay_ms": 3000, "asset_max_duration_ms": 30000, "asset_sample_rate_hz": 8000, "base_url": "https://openrouter.ai/api/v1", "closing_delay_ms": 3000, "greeting_pad_ms": 400, "history_max_bytes": 12000, "llm_max_retries": 0, "llm_timeout_seconds": 15, "max_call_seconds": 120, "max_call_turns": 16, "max_tokens": 4096, "media_drain_ms": 150, "model": "openai/gpt-oss-120b", "model_steps_per_turn": 5, "parallel_tool_calls": false, "provider": "cerebras", "provider_store": false, "raw_recording_enabled": false, "reasoning": "medium", "reply_max_chars": 400, "reply_max_questions": 1, "reply_max_sentences": 2, "routing": "default", "schema_version": 1, "summary_input_max_bytes": 12000, "temperature": 0.2, "tracing_enabled": false, "turn_timeout_seconds": 20, "voice_model_revision": "e7c96f2fc0ba843cd0f86e02786655bb56f50df8"}'::jsonb,'ea971dcd5914281d89425535dd00e18693a8ba44ffe303cce19bdc6827c46a6a')
ON CONFLICT DO NOTHING;
INSERT INTO model_catalog(id,revision,display_name,preset_id,preset_revision)
VALUES ('gpt-oss-120b-cerebras',1,'GPT OSS 120B · Cerebras','initial-voice-v1',1)
ON CONFLICT DO NOTHING;
INSERT INTO model_catalog_status(model_id,model_revision,enabled,qualification_ref)
VALUES ('gpt-oss-120b-cerebras',1,false,'pending-runtime-and-performance-qualification')
ON CONFLICT DO NOTHING;
