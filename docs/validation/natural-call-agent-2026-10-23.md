# Natural call-center conversation

Date: 2026-10-23. M4-01/02, US-02, owner-authorized ADR 0007.

## Latest real-call finding

The latest call had two caller turns and one unconfirmed saved note. The last
assistant speech was the fixed message acknowledgement alone (1720 ms). The
agent returned finish=1 on storage, followed by local call_ending and disconnect
at 32580 ms. The transport followed the prior implementation, but the owner
rejected that abrupt conversational ending. No private transcript is reproduced.

## Changes

Kübra's role now describes professional, context-sensitive call-center behavior:
listen and acknowledge, clarify uncertainty, reuse known information, preserve
message additions, offer an opportunity to continue, and end politely when the
caller is done. No message-content confirmation is reintroduced. A declined
message and a caller who already said goodbye need no forced extra question.

Remove the automatic finish and fixed speech from take_note; return its durable
result to the model. finish_call accepts optional contextual closing_text, bounded
to 400 characters; empty text and questions cannot close. Only caller_finished
requests are accepted, so a saved note alone cannot authorize tool closing.
The unchanged gateway waits for closing audio and its existing hangup pause.
The approved opening, voice, provider/model and notification deferral are preserved.

## Validation

- Mac: 50 agent/phrase tests passed, 4.53 s.
- Linux: 53 agent/phrase/DB/native closing tests passed, 35.70 s, no skips;
  one known audioop deprecation warning. Native code/binary unchanged.
- Initial real API probe asked for a missing phone number before saving. Prompt
  was clarified to save a usable message with null missing details before
  optional contact questions. A subsequent probe passed storage/addition/exit,
  decline, continued-question and already-finished-message branches. It repeated
  the anything-else invitation after an addition; the final prompt now allows
  that invitation once per call. A final real API probe passed all four scenarios
  (six turns), acknowledged the addition without repeating the question, and
  preserved the original message and addition as an unconfirmed note.
- Final Linux agent/phrase regression: 50 passed, 4.67 s. Ruff and diff whitespace
  checks passed.
- Synthetic PCMA loopback with real CUDA ASR/EMA, OpenRouter and isolated
  PostgreSQL: two turns passed. The first saved a note and kept listening; the
  second completed the farewell and local SIP termination. Post-call summary
  persisted. First response audio took 6019 ms after endpoint, final-turn audio
  3699 ms; waiting music totaled 7840 ms. This ran before the final once-only
  invitation wording adjustment; the final wording was checked by the API probe.
  The separate two-codec closing-pause regression is included in the 53 checks.
- Activated on the idle Linux development line: gateway PID 2035604, agent
  launcher PID 2035537. All three gRPC workers report SERVING; gateway is ready.
  Profile natural-v1 retains v5 opening, 3000 ms ringing and 3000 ms closing pause.
  Native binary SHA-256 remains
  bb9d5823635885d38e7df3e96de6cfa0f8d1239278f321d3b6a74c969f7a433e.
  Previous code/process profile and private logs are retained privately for rollback.

This introduces a model continuation after storage, which may add response delay.
It does not prove general human conversation quality or latency targets.
Human carrier retest of the new conversation role remains pending. No real call
was placed by this validation. Model-driven dialogue remains probabilistic; these
scenarios do not establish general conversation quality.

## Polite purpose question refinement

Owner follow-up, M4-01/02 and US-02: replace the passive message offer after
unavailability with a polite open question about the reason for calling, only
when that reason is unknown. This is a prompt-only behavior change.

Two synthetic real OpenRouter probes passed: an availability-only query received
“Hangi konuda görüşmek istemiştiniz?” and stayed open without a note; an already
supplied callback request saved an unconfirmed note without re-asking its purpose.
Audio receipts/storage were simulated for these probes, not carrier evidence.
Linux agent/phrase regression: 50 passed in 4.70 s. Ruff and whitespace checks
passed. Activated idle-line profile natural-v2, gateway PID 2060196 and agent
launcher PID 2060129; all three workers healthy and gateway ready. Opening and
native binary unchanged. New wording has not yet been verified on a handset.
