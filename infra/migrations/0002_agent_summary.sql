ALTER TABLE call_summaries ADD COLUMN detail_jsonb jsonb NOT NULL DEFAULT '{}';
CREATE TABLE summary_jobs (
    call_id uuid PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'failed')),
    attempts integer NOT NULL DEFAULT 0,
    failure_code text
);
CREATE UNIQUE INDEX utterance_generation_speaker ON utterances(call_id, source_generation_id, speaker);
