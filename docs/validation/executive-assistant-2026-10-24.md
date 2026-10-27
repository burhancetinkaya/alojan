# Executive-assistant conversation repair — 2026-10-24

Tasks M4-01 / M5-03; US-02, US-06 and US-08; ADR 0007 owner refinement.

## Observed defect

Reviewed the latest completed carrier call's stored recognition, delivered-speech
records and content-free timing logs. No raw recording was enabled or listened to.
A concrete product question was dismissed with an unsupported support redirect;
no note was stored. Repeated generic invitations prolonged the closing. One
interrupted response had empty aligned text, so it must not be treated as fully
heard. Recognition also contained unclear words; this change does not establish
what those words actually were or claim an ASR repair.

The prior agent's model turns in that call took approximately 0.5–1.1 seconds.
The principal defect under review was conversational behavior rather than delay.
No private transcript, caller number, call identifier or credential is included
in this report. Replays use synthetic products, people and messages.

## Change

Kübra's role is a concise, attentive senior executive assistant. Concrete product
problems addressed to Burhan Bey are usable requests to store, even when she
cannot answer them herself. A topic announcement alone is not a message. Preserve
known details, acknowledge storage without readback, and do not invent support
routes, calendar facts or callback commitments. Keep GPT-OSS 120B / Cerebras,
medium reasoning, temperature 0.2, Responses streaming and the bounded tool loop.

Replace the blanket thanks/question repeat with a narrower intake guard: a bare
thanks with no note and a delivered non-optional question clarifies locally.
Optional-invitation wording and handled requests reach contextual completion.
The guard is a limited text heuristic, not general intent or ASR-confidence
classification; typed pending-question intent is its upgrade condition.

The speech boundary removes observed generic invitation patterns: after durable
storage it uses a short acknowledgement; without a durable note it requests a
correction within the existing five-step bound. Observed unsupported callback
claims receive bounded truthful wording rather than another model roundtrip. A
storage acknowledgement requires a durable note ID; otherwise only uncertainty
is stated. Closing repairs preserve the farewell. These finite
checks are not a general semantic guarantee against every paraphrase. Notes,
cancellation, sent-audio history, tool validation and the three-second closing
delay retain their existing boundaries.

## Comparative evaluation

All live-model measurements use Linux and real OpenRouter calls with synthetic
conversation history; note saves in the conversation replay are in memory. They
are not handset or database persistence measurements. State checks verify note
presence and completion; manual review additionally inspects wording, preserved
facts and unsupported promises. Passing the former alone does not prove quality.

The original profile passed 15/20 replay state checks. Exploratory expanded
prompts improved some cases but still produced generic invitations, premature
thanks-closing, missing essential questions or callback promises. A high-reasoning
trial reached 4,445 ms and did not resolve all quality issues, so it was rejected.
The final revision uses the shorter role prompt and bounded speech checks above.

The 11-conversation release replay passed 33/33 note/completion state checks,
including unresolved intake, handled thanks, a new request after thanks,
correction plus exit, topic-only requests and instruction-override attempts.
Three turns used local guards. The 30 model-driven turns averaged 894 ms, with
maximum 2,055 ms to completed validated speech (in-memory note saves). Observed
generic invitation patterns did not reach speech in this release replay.
Manual review still found an omitted product-name question and an inappropriate
callback-inability disclaimer; the latter received one additional observed-pattern
check plus focused unit/live-model rechecks. Rejecting these claims back to the
model caused two repair failures (one above three seconds); the final bounded
truthful repair avoids that additional model roundtrip. State scores do not hide these
wording limitations. A meeting-date question also received an overly generic
return-time uncertainty answer in one exploratory replay.

Real API + isolated PostgreSQL + simulated playback receipts passed note storage,
unconfirmed status, closing and structured post-call summary before the final
callback-claim boundary extension. Real native PCMA loopback with CUDA ASR/EMA,
OpenRouter and isolated PostgreSQL subsequently passed two turns, stored an
unconfirmed note, closed and generated a summary. First audio after the two turn
endpoints was 1,939 ms and 720 ms. A second phrase in turn one began at 4,559 ms
because the preceding 2,600 ms of speech was playing; that is not first-response
latency. This is synthetic local audio, not a carrier listening result.

The final bounded repair does not alter the native media path. Final focused
tests passed on Linux: **101 passed in 7.63 s**, covering contextual thanks,
local nonspeech guards, bounded speech repair with/without durable storage,
closing repair, reasoning isolation, cancellation, wire settings, note persistence
and latency accounting. Ruff check and format check passed; `git diff --check`
passed. The graph was refreshed without a persisted artifact.

The final focused callback replay completed 5/5 note/completion decisions,
maximum 1,765 ms, but manual review found a new callback-guarantee paraphrase.
That exact observed paraphrase was added to the bounded repair and covered by
two durable/non-durable regression cases in the 101-test result above. It was not
counted as a clean language-quality pass. A general paraphrase-proof guarantee
is explicitly not claimed.

## Remaining acceptance

Senior-assistant quality is not established by scripted state checks alone.
Follow-up detail collection and wording still need owner listening on the real
line. The product-name question was omitted in some synthetic conversations;
the known problem remained stored and a volunteered product could update it.
Model-chosen intent/closing and unrecognized promise paraphrases remain quality
risks. No production-readiness, full G3, carrier listening or soak gate is closed.

## Development activation

Reloaded only the agent after checking the latest carrier call had closed and
there were no recent active database calls. GPT-OSS 120B / Cerebras / medium
remains selected. Agent, ASR and TTS health checks returned SERVING; the existing
native gateway process remained running. Previous source and logs are retained
under ignored `.local/rollbacks/executive-assistant-20261024/`. No carrier call was
placed by this task; owner listening on the new version remains pending.
