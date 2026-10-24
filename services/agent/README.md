# Agent service (M4)

## Current Docker deployment

The owner-selected runtime is [Docker Compose](../../docs/DOCKER.md), under
[ADR 0011](../../docs/ADR/0011-docker-runtime.md). Use that guide for startup,
private configuration, health checks and recovery. Native commands below remain
development and rollback references; do not start a duplicate worker beside the
container using the same port or GPU model.

A private loopback gRPC service uses OpenAI Agents SDK 0.24.0 against OpenRouter's
Responses endpoint, with owner-selected `openai/gpt-oss-120b`, reasoning `medium`,
and Cerebras-only routing without provider fallback. There is no SDK tracing,
stored Responses state or automatic retry. GPT-OSS cannot disable reasoning;
temperature is 0.2 and verbosity is omitted. Raw model text is never forwarded:
`respond(text)` and `finish_call` supply bounded, validated speech through actual
tool calls. Tool selection remains required after note storage. The SDK still
streams model responses, but TTS waits for complete validated speech arguments,
then the existing phrase queue splits and plays the reply. See the latest
[Linux evaluation and rollout status](../../docs/validation/gpt-oss-reasoning-2026-10-24.md)
and ADR 0005; earlier Mac prompt-only failures remain recorded separately.
The pinned client versions and hashes are in `uv.lock`. See ADR 0005.

Each call owns bounded conversational context (12,000 UTF-8 bytes of recent
complete utterances), at most 16 turns and 16 phrases per turn. SDK runs permit
five tool/model steps, 4096 output tokens per step including reasoning, and 4096
raw output text bytes per
turn. Responses are emitted as short phrase-sized `text_delta` events. Only
completed output-port phrases become assistant context; interrupted phrases keep
an empty text with the measured sent duration. This is sent audio, not proof of
handset playback. The callback never performs RPC/DB/API work.

`take_note` writes only local PostgreSQL notes, idempotently on call/version.
Under owner-approved ADR 0007, Kübra acts as a warm, concise senior executive
assistant. A successful `take_note` returns the durable result to the model,
which chooses `respond` for an acknowledgement/follow-up or `finish_call` when
the caller has finished, including contextual thanks after a handled request. Identical already-durable notes reuse the
saved result; no repeated database IO is necessary. Storage alone
never closes the call. A usable message is saved before optional contact-detail
questions. A topic announcement or a wish to ask a product question first needs
its actual question/request; it is not a complete message. A concrete product
problem/question addressed to Burhan Bey is a usable request to save, even though
the assistant cannot provide technical support. Ask for an unknown product or
another essential missing detail, not for already supplied information. Avoid
generic anything-else invitations and unsupported redirects. Further additions
update the note, and no readback confirmation is requested. `confirmed=true`
remains rejected.

When the caller is done, `finish_call(reason="caller_finished", closing_text=...)`
emits the model-selected brief farewell and requests closing. Empty/oversized
closings and questions are refused. The gateway drains closing audio and waits
three seconds plus its existing 150 ms media allowance before BYE. Storage failure
cannot announce success. Owner-selected availability wording is not calendar
knowledge and must not preempt an already supplied message. If the purpose is
unknown, follow unavailability with one polite open question about the reason for
calling; never ask the generic reason again when it is already known.
Unclear or unrelated recognized answers require a short clarification and continued
listening. Thanks are interpreted with the delivered context: an essential
unanswered question still needs clarification; an acknowledged request with no
essential question pending can close politely. A question mark alone no longer
forces a repeated question. The local intake guard requires no existing note and
a delivered question without optional-invitation wording. This limited heuristic
does not classify every possible Turkish question. Known generic invitation
patterns use a short acknowledgement only when a durable note exists; otherwise
the model can correct them within the existing five-step limit. Observed callback
guarantees or inability claims use bounded truthful speech without another model
request. Acknowledgement requires a durable note ID; neither a speculative note
nor a failed write can claim storage. These finite patterns are not a general
semantic validator.
Three narrowly matched stock ASR phrases trigger a local repeat request before
any model/tool execution; existing notes are preserved and no finish is emitted.
Longer legitimate messages containing those words still reach the model. Suspect
historical text is marked unknown only in model input; the original stored
recognition remains unchanged. This finite guard is not general ASR confidence
estimation. The prompt handles other ambiguous answers; explicit exits still work.
See [clarification evidence](../../docs/validation/clarification-recovery-2026-10-23.md).

