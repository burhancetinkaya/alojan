# Agent configuration completeness audit

## 2026-10-27 — Instruction variables (AGP-06/09, CFG-01)

Main agent instructions now support optional per-agent literal variables and
reserved identity/time fields through UI, API and management MCP. Release-v10
snapshots pin definitions/timezone; each model turn renders against a single trusted
clock sample with no network/database lookup. Syntax/name/timezone/expanded-size
validation preserves the platform policy boundary; old templates remain literal.
Greeting/audio, summaries and tool guidance keep their existing template contracts.
See [ADR 0011](ADR/0011-self-service-voice-agents.md) and
[authoring contract](../services/app-api/README.md#instruction-variables).


## Scoped delivery operations (2026-10-25)

AGP-05 / CFG-07/15 now exposes workspace/agent-bound delivery metadata and owner-only
retry review. Exact original action/target, selected rendered text and payload digest
are reviewed before explicit duplicate-risk acceptance. No current draft, caller input,
replacement grant, arbitrary field or destination override can change a past delivery.
The request ID is idempotent, review generation prevents stale consent reuse, and the
original grant/target plus enabled requester ownership are checked before dispatch.
Three manual rounds/five attempts and polling/rate limits remain platform policy;
users never tune retries. No receipt fabrication or raw transcript exposure is added.


## Reviewed Telegram action selection (2026-10-25)

AGP-05 / CFG-07/15: drafts now select bounded Telegram actions, fixed workspace targets
and explicit output fields. Owner consent pins exact agent/workspace, operation, target
and data scope. Editing cannot broaden a prior grant; rollback cannot replace revoked
authority. V2 manifests pin grants with same-agent/workspace FKs. No tokens or untrusted
execution expressions enter manifests. Empty actions preserve historical v1 digests.
The authoring/consent and scoped delivery consumers are implemented. Finalization
atomically projects only reviewed fields into immutable release/grant-bound jobs.
The independent dispatcher rechecks live authority, fences attempts, bounds rendering
and networking, and never automatically retries uncertain writes. V2 compilation now
requires the exact workspace. Telegram origin, queue/rate/deadline caps, labels and
retry safety are fixed platform policy, not settings users must optimize. Actual bot
acceptance, manual-retry UI and matched voice performance remain pending.

## Telegram connection authoring (2026-10-25)

AGP-05 / CFG-07/15: fixed bot/chat destinations are now encrypted workspace records
with owner-only creation/revocation and metadata-only reads. Model and Telegram token
purposes cannot be interchanged. Existing runtime roles cannot read Telegram tokens.
No static/global Telegram target is consumed by this new API. Agent action selection,
explicit grants, payload-field configuration, finalized-event fan-out and delivery
remain pending; connection storage alone never authorizes an external write.

## Provider connection and summary worker consumers (2026-10-25)

AGP-02/03/05 / CFG-04/07/15: drafts/releases now carry an opaque model_connection.
New managed deployment requires a scoped enabled connection, never a global-key
fallback. Historical omission keeps canonical digests unchanged. Owners create/revoke
encrypted connections through write-only API controls; management cannot select
ciphertext. Decryption checks workspace/reference/provider identity using a separate
reader and external key file. At most 16 clients are prepared outside turns.

Two-second freshness bounds revocation; existing requests are not recalled, and storage
outage can block later turns. The independent summary worker uses each job's historical
connection/instructions and scoped records. Cancellation preserves leased work; failed
credentials/model output produce explicit failed finalizations without delivery.
General tools/actions, in-place key rotation, UI and real quality/PERF remain pending.

## Current readiness coordination (2026-10-25)

AGP-03 now produces consumer-owned DB receipts from authoritative releases, validated
preloaded audio, speech configuration probes and fresh local dependency checks. The
standard AgentService issues ready_for_answer only with a matching fresh coordinator
pin; no test override is needed for the new native Session scenario. Legacy startup
still has no coordinator. This supersedes earlier statements that all permits are
scripted, not the production activation/qualification gates.

Readiness rejects expired/missing/corrupt assets, wrong voice workers, disabled models/
workspaces, failed record-writer permissions and superseded consumers. Warm refresh
uses no asset regeneration or model inference. Active calls retain their original
pins. Explicit operator-selected deployment startup now uses `alojan_agent.managed`,
with bounded versioned configuration, separate DB roles, startup rollback, restart
revalidation and shutdown/reconciliation. Legacy startup remains separate. General
tools/actions and real quality/PERF remain incomplete. Provider connection selection
is a business credential choice, not a performance tuning control.

## Current routed Session integration (2026-10-25)

AGP-03 / CFG-05/06/08/09/10/11/12/17 now connects native Session to the existing
pinned ASR/agent/TTS consumers through an opt-in loopback-only conversation profile.
Greeting/unavailable audio, business identity, speech policy, timing/calibration,
output limits, service leases and scoped records remain tied to the initial release.
The normal InitializeCall readiness gate remains closed. Earlier sections describing
full Session wiring as pending are historical; production coordination, per-agent
credentials/general tool/action execution and qualification remain pending.

The prepared greeting starts immediately after ACK; conversational capture waits for
answer persistence. Native cleanup keeps pins alive until final generation
invalidation/receipts finish; the agent finalizes only after cancelled
turn cleanup. Two-workspace tests check identity, release/scope, note and summary-job
isolation; CPU interruption verifies partial speech is not stored as fully delivered.
No user-facing performance controls, new schema, new dependency or external delivery.

Date: 2026-10-25. Review of local source and the target design; implementation status below.
Authority: [ADR 0011](ADR/0011-self-service-voice-agents.md).
This is a blocking checklist for AGP-02–09, not a claim that constants were removed.

## Superseding ownership decision

The latest owner request changes the purpose of this audit: remove accidental
hard-coded business identity/behavior and centralize technical optimization; do
not expose every source constant to users. The inventory below identifies where
values are consumed, not a requirement for user-editable controls.

| CFG groups | User-facing fields | System-managed fields |
|---|---|---|
| 01–02 | Identity, business instructions, tone, greeting/farewell/availability and further-help preference | Recovery safeguards and truthful completion semantics |
| 03 | None | Intent dictionaries, hallucination/recovery detection, matching policy |
| 04 | Approved model/provider connection selection | Model-specific reasoning, temperature, tokens, routing, retries/deadlines |
| 05–06 | Natural-language brevity/style preference | Context/truncation, turn/phrase/byte limits and validation |
| 07 | Business output fields and summary content | Schema complexity/size caps and extraction validation |
| 08–10 | None initially | Ringing, call safety duration, RTP timeout, closing/drain, VAD, silence, interruption/echo calibration |
| 11–12 | Business vocabulary/pronunciation corrections | ASR decoder/cadence/utterance budget, TTS seed/chunking/normalization |
| 13 | Approved greeting/fallback/farewell text/assets | Lead-in, waiting playback timing/level and validated asset format |
| 14–15 | Tool selection/business config, destinations, grants, output mapping and action conditions | Technical timeout/retry/queue policy and execution security |
| 16–17 | None | Admission/rate budgets, lifecycle reclamation, RPC/resource/recovery limits |
| 18 | Permitted output-sharing choices | Privacy/security enforcement, retention and logging limits |

`engine_presets` centralizes immutable tested technical values. The agent release
pins the selected model's preset automatically; operators optimize/roll out presets,
users do not adjust VAD, tokens or milliseconds. Consumers still require typed
bounds and full tests. Physical/protocol constants may remain in code; optimized
settings may be fixed in a versioned preset. The desired invariant is no accidental
business constant or hidden conflicting default, not zero literals in source.

## Scoped record and summary consumer status (AGP-03/05 partial)

Records now validate the complete pinned route, answered state and idempotent content.
Forced database RLS covers calls and children. Leased summary work loads the historical
release, enforces durable-note confirmation and atomically creates a bounded finalization
event with agent/owner names, number provenance and call timing. Legacy summary polling
excludes scoped jobs and legacy global notification insertion rejects routed calls.
CFG-07/18 remain partial: custom extraction/output mapping, record-access HTTP endpoints,
retention/export and conversational runtime activation are not implemented. Native
ACK/end persistence and node-scoped recovery now have isolated SIP/DB evidence, with
exact release fencing and lost-write repair. The independent worker service and
configured action fan-out/delivery remain AGP-05 gates.

## Python consumer implementation status (AGP-03 partial)

CFG-01/02/04/05 and portions of CFG-06/07/14/15/17 now have call-local Python
consumers and regression evidence. The shared runtime compiler resolves business
identity/text, rejects incompatible speech combinations and pins the qualified
engine preset. Agent-authored instructions cannot expose an unselected note tool.
Summary identity comes from the historical call snapshot after draft/binding changes.
No settings lookup or management API request is introduced into the turn path.

CFG-13 now has verified Python PCM preload, exact call pinning, private lease-bound
PCM transfer and native playback through the existing PJMEDIA output adapter.
Tests cover real Python/C++ transfer, PJSIP media ports and isolated native INVITE
selection/answer/CANCEL with scripted readiness. The actual agent/cache/router/DB
path still rejects answer and cleans up its initializing record. Production readiness,
runtime integration and routed activation remain pending.

These are not completed end-to-end CFG gates. Production routed conversation,
calibration qualification, per-agent secrets, general tool/MCP executors and configured
post-call delivery remain pending. Scoped records and isolated prepared playback
have the evidence described above; production wiring remains gated. The normal entry point
still uses the explicit legacy.py rollback adapter; routed calls remain blocked.
The original prompts remain only in that adapter, which is removed after accepted
migration and the rollback window. Shared intent dictionaries/abbreviations,
schemas, transport limits and truthfulness checks are system policy. No capability
or performance acceptance is inferred from schema presence or scripted inference.

## Recognition consumer status (AGP-03 / CFG-11 partial)

AgentDraft.asr_replacements -> immutable AgentRuntime -> InitializeCall.recognition
-> lease-bound Recognition.ConfigureCall -> Whisper/Nemotron per-decode options is
implemented and exercised with real publication/DB/gRPC and scripted inference.
Different calls retain different dictionaries, including an empty override; draft
edits do not change the pinned release. Shared regex validation preserves the existing
exact phrase/numeric safeguards and rejects case-equivalent aliases. AgentDraft.vocabulary
now supplies business terms to the prompt; unqualified ASR hotwords remain disabled.

Strict ASR mode rejects missing configuration. Native CallSetup now forwards it
before becoming ready in the isolated SIP profile; SpeechBridge carries the same
lease through turns/interrupt monitoring/cancellation in native probe tests. Full
routed Session conversation and readiness still need wiring before live activation. Existing
worker defaults are used only for legacy unconfigured calls. Decoder cadence, bounded
hint acceleration, utterance limits and algorithm calibration remain system policy,
not new user knobs. No GPU/model reload, extra decode, live switch or latency claim.
CFG-11 remains partial until native integration and measured quality/performance gates.

## Native service lease consumers (AGP-03 partial)

CallSetup now hands off separate immutable agent/ASR/TTS worker leases. Native turns,
playback reports, every phrase, interruption monitors and generation cancellation use
the matching lease. Managed construction rejects incomplete/mismatched bindings and
never falls back to unleased calls. CallSetup alone persists routed answer/end; the
legacy SpeechBridge finalizer remains restricted to legacy construction. Conversation
channels retain 16 KiB limits independently of prepared PCM transport.

This completes transport authority handoff, not the remaining configuration consumers.
Calibration qualification, full Session integration and tool/action
execution and readiness remain pending. TTS capability matching is implemented below.
Neither a TTS OpenCall acknowledgement nor scripted inference proves model readiness.

## Synthesis capability consumer status (AGP-03 / CFG-12 partial)

The compiled runtime now binds the draft's approved voice and engine preset's model
revision to a frozen synthesis profile. InitializeCall forwards it; native setup
requires a matching TTS ConfigureCall acknowledgement under the same admission budget.
The EMA backend declares capability only after verified weights and successful warm-up.
The worker pins release/digest/profile under its existing bounded lease and rejects
unconfigured managed synthesis. It never reloads a model to satisfy a request.

The current v1 contract remains the approved shared EMA voice, fixed seed 0 and mono
PCM16/8 kHz transport. Technical normalization/chunk/phrase policies remain platform
policy; broader CFG-12 consumer/preset consolidation and real quality/performance
qualification remain open. Management compilation uses standard-library profile data
and does not import generated RPC bindings or require TTS dependencies. No schema
migration or applied release mutation is needed for this derived runtime identity.

### Implemented native timing handoff (AGP-03 / CFG-05/08/17)

InitializeCall now derives a bounded GatewayConfiguration from the release's frozen
EnginePreset. Native setup validates it before speech leases/PCM; Session uses its
answer delay, original call-duration budget and prepared-audio media drain. A delayed
ACK does not restart duration. The farewell consumer derives closing plus drain from
the same snapshot; full routed conversational Session activation remains pending.
SpeechBridge requires managed settings and consumes max_call_turns and the agent
turn deadline, capped by the remaining call deadline. Old/malformed peers cannot
silently inherit CLI defaults. Legacy deployment behavior remains unchanged.

These six existing fields need no DB migration or UI override. They do not complete
CFG-08/17: RTP inactivity and the broader transport/recovery policy still require
classification/consolidation. Native endpoint/barge-in qualification, full Session
integration and readiness coordination remain open. Current
production InitializeCall remains not-ready; local tests do not establish model,
quality, performance or carrier readiness.

### Native endpoint/interruption handoff (AGP-03 / CFG-09/10)

EnginePreset now supports an explicit frozen NativeCalibration. Initialization emits
it in GatewayConfiguration; native setup validates bounds/order/alignment and rejects
missing/unknown wire schema. Managed SpeechBridge consumes the release's TurnSettings
instead of legacy caller/CLI thresholds. TurnDetector uses its silence reminder and
existing adaptive waits/VAD/hint scheduling. The speaking monitor consumes configured
interruption VAD, onset/sustained voice and quiet windows. Old-generation revocation,
per-call state and bounded queues remain unchanged.

Historical preset JSON/digests remain valid through an explicit frozen v1 compatibility
mapping; they are not rewritten. New preset tuning must be stored explicitly in a new
revision. The optional disabled revision-2 SQL example demonstrates this. Agent drafts
cannot set calibration. Fixed echo/lexical/score/stability/freshness/resource algorithms
remain platform policy under schema-v1 rather than newly exposed tuning controls.

CFG-09/10 transport and native consumers have local scripted tests; real pause/noise/
interruption quality and performance qualification remain open. This does not fix the
historical endpoint quality gate or enable full routed Session/readiness. Output consumers
are now connected as recorded below; routed conversation orchestration remains next.

## Review findings

The previous design covered profiles/models/tools but did not enumerate every
behavioral consumer. Adding configuration rows alone leaves several fixed Python,
C++ and speech-worker rules active. Migration 0003 is partial groundwork, not the
final configuration contract. The initial catalog must preserve accepted behavior;
new options require complete implementation and validation before selection.

Original inventory findings (superseded only where the status above gives evidence):

- Migration 0003 allows `max_call_seconds` up to 3600 and answer delay up to 30000 ms;
  gateway `main.cpp` accepts at most 300 seconds and 5000 ms respectively. Publishing
  those DB-valid values today would not configure a compatible gateway.
- Profile response size can be 1000 characters, but backend speech/closing validation
  still uses 400. Agent service/native bridge enforce other byte/phrase limits.
- Model, role examples, tool docstrings, note repair, availability, fixed responses
  and summary instructions still embed one identity or business behavior.
- Silence reminder at 7000 ms, turn settings, ASR chunk duration, phrase splitting,
  TTS request sizes and closing delays have independent fixed consumers.
- Worker-wide ASR replacement vocabulary and environment-selected routing cannot
  provide call-local configuration isolation. Reassigning shared process globals
  per incoming call would introduce races.
- `system_settings` includes fields whose scope differs: model settings are per
  agent; DB connection limits and physical transport budgets are shared controls.

These gaps block marking AGP-03 complete. Until consumers migrate, no multi-user
release may assume arbitrary stored configuration is effective.

## Configuration contract and inventory

Paths below are source evidence anchors, not a substitute for reading callers/tests
when implementing. Natural-language prompts may not reliably enforce limits: enforce
actual limits in their consumers. All effective fields below are resolved into a versioned release from user content
or a system-owned preset, with validated defaults, a typed schema and explicit units.

| ID | Source / existing behavior | Configuration to classify using ownership above | Consumers / acceptance |
|---|---|---|---|
| CFG-01 | `agent/backend.py`: Kübra/Burhan, role, examples, tool descriptions, corrections, summary | Identity, address/inflection forms, role, instructions, examples and business context | Prompt compiler, SDK tools, deterministic replies, summary; unrelated synthetic names have no legacy identity leakage |
| CFG-02 | `backend.py`, `service.py`: availability, farewell, clarification, silence, further-help lines | Versioned template set, availability wording, invitation enable/count and completion policy | Every model/fallback path uses snapshot; disabled invitation never forced by repair code |
| CFG-03 | `backend.py`: exact-stop/thanks/non-message/suspect-transcript sets and matching heuristics | Bounded phrase dictionaries and selectable reviewed intent/recovery policy | Matchers use call settings; no user regex/code; changing phrases cannot suppress explicit hangup or authorize writes |
| CFG-04 | `backend.py`: global MODEL/SETTINGS/CONFIG, env routing, client timeout/retry | Model/provider/connection, reasoning, temperature, tokens, routing/fallback, inference deadline/retries, summary model | Call-local SDK settings/client credentials; no model/provider substitution, no global mutation |
| CFG-05 | `models.py`, `service.py`, `store.py`: 12000-byte history/summary, 16 turns, 100 summary rows | Context truncation strategy/budget, turn limit, summary input selection/row/byte budget | History and DB query limits agree; truncation preserves durable note and sent-audio truth |
| CFG-06 | `backend.py`, `service.py`, `agent_bridge.cpp`: 400-char speech, 4096 bytes, 16 phrases, 1024-byte phrase | Reply/closing char budget, output bytes, question count, phrase count/bytes | Model instructions, validation and native consumer derive compatible bounds; Unicode char/byte tests |
| CFG-07 | `models.py`: note/subject/summary/action lengths, unresolved/privacy list sizes and schema | Per-agent extraction/output schemas and bounded field limits, summary style and enable policy | API, model schema, store and action field catalog agree; unsupported schema rejected at publish |
| CFG-08 | `main.cpp`, `run-netgsm.sh`: global prompts, 120 s call, 3000 ms ringing, 3150 ms closing | Maximum call duration, answer delay, closing pause and drain policy, RTP inactivity policy | Call-local gateway settings; total duration allows greeting/closing; CANCEL, no-audio and BYE tests |
| CFG-09 | `turn_detector.hpp/cpp`: fixed VAD/onset/stability/reminder and completion timing | VAD threshold, onset confirmation, silence reminder delay/count, silence termination, candidate/yes-no/open/incomplete/stability timing | Typed call-local detector settings; calibrated ranges/order constraints, labeled pause/noise/quality tests |
| CFG-10 | `interruption_monitor.cpp`, interruption/echo code: fixed windows and barge-in decisions | Barge-in enable/policy, speech confirmation, backchannel policy and supported echo/pre-roll windows | Per-call state; cancellation/sent accounting preserved; no stale-generation speech after settings change |
| CFG-11 | `asr/model.py`, `service.py`: global replacements, decoder setup, 1 s partial cadence, 30 s utterance | Approved ASR preset, vocabulary/replacements, supported decoding options, partial cadence and utterance limit | Request-local options; different vocabulary on interleaved calls; no reload/model copy per call |
| CFG-12 | `phrases.py`: 240-char chunk and abbreviations; `tts/service.py`: 512 chars; `tts/model.py`: seed 0 | TTS preset, supported seed/pronunciation/normalization, phrase boundary/length and abbreviations | Phrase splitter, model adapter and queues agree; only supported EMA controls shown; preserve names/numbers |
| CFG-13 | `main.cpp`, waiting music and prompt directories: prepared WAV selection and lead-in | Greeting/fallback/closing texts or approved assets, waiting audio enable/delay/level, greeting lead-in | Versioned asset job and call playback; no arbitrary paths; no live GPU regeneration |
| CFG-14 | `backend.py`, `mcp_boundary.py`: tool set, approvals, MCP URL/filter/3 s timeout | Selected configured instances, usage instructions, fixed fields/secret refs, grants, deadlines and approved retry policies | Executor enforces even if model asks otherwise; MCP schema drift and cancellation tests |
| CFG-15 | `service.py`, current summary/outbox path: single summary behavior, no configurable actions | Finalization/summary policy, action adapters/filters, output mapping, delivery/retry budgets | Durable deterministic jobs, no-model action selection, missing-output policy and uncertain-send tests |
| CFG-16 | `service.py`: two active turns/128 retained calls, generation lifecycle | Agent concurrency/rate/cost limits within workspace/host caps | Scheduler admission/fairness; safe lifecycle reclamation remains infrastructure, not an adjustable leak |
| CFG-17 | `service.py`, bridge RPC calls: turn deadlines/phrase receipts/recovery handling | Agent/tool/ASR/TTS logical budgets and recovery strategy within transport caps | Deadline propagation and consistent error reporting; preserve teardown after cancellation |
| CFG-18 | `store.py` and retention requirements: record selection/privacy/display | Agent logging/retention preferences within platform maximums, output disclosures and transcript sharing choice | Retention/export workers, scoped API and action mapping; secrets/recording controls remain mandatory |

Paths with `agent/`, `asr/` and `tts/` refer to their respective
`services/<service>/alojan_<service>/` packages. Native paths are under
`services/voice-gateway/src/`. Launch scripts/assets/proto/generated consumers must
be included in impact analysis, not only Python agent files.

## Boundaries: configurable behavior versus implementation invariants

Every supported business behavior is configurable; technical tuning is system-owned; not every integer in source is an
agent setting. PCM frame widths, codec math, protobuf field numbers, ONNX tensor
shapes, cryptographic algorithms, model hashes and physical port bindings remain
protocol/implementation invariants. Host GPU residency, inference worker counts,
queue allocation maxima, DB pools, metrics sampling and shutdown budgets are
platform resource controls. Netgsm routing/source/prefix stays private host config.

Security invariants remain non-disableable: AI identity, authorization, truthful
storage/delivery, workspace isolation, stale-generation rejection, bounded memory
and credentials exclusion. An agent can request a smaller budget, never weaken
these rules. The UI displays supported choices and limits; no nonfunctional knobs.
TR/EMA is initially the only approved language/voice choice. Architecture supports
reviewed presets, not untested voice controls or runtime model downloads.

## One effective configuration from editor to media

1. Define one versioned typed configuration schema with explicit units, defaults,
   bounds, cross-field constraints, ownership and sensitivity. Produce form metadata
   and OpenAPI from it; map native fields through a typed versioned protobuf contract.
   Do not independently invent DB, UI, Python and C++ bounds.
2. Create a draft from a named versioned preset. Store explicit effective values at
   publish; no hidden inheritance from later changes to global defaults or env vars.
3. Validate against all selected consumers' capability versions, worker model
   readiness, physical limits and provider support. Reject inconsistencies rather
   than silently clamping. Separate character counts, UTF-8 bytes, milliseconds,
   samples and tokens; derive conversion constraints using the actual schema.
4. Compile prompt/tool schemas/output mappings and ready assets into an immutable
   manifest. Include config/schema/policy/model/asset versions and digest. Do not
   put secrets in the manifest; use scoped references. Record creator and grants.
5. Pin the manifest at call initialization. Supply validated detector/speech/runtime
   settings once over private gRPC and instantiate call-local consumers. No settings
   read or prompt compilation in a media callback/per-turn HTTP request.
6. Show redacted effective settings and release ID on the call detail screen, so a
   user can see which values actually ran. Detect node capability/config drift and
   refuse admission to incompatible nodes. Existing calls keep their snapshots.
7. Bound config size, prompt/tool token cost and cache footprint. Keep ordinary UI focused on business choices; expose engine tuning only in
   operator controls without weakening validation. The same setting cannot be
   edited in multiple competing locations with ambiguous precedence.

Model presets may describe algorithm choices but executable control logic remains
reviewed code. Any setting requiring shared worker mutation must be implemented as
safe per-request state or marked unsupported before publication. Never load one
GPU model per agent merely to make a setting configurable. Catalog changes preserve
model/service pins and require their own hardware/quality acceptance.

## Completion gates and plan amendments

- AGP-02 must ship a machine-readable configuration coverage register with each
  CFG ID, field path/unit/default/range, source preset, owner, DB/API/native consumer,
  tests, secret classification, reload semantics and migration status. Missing
  consumers block publication/completion; a DB field alone is not support.
- AGP-03 must remove identity/business/default-policy literals from production
  consumers. Literals may remain in versioned presets, synthetic fixtures and
  protocol invariants with documented classification. Use targeted lint/AST checks
  and a reviewed allowlist, not a brittle ban on every numeric/string literal.
- Add two deliberately different synthetic agents and interleave their turns.
  Change each configurable field individually within valid ranges and verify its
  observable effect or precise validation failure at the actual consumer. Include
  legacy-name absence, no-note agents, custom invitation/closing, vocabulary,
  model settings, timing, tool fixed parameters, outputs and actions.
- Test DB/API/protobuf roundtrip, bounds parity, Unicode, schema upgrades, unsupported
  combinations, old/new worker capability mismatch, release rollback and no mutation
  of active calls. Changing user UI fields without runtime effect is a test failure; additionally
  verify users cannot submit engine overrides through forged API requests.
- Keep migrations 0001–0003 untouched. New migrations introduce runtime revisions
  and corrected supported bounds, copy old values with provenance and report
  incompatible existing values for review; never silently truncate/replace them.
- Run [PERF-01–06](AGENT_PLATFORM_PERFORMANCE_PLAN.md) with the unchanged legacy
  preset before testing different models/features. Added configuration flexibility
  must not add dynamic lookups or unbounded work to the hot path.

## Optimization scorecard

Treat 'most optimized personal secretary' as a product ambition, not a verified
world ranking. Track performance and usefulness together: end-of-speech→first
substantive audio P50/P95, interruption stop, false cutoff/false barge-in rates,
message/identity/entity accuracy, correct tool selection, durable action completion,
call failure rate, cost per completed useful call, GPU/CPU/RAM and sustained qualified
concurrency. Define denominators and report failures/missing data, sample sizes and
confidence. Waiting music does not count as a fast answer.

Optimize measured bottlenecks in this order: configuration compilation/caching and
asset readiness; bounded scheduling/IO; ASR endpoint and TTS phrase timing; prompt
and tool-schema token size; provider/model settings; qualified concurrency. Each
change gets matched quality/speed/cost evidence. Do not achieve speed by losing
names/numbers, cutting callers off, skipping authorization, omitting notes or
claiming unconfirmed delivery. New candidate configurations stay drafts until
acceptance. No absolute performance or competitive claim follows from this plan.

## Review status

Graph discovery and literal/source inspection covered the agent backend/models/
service/store/phrases, gateway options/bridge/turn/interruption paths, ASR/TTS
services/adapters and carrier launcher. This is a broad planning audit, not a proof
that every executable path has already been inventoried or refactored. The
machine-readable register, consumer tests and removal gate are required to establish
that completeness during implementation. No live restart, DB change or new benchmark
was performed in this review.


## Pinned output consumers (AGP-03 / CFG-06/12 partial)

The immutable engine preset now optionally declares schema-v1 OutputBudget: phrase
characters/UTF-8 bytes, phrase count and total turn bytes. Historical JSON omits the
new field and retains its canonical digest and frozen 240/1024/16/4096 defaults.
New revisions explicitly declare tuning. Agent drafts cannot supply engine controls.
The shared phrase policy is used at publication/tool validation and streaming;
configured recovery/closing/combined acknowledgements must fit before publication.
AgentService enforces the pinned output budget and native SpeechBridge validates the
same budget before enqueueing text for TTS. Native managed character counts use UTF-8
scalars, not bytes. The old unconfigured native path retains its byte-only admission.

Fixed system ceilings remain intentional: 400 reply characters, 240 phrase characters,
1024 phrase bytes, 16 phrases and 4096 turn bytes; operators may only narrow them.
The character budget must fit four-byte UTF-8 encoding inside its byte budget.
The TTS worker retains its independent 512-character input ceiling (always above the
phrase ceiling), 30-second generated-audio cap, eight-item queue and fixed EMA
normalization/seed/chunk implementation. Native eight-item phrase queue, 16 KiB RPC
ceiling, metadata limits and the backend's 4096-byte discarded free-text guard remain
security/resource policy, not per-agent controls. They are distinct from speech budgets.
No additional model, inference or queue and no per-turn config IO is introduced.

This completes the scoped output consumer handoff, not routed conversational Session,
real speech quality/performance qualification or general tools/actions. Ordinary
InitializeCall remains not-ready and routed RunTurn remains blocked.
