# Natural closing without duplicate acknowledgement — 2026-10-24

M4-01 / M5-03; US-02/05/06/08; ADR 0007 owner follow-up.

## Finding and change

The latest completed carrier conversation contained a storage acknowledgement,
then a caller's thanks, then another storage acknowledgement in the farewell.
Only one note version existed. Reviewed stored recognition and completed-speech
records; no raw audio recording was enabled or listened to. No private caller
transcript, number, call identifier or secret is included here.

Added ten executive-assistant prohibitions to the system prompt, adapted from
[the documented research](../AGENT_CONDUCT.md). Natural variation does not mean
repeating the same fact with synonyms. Do not reintroduce, re-request known
information, over-apologize, reopen closing, invent commitments or dismiss an
in-scope request. New information, explicit repeat requests and interrupted audio
remain valid reasons for a relevant follow-up.

The code now associates every emitted phrase with its durable note version.
Completed receipts for observed acknowledgement phrases advance a separate
acknowledgement version; interrupted receipts do not. A late older receipt cannot
acknowledge a correction. A repeated storage announcement in closing becomes a
short social farewell only when that current version was already acknowledged.
Callback-claim and generic-invitation repair paths also avoid re-announcing that
version. No additional model request, external write, schema or protocol change.

## Linux validation

- Focused regression suite: **108 passed in 7.71 s**. Includes full gRPC flow for
  acknowledged versus interrupted speech, delayed/duplicate receipts, call
  isolation, corrected note versions and repair-path repetition. Confirmation
  remains false; acknowledgement receipt alone neither confirms nor closes.
- Ruff check and format check passed (11 agent/test files); diff whitespace check
  passed. Knowledge graph refreshed without creating a tracked graph artifact.
- Real GPT-OSS 120B/Cerebras medium-reasoning replay: **13/13 note/completion state
  checks** across five synthetic conversations. Mean first phrase **1,066 ms**,
  maximum **1,930 ms**, including in-memory note saves and gRPC overhead. Completed
  playback receipts were simulated. Four eligible closing turns contained no
  repeated acknowledgement. An explicit repeat request was answered; a new
  question stayed open and a corrected note retained the requested detail.
- The correction-and-exit case stored the correction but chose only a farewell;
  it was not counted as a new acknowledgement. State success is not a blanket
  language-quality pass.
- Native synthetic PCMA loopback with real CUDA ASR/EMA, OpenRouter and isolated
  PostgreSQL passed note storage, closing and post-call summary. First audio at
  the two turn endpoints: **1,659 / 1,540 ms**. This is local audio integration,
  not a new carrier listening pass.

## Limits and deployment

Receipt text matching recognizes observed Turkish acknowledgement forms, not all
semantic paraphrases. Completed output does not prove the caller heard it. Existing
ASR, detail-follow-up, model-intent, G3 and soak limitations remain open. No claim
of human-assistant equivalence is made. New owner listening on the carrier line
remains pending. Model, provider, reasoning and the three-second post-farewell
delay remain unchanged.

Development activation: reloaded only the idle agent after checking carrier
closure and recent database activity. Agent, ASR and TTS returned SERVING; the
existing native gateway stayed running. Prior agent source (backend, models,
service) and log are retained under ignored
`.local/rollbacks/natural-closing-20261024/`. Local and Linux source hashes match.
No Git commit, push or carrier call was performed by this task.