No notification, scheduling or arbitrary external tool is exposed. The separate
MCP adapter is an owner-allowlisted, approval-required Streamable HTTP boundary;
it is not attached to the phone agent or connected to live systems.

The agent emits only response speech. At the owner's request, the native gateway
now provides quiet instrumental waiting music after 800 ms until the first speech
frame is available. Music never enters this service's receipts, context or note
confirmation. It cannot extend the turn deadline.  See [waiting music provenance and behavior](../../assets/waiting/README.md).
Sanitized text-readiness logs remain distinct from handset audio measurements.

`EndCall` creates a durable summary job after gateway teardown starts. A separate
worker validates the summary schema and never upgrades the stored confirmation
status based on model opinion. Failures remain in `summary_jobs` with a sanitized
code; an owner can reset a failed job to `pending` for retry. The caller does not
wait for summary inference. The summary object cannot promise an action.

## Linux run

Install with `uv sync --frozen --project services/agent`. Keep the key in
`.local/agent.env` with permissions 0600; keep the database URL in `.local/dev.env`.
Apply migrations with the existing app API migration command first.

```sh
PYTHONPATH=services/app-api uv run --frozen --env-file .local/dev.env python -m alojan.migrate
PYTHONPATH=services/agent:services/voice-contracts:generated/python \
  uv run --frozen --project services/agent --env-file .local/dev.env \
  --env-file .local/agent.env python -m alojan_agent --port 15073
```

Select `--agent-port 15073` with adaptive turn models and barge-in on the gateway.
A fixed-capture profile is accepted solely for deterministic native integration
checks. Without `--agent-port`, existing speech tests and the live M3 profile
remain unchanged. Health means service/DB configuration, not verified provider
permissions; API and carrier acceptance are separate gates.

## Limits still requiring validation

Linux regression and synthetic actual ASR/EMA/API dialogue checks passed; see
[the evidence](../../docs/validation/linux-agent-2026-10-23.md). The agent profile is
active on the development line. The owner confirmed correct readback but reported
excessive waiting, so carrier latency acceptance remains open. M3's
incomplete-turn fallback and silent-caller reminder remain deferred by the owner;
the agent prompt alone cannot implement ASR retry timing. Call state and cancellation tombstones
are bounded at 128 calls / 4096 generations per process and fail closed at
capacity; restart supervision and lifecycle reclamation remain hardening work.
EndCall delivery is bounded/best effort at the gateway; a gateway crash before
the end RPC leaves an active DB call for later reconciliation. No M5 completion
or production readiness is implied.

## Performance review follow-up

Streaming now accepts sufficiently long comma/semicolon clauses while preserving
common title and numeric boundaries. Ordinary sentence endings remain immediate.
The previous confirmation flow is superseded by ADR 0006. Exact explicit goodbyes
still close locally without saving or confirming a note or calling the model.
Summary input retains recent complete utterances under 12,000 UTF-8 bytes.

See [measurements and remaining review findings](../../docs/validation/performance-review-2026-10-23.md).
`tools/validate-agent-call.py --adaptive --asr-port 15172 --goodbye --output DIR`
checks a synthetic early goodbye without a note. Omit
`--goodbye` for message storage, a chance to add more, and a second-turn natural farewell without confirmation; use the private env
files and a fresh output directory as described above.

