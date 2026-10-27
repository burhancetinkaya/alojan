# Clarify uncertain recognition instead of ending — 2026-10-23

Tasks M4-01/02 and M5-03; acceptance US-02/06; owner follow-up to ADR 0007.

## Finding

The latest owner-reported carrier call answered an open purpose question with a
product inquiry, according to the owner. Its stored ASR text was instead a stock
video-outro thank-you. The agent produced a farewell and requested normal closing;
no note was stored. Gateway diagnostics showed no received packet loss/reordering,
malformed input or speech fallback. This supports a recognition/interpretation
failure, not a transport disconnect. It does not establish the acoustic cause:
recording was disabled, so the actual received waveform cannot be replayed.

The same stock phrase had appeared in the preceding synthetic noise-only Whisper
evaluation. The earlier exact product-spelling map cannot repair a completely
different sentence. No private transcript, caller number, call identifier or
owner-specific vocabulary is included in this report or the regression fixtures.

## Change

Keep a bounded exact-match guard before model execution for the observed outro,
its short thank-you variant and the observed subtitle-credit phrase. Ask the
caller to repeat, emit finish=false, preserve existing notes and perform no model
or note-write call. Case/punctuation normalization uses the existing helper;
longer legitimate utterances containing these words are not discarded.

For a bare thank-you following a delivered assistant question, repeat that
question and keep listening. Explicit stop requests retain their local fast path.
The conversation prompt now asks a targeted clarification for other unclear or
unrelated answers and removes the previous instruction to close after two failed
clarifications. Repetition is permitted only for unanswered questions. The
existing turn/deadline bounds remain; silent-caller reminders and native incomplete
turn timeout behavior are not changed by this recognized-text recovery.

On subsequent model requests, suspect historical recognition is represented as
unknown speech, preventing the mistaken farewell from becoming established
caller intent. The original database record remains intact for diagnosis.
No recording, inference model, ASR decoder setting, dependency or native binary
changed. This guard prevents a known failure consequence; it cannot identify every
hallucination, recover the lost audio, or guarantee model compliance for all
unseen ambiguous answers.

## Verification

- Linux: 59 agent/phrase tests passed in 4.81 s. New tests use real loopback gRPC
  and the pinned SDK with scripted inference: no model execution on guarded text,
  no note writes, unchanged prior note, finish=false, successful next-turn recovery,
  uncertain history filtering, explicit exit and legitimate longer speech.
- An initial test run had 58 passes and one test-instrumentation failure because
  the pinned SDK supplies model input positionally. Correcting the observer's
  argument access produced the final 59 passes; production code did not change.
- Six synthetic backend scenarios passed. The two local clarification paths
  needed no API call and measured below 1 ms in the direct-backend probe. Real
  OpenRouter runs clarified an incomplete answer and unrelated small talk, kept a
  product inquiry open, and closed for an explicit declined-message exit. These
  API turns measured 5263, 5057, 6513 and 3224 ms respectively; general model
  response latency is not solved by this change.
- Synthesized product-inquiry audio through real CUDA ASR: six PCMA/PCMU cases
  at full, quarter and approximately -24 dB amplitude all retained the inquiry
  intent. Exact product spelling matched five of six; the quietest PCMA case
  still misspelled it. Unpaced service totals were 414–443 ms. This synthetic voice
  does not reproduce or validate the owner's lost handset utterance.
- A three-turn native PCMA loopback with real CUDA ASR/EMA, OpenRouter and isolated
  PostgreSQL passed: stock phrase → spoken clarification → corrected product
  inquiry/continued conversation → explicit stop/farewell/BYE. The clarification
  started playout 138 ms after ASR half-close; the second turn was 5640 ms and the
  explicit stop 139 ms. The post-call summary completed. No carrier call was made.
- Ruff lint/format checks passed for both changed Python files; diff whitespace
  checks passed. The prior whole-repository suite was not rerun for this focused
  agent behavior change.

## Development deployment

After successful integration checks and an idle-line check, the agent was restarted
with a private rollback copy. The gateway, ASR 15173, EMA 15072, approved opening,
three-second ring delay and closing pause remain unchanged. The active policy is
`natural-v3-clarification`. Human carrier retry remains pending; this is not broad
noise-quality or production acceptance. Work remains local/unpushed.
