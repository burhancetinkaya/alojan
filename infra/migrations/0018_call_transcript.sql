-- AGP-06 / P1: deterministic bounded transcript pages; no media write-path change.
SET LOCAL lock_timeout = '200ms';
SET LOCAL statement_timeout = '3s';
CREATE INDEX utterances_call_transcript ON utterances(call_id,created_at,id)
WHERE is_final AND (speaker='caller' OR (speaker='assistant' AND audio_sent_end_ms>audio_sent_start_ms));