A caller who declines a message or says they will call later can exit through
`finish_call(reason="caller_finished", confirmed_message=null)` without a note.
The server returns the selected farewell (or a short compatibility default) and
finish decision. Free-form model farewells no longer request closing or speech:
the model must call the actual closing tool. Exact explicit caller goodbyes still
use the local shortcut described above. Native audio completion and the closing
pause precede disconnection. This does not authorize or fabricate message delivery.


M3-01 recovery: the native gateway can send validated `input_event` metadata for
silence reminder, uncertain-input clarification or silence timeout. These local
responses bypass the LLM and tools; no synthetic caller utterance is stored.
Delivered speech uses the existing receipt path and enters assistant history.
See [contract and deployment ordering](../../proto/README.md#m3-01-recovery-input-metadata-additive-v1-convention).

## Stage latency and OpenRouter routing (M4-01 / M5-03)

`event=agent_latency data={...}` reports each admitted turn, including failures,
timeouts and cancellations. It contains a hashed call key, generation, response
versus recovery kind, DB readiness, first provider text delta, first speakable
delta, first emitted phrase, model-step start/end/text times, reported input/cache/
output tokens and local tool start/end times. Times are monotonic milliseconds
relative to turn admission, not phone audio arrival. Model steps may contain no
text when they only request a tool. Missing measurements are `-1`, not zero.
No caller text, tool arguments/results, API keys or SDK traces are logged.
The existing five-model-step limit bounds per-turn model telemetry; only the
latest turn timing is retained in call memory.

`ALOJAN_AGENT_ROUTING` accepts `default` (the selected model's base routing), `latency`
(`provider.sort=latency`), `sticky` (random per-call `session_id`) and
`latency-sticky` (both). Invalid values fail at startup. Sticky routing is a
provider preference, not a hard pin or a cache-hit guarantee. Each call has a
different opaque session; no phone number or transcript is used as the key.
All profiles retain Cerebras-only routing with fallback disabled for the GPT-OSS
candidate; latency sorting cannot expand that allowlist. The historical four-arm
comparison used the previous model's unrestricted routing. The same model,
Responses streaming, reasoning, tool policy and no-storage settings apply to all
profiles. Summary requests also retain the Cerebras pin and medium reasoning.

Run the synthetic comparison from the repository root:

```sh
uv run --frozen --env-file .local/agent.env python tools/benchmark-agent-routing.py \
  --rounds 3 --output .local/routing-comparison.json
uv run --frozen python tools/report-latency.py \
  .local/logs/agent.log .local/logs/netgsm-gateway.log
```

The comparison rotates profile order across three two-turn scenarios. It uses
the real API, an in-memory synthetic store and simulated playback receipts;
it excludes ASR/TTS, durable database time and carrier transport. Shared provider
caches are not flushed. Compare behavior failures, typical/tail latency and
observed cache usage; do not call an absent cache counter a cache miss. The report
excludes recovery/music/failed turns from successful latency distributions and
reports failures/missing samples separately.

## Delivered acknowledgements and natural closing

The [conduct rules](../../docs/AGENT_CONDUCT.md) distinguish useful new information
from paraphrasing a completed action. Each emitted phrase snapshots the durable
note version. Only a completed playback receipt for a recognized acknowledgement
advances the call's acknowledged-note version. Late receipts retain their original
version; interrupted speech does not advance it. This is neither a caller readback
confirmation nor a claim of handset perception.

If the current note was already acknowledged, closing and repair paths omit its
storage announcement and preserve a short farewell. An updated note remains
eligible for acknowledgement, and an explicit repeat request can be answered.
Known patterns are finite; the prompt handles broader conversational repetition.
No extra API call is added. See the [natural-closing evidence](../../docs/validation/natural-closing-2026-10-24.md).

### One further-help invitation

Under the latest ADR 0007 refinement, ask for another topic once after handling
the request and essential details. Completed playback sets a per-call flag that
survives note updates. Unheard invitations can be retried; explicit exit remains
valid. Ordinary thanks before the invitation keeps listening with the question.
Known invitation paraphrases are detected at the speech boundary; repeated
invitations require a corrected model response. This finite detector is not a
general semantic guarantee. No extra model request is needed on the normal path.

### Researched service practices

The prompt pairs existing conduct boundaries with six positive practices from
primary-source service and conversation-design guidance: contextual listening,
specific empathy, plain language, focused recovery, truthful next steps and faithful
corrections. See [source mapping](../../docs/AGENT_CONDUCT.md). The ISO overview
provides framework context only; this is not a conformity claim. Product identity
is an essential detail before offering further help for product/account problems.
No voice model, tool authorization, media timing or recording policy changes.

### Synthetic dialogue review

Run the explicit real-API evaluator on the primary Linux host:

```sh
uv run --frozen --env-file .local/dev.env --env-file .local/agent.env python tools/evaluate-agent-dialogue.py --output .local/dialogue-review.json
uv run --frozen --env-file .local/dev.env --env-file .local/agent.env python tools/evaluate-agent-dialogue.py --cases tests/fixtures/agent/dialogue-review-holdout.json --output .local/dialogue-review-holdout.json
```

This uses the pinned agent model, loopback gRPC, the existing in-memory test store
and synthetic completed-playback receipts. It incurs API usage but makes no carrier
call or durable business write. Results stay private; failures return nonzero.
Review replies and note contents against each fixture's rubric: automatic phrase
checks alone miss semantic failures and are not a quality certification. The second
set was held out from the first prompt revision; after review it is a regression
set, not permanently unseen data. Prompt security guidance does not redact raw
caller transcripts or remove secrets from model inputs.

### Dialogue-quality candidate (M4-01/02)

The development candidate adds private `acknowledges_saved_note` intent metadata
to `respond` and `finish_call`. This does not change protobuf, database schemas or
the number of model requests. A model flag cannot authorize storage: the agent
checks the durable note, binds the accepted response to its note version, and
requires completed playback for every phrase in the response before marking its
acknowledgement heard. Late receipts cannot acknowledge a newer note. Partial or
cancelled response groups do not qualify. This conservative rule can leave an
acknowledgement unmarked when its following question was interrupted.

The old phrase detector remains a defensive check and compatibility fallback for
backends without explicit intent; its vocabulary was not extended. Intent tags
can still be semantically wrong, so real-model review remains necessary. Summary
input now labels chronological utterances and decodes the durable note into an
object; it does not automatically replace caller intent with a potentially stale
saved note. The existing worker still enforces confirmation status from storage.

The candidate is evaluated separately from the running listener. Release status
and limitations are recorded in
[the dialogue-quality validation](../../docs/validation/dialogue-quality-2026-10-24.md).
Run `tests/test_agent_ack_intent.py` and `tests/test_agent_update_failure.py` with
the existing agent suite. `tests/test_agent_summary_live.py` additionally requires
`ALOJAN_REAL_SUMMARY=1`, `ALOJAN_SUMMARY_EVIDENCE_DIR`, real API access and the
isolated test database fixture. It makes external inference requests but no
carrier call or notification. Evidence is private; do not commit generated output.


### Consolidated development snapshot

The main consolidation combines the dialogue-quality candidate with the grounded
reply guard. `respond` accepts both `acknowledges_saved_note` and `repeat_requested`;
a repeat exception does not bypass durable-save or playback accounting. The merged
prompt retains the same model/provider/settings. It is not identical to the current
live agent: [publication evidence](../../docs/validation/main-publication-2026-10-24.md)
records the remaining quality failures. Publishing source does not activate it.


## Post-call Telegram notifications (M5-01)

An independent `python -m alojan_agent.notifications` process now consumes ended
calls through the PostgreSQL outbox. It exposes no conversational tool and does
not change the agent prompt or voice lifecycle. Pair the owner's private chat and
activate the channel explicitly using [Telegram setup](../../docs/TELEGRAM.md).
Bot credentials and recipient files stay under ignored `.local/` with mode 0600.
