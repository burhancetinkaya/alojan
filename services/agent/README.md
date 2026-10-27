# Agent service (M4)

## Operator maintenance fence

Both legacy and managed launchers support `ALOJAN_WORKER_ADMISSION_FILE`. While
fenced, new setup/turn requests are denied; existing work and required cancel/end/
release/playback bookkeeping finish normally. Maintenance readiness accounts for
active RPCs, leases, calls, turn and initialization tasks and legacy summary work.
Legacy summaries pause new claims without dropping queued jobs; current work finishes.
Cancellation cleanup errors cannot be discarded and then reported as idle. Ordinary
Agent health retains its existing meaning, and no HTTP service is added.

The maintenance receipt covers this process's inference work, not external provider
execution, unrelated action/summary workers, database reconciliation or a global GPU
reservation. See the [operator sequence](../../docs/DEV_SETUP.md#dependent-worker-maintenance-fence).

The staged AGP-03 path preloads immutable runtime and greeting/unavailable PCM
from the release, then pins them at private initialization. It supplies business identity/instructions,
configured recovery/repair text, selected note alias/guidance, model settings and
history/output/turn budgets. Post-call summaries resolve the same historical
release. These consumers have scripted inference, real HTTP-transport mocking,
loopback gRPC and disposable PostgreSQL coverage. No management/configuration IO
is added to a conversational turn. A shared client transport is retained.

Ordinary initialization still returns `ready_for_answer=false`. Routed RunTurn now
requires a pinned runtime/route/audio bundle, an explicit readiness permit and a
persisted answer. The private readiness coordinator can now supply that permit
after preflight; tests exercise it through the full native Session. The descriptions below apply
to the existing legacy entry point. `legacy.py` preserves its main/summary prompts
for migration/rollback; it is never a fallback for an unknown routed number. Remove
it after accepted migration and the rollback window. General tools, per-agent credentials, MCP and post-call actions still need their
consumer gates and production coordination.

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
carrier call or notification. `tests/test_managed_summary_live.py` applies the same
correction/ambiguity assertions to the scoped worker with an immutable published
release and restricted credentials. It also verifies completion without action jobs,
notification outbox entries or MCP executions. Both require the same explicit opt-in
and use only disposable records. Evidence is private; do not commit generated output.


## Staged multi-agent initialization

AGP-03 adds private InitializeCall/CancelCallSetup boundaries backed by CallRouter.
The normal entry point remains legacy-only; no routing enable flag exists yet.
An explicitly constructed routing service returns readiness false. RunTurn accepts
only an active call with a readiness permit, persisted answer and all release pins,
preventing a new profile from falling through to legacy identity/tools. See the [RPC contract](../../proto/README.md)
and [implementation evidence](../../docs/CALL_TEST_PLAN.md).

The deployed managed-call lease and acknowledgement logic is preserved. Optional
`ALOJAN_RECONCILE_AFTER_SECONDS` is 0 (disabled) or 300–86400; when enabled the worker
checks every 30 seconds, reclaiming up to 100 stale initializing and 100 stale active
rows per pass. Stale setup ends without summary/outbox; only stale active calls get
the existing recovery summary job. A row's recovery timestamp is not a measured
hangup time. Never enable a new routed runtime without its consumers and recovery.

## Prepared release preload (AGP-03, staged)

`PreparedReleases` belongs to the agent event loop. A trusted preload coordinator
will supply an authoritative scope/release/manifest/digest and a private local asset
root installed by `alojan.voice_assets`. Call `await cache.preload(...)` before
passing the cache to `AgentService(..., router=..., prepared=cache)`. This is an
internal contract, not a management endpoint or production configuration flag.
The normal entry point remains unchanged. This step does not produce DB readiness;
that requires native playback and all voice dependencies to acknowledge the release.

The loader traverses `<root>/<scope UUID>/<speech digest>` with directory descriptors
and no-follow opens, validates the exact manifest and bounded WAV bytes, then keeps
immutable mono PCM16 8 kHz data. It never synthesizes or opens caller-supplied paths.
The shared validator rejects incomplete RIFF/chunk lengths even with matching
hashes. Filesystem/format errors expose a generic preload failure, not private paths.

Defaults are 16 cached releases and 16 MiB accounted payload (PCM plus conservative
text allowance); object overhead is separately bounded by entry count. At most two
loads run concurrently, duplicate requests coalesce and a third distinct load is
rejected. Cancelled waiters do not cancel worker tasks or create unlimited threads.
A failing load cannot evict a valid entry. Admission performs no filesystem reads,
PCM decoding or prompt compilation. It pins exact scope/release/digest data; a cache
miss is a setup failure even when the DB readiness row is valid. No legacy fallback.

Calls retain their pin until setup cancellation or lease release/expiry. LRU eviction
excludes all pinned releases; disk replacement cannot change active PCM. Shutdown
rejects new work and waits for outstanding local-file loads; existing call references
stay valid until normal teardown. Asset roots must be trusted local storage, not an
unbounded network mount. Close the cache after closing call leases. Routed native
playback, readiness production and real model/voice acceptance remain rollout gates.

`GetPreparedAudio` exposes only the live call's exact pinned release/digest over
the private leased/deadlined boundary. It copies the verified greeting/unavailable
PCM without filesystem, DB or model access. Cancellation/release removes access.
The agent send limit is 1,000,000 bytes for two at-most-30-second clips; request
size remains 16,384 bytes and RPC concurrency remains 16. These are protocol caps,
not user tuning. Native transfer/playback tests cover two distinct agent packs,
maximum valid payload and malformed/late replies. See the [contract](../../proto/README.md).
This component does not activate the normal entry point or acknowledge readiness.

## Scoped records and finalization (AGP-03/05, staged)

Migration `0009_scoped_call_records.sql` adds RLS to calls and their child records,
leased ownership on the existing summary queue, and immutable `call.finalized.v1`
records. Ownership derives from `call_route_snapshots`, never from caller/model data
or the latest draft. New routed summaries cannot enter the global legacy Telegram
outbox; the legacy summary poller selects only unscoped jobs.

`Store.for_route(route)` returns the private `CallRecords` repository. It checks the
complete immutable routing identity and locks the call before writing. It requires
an answered active call for utterances/notes, detects conflicting retries, and ends
the call with its scoped summary job in one transaction. `answered` is an internal
consumer of private ReportCallAnswered: a live lease, exact release/digest and an
explicit internal readiness permit are required. It is not a management/user endpoint.
The native isolated profile reports its observed SIP ACK and end timestamps. Duplicate
answer reports preserve the first timestamp; conflicts and timestamps outside the
call window/five-second clock-skew allowance fail. EndCall carries the same witness
to repair a missing answer write atomically; an unanswered end produces no summary.
AgentService selects this repository whenever routing is configured; a missing route
cannot fall back. Ordinary startup creates no answer permit and remains not-ready.

`CallSummaries.process_one(backend)` claims one job using `SKIP LOCKED`, with a new
fencing token and a 60-second lease. No transaction remains open during model work.
The model deadline comes from the pinned qualified engine preset (at most 20 seconds).
Database work runs on worker threads with 3-second statements, 1-second locks and
5-second transactions. Expired claims can be reclaimed; old workers cannot finish.
Cancellation/infrastructure errors leave a recoverable lease. An explicit provider
429 in the scoped worker defers the existing fenced claim for 60–300 seconds, up to
three total claims. Retry-After seconds/HTTP dates are honored within that ceiling;
malformed or longer delays terminate instead of retrying earlier. Other model/schema/
24 KiB output failures remain terminal with an explicit null summary. Confirmation
comes from the latest durable note, never from the summary model's assertion.

Summary, immutable event and queue completion commit atomically. A repeated completed
claim is rejected and cannot create a second event. Events include the pinned agent/
owner identity, number provenance, timing/outcome, latest durable note and summary;
they exclude raw transcripts, audio, credentials and internal prompts. The event has
a 64 KiB database ceiling. Custom extraction and tool-output fields are not enabled.

Provision separate unprivileged roles with `alojan.roles --purpose records` and
`--purpose summaries` using private migration credentials. The records role has no
notification/finalization/model-output permission. The summaries role can discover
pending scoped jobs across workspaces, but reads conversation data only after binding
the claimed workspace inside a transaction; it cannot mutate conversation records.
Neither role can provision users, routes or readiness. Combining their grants is rejected.

This is a tested private repository/one-job worker boundary, not an activated worker
service. Dedicated worker process/deployment, bounded infrastructure retry/dead-letter
policy, action configuration/fan-out/Telegram delivery and final runtime integration
remain pending. Do not migrate the live database or activate routing with this step:
existing legacy database roles must be audited for the new forced RLS, and the old
agent worker must be upgraded before introducing scoped summary jobs. Privileged
migration credentials are for provisioning/testing, never the new runtime credential.


The existing optional reconciliation loop now dispatches through AgentService. Legacy
mode touches only unscoped rows. Routed mode uses the admission role to discover at
most 16 stale routes for its configured node, then the separate records role binds
each original scope and rechecks age/state under a call lock. It records missing end
or abandoned setup explicitly; unknown hangup duration remains null. Only answered
calls enqueue post-call work. Age remains 300–86400 seconds (greater than the current
hard call limit), polling every 30 seconds. Lost release/cancellation cannot manufacture
an answer. Rerun dedicated-role provisioning for the added started_at read and
failure/event-write grants before testing this integration. No live grant change is
performed automatically. Calls still need the remaining consumers/readiness gates
before normal routed startup can be enabled.


## System-owned output budgets

EnginePreset.output pins phrase characters/bytes, phrase count and total turn bytes
for the call. Users select qualified models; they do not set these technical controls.
The shared phrase policy preserves the existing punctuation/abbreviation rules and
splits Unicode strings before encoding. Publication and completed speech tools reject
text that cannot fit the selected budget; streaming independently enforces the budget
before emitting each phrase. Rejected output does not emit a successful end marker or
create a completed playback receipt. Existing cancellation and storage behavior remain.

Historical presets without output keep canonical digests and frozen v1 limits
(240 characters/1024 bytes per phrase, 16 phrases/4096 bytes per turn). New revisions
store explicit limits, bounded by those fixed ceilings. Optional agent_output.sql
is disabled until qualification. Native managed consumers require the complete schema-v1
output message; update both peers/generated bindings together. TTS's 512-character
ceiling, bounded queues and discarded provider free-text limit remain fixed security
policy. Production routed RunTurn is still blocked until the remaining consumers and
readiness gates are complete.


## Routed conversational lifecycle (AGP-03, isolated)

RunTurn consumes the initialized Call and rejects missing/ended/revoked/unanswered
pins. Supplied caller metadata must match initialization; it cannot replace the pinned
identity. Ordinary startup has no coordinator and cannot issue a readiness permit. Tests connect native
Session to scoped records and synthetic inference without enabling a production route.

ReportCallAnswered marks a call usable only after the scoped write succeeds and its
lease/Call identity is rechecked. EndCall revokes conversational admission, cancels
generations and awaits any active turn's cleanup within the existing 1.8-second RPC
budget before finalizing records/summary work. Timeout is an error, not a successful
end; reconciliation remains necessary after process/RPC failure. Shielding prevents an
EndCall deadline from interrupting cleanup of an already-cancelled note/model task.
Release/setup cancellation removes the answered pin. No new RPC, DB schema, dependency
or management lookup is added to the conversational path.


## Node-local release readiness (AGP-03)

`ReleaseReadiness` attaches to an explicitly constructed routed AgentService with a
matching node-specific ReadinessRepository and private ASR/TTS channels. Trusted
deployment code calls `await coordinator.activate(scope, release)` before binding a
verified number, runs `coordinator.run(stopping)` as a background task, and awaits
`coordinator.close()` before closing its cache/channels. Neither browser input nor a
model tool may call this boundary directly. The legacy executable does not construct
this coordinator. The explicit managed entry point below is for isolated acceptance.

Activation reads an enabled workspace's immutable release and qualified model from
the database, claims a fresh consumer ID, validates/preloads installed PCM and pins
the exact release in memory. Real ConfigureCall probes exercise recognition vocabulary
and TTS capability matching using ephemeral leases without inference; all known leases
must be released successfully. Final health and record-writer checks precede the ready
receipt. Backend checks validate local model/settings/client availability only; they do
not spend an API request or prove provider credentials, quota, model quality or latency.

Each receipt belongs to one `(scope, release, node, digest, consumer)` and expires in
10 seconds in PostgreSQL. Admission also needs this process's matching cache entry and
a monotonic local receipt no older than two seconds. A restart cannot trust an earlier
process's DB row. A successor claim fences old renewals/withdrawals; a still-running
old process stops new admission when its local receipt expires or renewal fails.
This is bounded propagation, not an instantaneous distributed fencing guarantee.

The background loop checks health/storage and renews enabled, qualified targets;
it never reloads audio, configures speech or runs inference on warm refresh. A failed
refresh clears local admission immediately; a missed refresh expires it automatically.
Existing admitted calls retain their release, answer permit and service leases.
Shutdown clears admission before any awaited cleanup and withdraws only owned rows.
The database row may remain visible until its TTL after loss of connectivity, but
cannot independently authorize calls. No tool-grant revocation protocol is implied.

Migration 0010 adds the nullable consumer ID without changing historical rows. Apply
it before provisioning the dedicated readiness role; management/routing/record roles
cannot write consumer IDs. Readiness has no user, call-record, binding or delivery
privileges and has a restrictive node policy in addition to workspace RLS. The old
`assistant_profiles.enabled` field is not the managed activation switch; number
bindings, workspace state, release qualification and consumer readiness control it.

Missing/corrupt assets, configuration/health failure, capacity, cancellation or lost
cleanup acknowledgement cannot publish local readiness. Unknown lost-open tokens
remain subject to the existing 300-second speech lease expiry; no automatic retry of
activation is performed. Readiness entries hold existing bounded cache pins, preventing
an apparently ready release from being evicted. General credentials/tools/actions,
and production qualification remain pending; isolated startup is now wired below.

## Explicit managed deployment entry point

`python -m alojan_agent.managed --config /absolute/private/managed-node.json` runs
the same AgentService with separate routing/records/readiness credentials, the existing
bounded prepared cache, private speech channels and readiness coordinator. See
[deployment setup](../../docs/DEV_SETUP.md#explicit-managed-node-startup-isolated-agp-03)
and `infra/examples/managed-node.json`. Operator-selected targets are immutable release
IDs, never a query selecting all published agents. Unknown/duplicate fields, invalid
ports/identifiers, empty/oversized target sets and unavailable assets fail closed.

All targets pass startup preflight before RPC serving. The port is exclusive before
receipt claims; restart obtains new consumer IDs. Failed startup/stop withdraw only
this process's receipts. Stop signals are coalesced so cancellation cannot interrupt
receipt cleanup. Generation/RPC teardown precedes cache/channel/client closure.
The existing scoped reconciliation loop runs at a fixed 600-second recovery age,
30-second interval. It preserves uncertain/missing end evidence, not invented answers.

No legacy summary or notification loop runs in managed mode. Scoped jobs are consumed
by the independent summary worker below. Managed model credentials now come only from
the pinned scoped connection. Configured actions and real quality/performance/carrier
acceptance remain required before live migration. No default launcher, resident service,
second-number route, model instance or user-facing engine control is changed.

## Scoped credentials and independent summary worker

Managed Backend requires ProviderClients and rejects legacy client/model overrides.
The immutable runtime carries the trusted route's workspace and release's opaque
model_connection. Prepare/refresh decrypts an identity-bound envelope using a separate
read-only DB role and external key. Model selection is memory-only, with at most 16
clients and two-second freshness. Pending refresh preserves still-fresh access; failed
or missed refresh blocks later requests, including later turns of existing calls.
Already-dispatched requests are not recalled. Model/preset options stay call-local
even when agents intentionally share a connection. No raw key enters a runtime/prompt.

`python -m alojan_agent.summary_worker` runs independently under services/action-worker
and infra/compose.worker.yaml. It consumes scoped leased jobs, loads historical
release/records, prepares that connection and finalizes once using CallSummaries.
Clients open/close per sequential job so historical references cannot exhaust the
voice cache. Model/credential failure is explicit; infrastructure failure/cancellation
preserves the lease. Finalization cannot invent confirmation and atomically schedules
only the pinned release's reviewed action projections. A separate delivery_worker
process enforces live original authority and handles Telegram receipts/uncertain sends;
the summary worker never reads Telegram credentials. Neither worker has media, an RPC
listener or a management server. See [delivery behavior](../action-worker/README.md).
See [setup](../../docs/DEV_SETUP.md#scoped-provider-credentials-and-separate-summary-worker).

## Real post-call acceptance

Managed and explicit legacy summaries use the same platform summary policy. A saved
note does not override later corrections or create a new request to update the note.
The policy requires final meaning, independent items, unresolved ambiguity and Turkish
handover text. These are model instructions, not deterministic semantic guarantees.
The current candidate still fails expanded real final-meaning cases and must not be
activated on the basis of scripted output tests alone.

`tests/test_declared_outputs_live.py` exercises the actual scoped summary worker and
provider with synthetic conversations, eight typed fields, pinned release definitions,
unknowns and malicious instructions. It performs no action/tool delivery. The explicit
opt-in/evidence directory setup and remaining quality failures are documented in
[real acceptance](../../docs/validation/real-outputs-receiver-2026-10-26.md).

## MCP call runtime (AGP-07)

Optional read-only MCP tools are pinned in manifest version 3. The existing managed
launcher enables them when `ALOJAN_MCP_DATABASE_URL` (the dedicated execution role)
is configured. Use the existing private `ALOJAN_CREDENTIAL_KEY_FILE` for purpose-bound
MCP bearer credentials. There is no operator endpoint allowlist: workspace owners
can save canonical public HTTPS MCP endpoints and request discovery themselves.
DNS/IP pinning, private-address rejection, TLS verification, redirect rejection,
bounded responses and per-agent tool grants still apply. Missing credentials fail
startup. Absent executor configuration leaves MCP-free agents unchanged; an MCP
release cannot become ready without an executor. Never use the management,
owner/migration or provider-credential role as the MCP DSN.

The existing readiness heartbeat refreshes grant/review/connection/issuer state and
compares selected tools to the latest recorded discovery. Local permission freshness
expires within two seconds from refresh start. A refresh failure invalidates that
MCP entry immediately; its release loses local admission while unrelated ready
releases continue. Shared speech/DB deadline failures retain global fail-closed
behavior. Revocation can prevent subsequent requests and cancel a waiting request;
it cannot retract data already sent to an authorized server. No remote catalog,
profile or permission query runs per dialogue turn. Starting/completing an actual
invocation uses the bounded asynchronous journal; RTP/media callbacks do not wait.

System-owned initial bounds (qualification required before raising):

- Sixteen prepared permission entries; expired entries are reclaimed. Up to eight
  explicitly selected tools per release, 64 KiB authorization snapshot.
- Four in-flight MCP operations per node, two per dialogue turn, eight per call;
  excess requests fail immediately with no queue or retry.
- Four-second operation deadline including journal/handshake/call/result persistence;
  two-second SDK reads, one-second connect. Cancellation cleanup waits at most
  0.5 seconds plus a bounded 0.8-second outcome write. A non-cooperative transport
  retains its node slot until it actually exits.
- One isolated authenticated session per invocation; no cross-workspace pool.
  Approved endpoint, vetted/pinned public DNS address, original Host/TLS SNI,
  certificate verification, no proxy/redirect/compression, 256 KiB response limit,
  16 KiB SSE event bound. Protocols 2025-11-25 and 2025-06-18, no sampling/elicitation/root handlers.
- Fixed parameters are absent from the model schema and cannot be overridden.
  Runtime/combined inputs and structured output use the approved bounded schemas;
  payloads are at most 8 KiB. Grant v3 / release v9 (`bounded.v2`) also supports
  schema-less JSON-object output, including one JSON text block when structured
  content is absent. Arbitrary text/images/resources/metadata are ignored.
  UUID/date-time input formats are validated; no typed output projection is available
  without a declared output schema.
  Literal credential echoes and invalid structured outputs fail without persisting
  their contents. Successful typed data remains untrusted model input.

Call scope/profile/release, answered/open database state, turn identity and local
permission freshness fence execution. A 50 ms cooperative monitor cancels outstanding
work when the call/turn/permission becomes invalid; late results cannot enter a newer
turn. No tool execution retries occur, including after a lost response. Summary workers
prepare only model credentials and do not require MCP readiness; revocation therefore
does not prevent an otherwise available call summary.

Shortcut: drift checks use the latest explicit discovery, not a remote catalog fetch
on every call. Operators must rediscover/review server changes; unnoticed server-side
behavior changes are not detected by a matching stored schema. Upgrade with a qualified
server-revision attestation mechanism if a provider supports it. Read-only review is
an operator trust decision, not a guarantee inferred from remote annotations.

These are candidate-only integration controls. Linux tests use disposable scoped
schemas, synthetic speech/inference and mock HTTP transports through the actual SDK.
Real approved-server TLS/behavior, GPU/carrier latency and multi-call load acceptance
remain pending; no performance superiority is claimed by these bounds.
