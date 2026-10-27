# Agent platform performance and deployment plan

Owner prioritization (2026-10-27, ADR 0011): post-call summary semantic/wording quality
is deferred and no longer blocks the current private rollout. The voice performance,
conversation quality, isolation, durable action and rollback gates below remain.
Known failed summary evidence must not be relabeled as passed.

## Prepared speech preview isolation — 2026-10-26

Management now reads at most 500,000 bytes of trusted prepared audio per authorized
request, verifies it outside the DB transaction, and shares the existing two-operation
HTTP limiter. Its 0.5 CPU/512 MiB container mounts the store read-only. No inference,
GPU reservation, media callback, per-turn lookup or voice process change. Browser
blobs are released on draft changes/navigation. Read-only owner decode and preserved
voice containers establish functionality only; matched latency/load acceptance stays
open. New audio generation still requires the drained-window process below.

## 2026-10-26 — Owner-directed in-place trial

The owner selected the unused existing line/host for managed testing. Same resident
ASR/EMA workers now serve the managed runtime; HTTP/summary/delivery run separately.
Linux native SIP/cleanup checks passed and the final real-model two-turn loopback
completed in 33.29s. Deployed partial-hint calibration was preserved in immutable
engine revision 2 before opening the line. These are functional observations, not
matched latency/load/soak acceptance. Real provider behavior passed only 3/6 checks.
PERF-01–06 and handset acceptance remain open; trial eligibility is not full
qualification. See [evidence](validation/in-place-platform-2026-10-26.md).

## Maintenance deployment update — 2026-10-26

Gateway and speech derivatives have passed actual startup/quiescence on primary
Linux with customer admission closed. The agent is now stopped after discovering
that its scoped consumer needs the not-yet-migrated production schema. The startup
guard is strengthened; matching candidate schema/runtime remains a prerequisite.
The preceding documentation transfer is complete. Separate API,
Telegram and PostgreSQL containers are unchanged. See
[rollout evidence](validation/maintenance-rollout-2026-10-26.md).

The retained deployed control source/binary and dependency versions are frozen for
comparison. A compatibility call using new speech service code is not the unchanged
stack baseline. Record full variant identity and restore/restart exact control
workers in an exclusive window for matched measurement as needed. No PERF gate is
closed by startup receipts or a single synthetic call.

## Dependent-worker quiescence — 2026-10-26

AGP-09 / PERF-01/03 preparation now has an opt-in worker admission fence and an
on-demand `voice.v1.Maintenance` Health Check on the existing private gRPC listeners.
New work is denied while fenced; cleanup remains available. Active RPCs, call leases,
agent turns/initialization/legacy summaries, native futures and cleanup failures keep
the receipt unready. EMA explicitly confirms scheduler cleanup and CUDA synchronization.
These are implemented conditions, not a claim that a real GPU run passed.

Control-file polling is outside the audio loop; no new lookup occurs per audio frame
or turn. Enabled RPC wrappers add a counter and an admission check per RPC; disabled
deployments install no interceptor. Measure enabled overhead in PERF-02/03 before
activation. Normal health is independent of maintenance, preserving supervisor policy.

For a preparation window, drain the gateway, fence workers, obtain fresh receipts
from all three current instances and exclude other producers. A restart invalidates
the reservation, including potential model warm-up before readiness. Reopening a
worker for a controlled benchmark also invalidates its maintenance receipt; retain
gateway closure and exclusive producer control. DB housekeeping and remote-provider
execution are outside the inference receipt. See [evidence](validation/worker-quiescence-2026-10-26.md).

Compatible packages are staged, not deployed. Next: coordinated maintenance rollout
and real-worker receipt validation, followed by fresh matched voice/latency measurements.
No PERF or carrier gate is closed by scripted gRPC or package-import tests.

## Supervised admission persistence — 2026-10-26

AGP-09 / PERF-01/03 preparation: the compatible validation supervisor now starts the
native child closed and applies operator-owned persistent admission state only after
that child's acknowledgement. File checks and signal delivery occur outside the
gateway/media process. Docker crash/restart, closed SIP 486, explicit resume SIP 200,
ongoing PCMA/PCMU media and healthy closed admission are covered by
[functional evidence](validation/supervised-admission-2026-10-26.md).

This does not close a PERF gate. Account for the 250 ms supervisor poll, bounded log
forwarder and existing health probes in the matched real comparison. A probe can
delay control by its five-second timeout; native acknowledgements, never elapsed
time or request logs, establish the fence. Live deployment, dependent-worker
quiescence (including non-preemptible inference and unresolved cleanup), fresh
matched voice measurement and carrier acceptance remain pending.

## Native admission drain implementation — 2026-10-26

The development gateway now supports operator close/resume signals and a start-drained
option without changing existing capacity. Local SIP/RTP checks cover ongoing calls,
ringing/setup, rejection, closed startup and cleanup. See
[evidence](validation/admission-drain-2026-10-26.md). This adds one flag check at new
call admission and main-loop state acknowledgement; no media callback IO, per-turn
configuration lookup or new HTTP service. These functional results do not measure
PERF overhead. The resident lifecycle gateway is unchanged. Safe GPU maintenance
still requires compatible supervised deployment, persistent closed-on-restart launch
configuration and dependent-worker quiescence; local_calls=0 alone is not sufficient.
General max_calls=0 configuration/reload remains unimplemented.

## Exact audio reuse — 2026-10-26

Candidate Kübra's prepared greeting/unavailable WAVs now match the deployed bytes,
after aligning the draft's genitive apostrophe with the original source text. This
removes synthesis variance for these fixed assets; it does not establish per-turn
latency, listening or model qualification. The operator packaging command performs
bounded CPU/file validation only and never starts EMA. Changed speech still needs
the fenced preparation window below. See [evidence](validation/voice-pack-preparation-2026-10-26.md).
The current gateway has bounded SIGTERM shutdown, not controlled long-call draining;
the capacity plan's max_calls=0 reload remains unimplemented. Establish and verify an
explicit ingress fence before running real inference comparisons; idle snapshots alone
cannot reserve voice/GPU capacity. No PERF gate was closed by the packaging tests.

## Preflight measurement refresh — 2026-10-25

PERF-02 isolated Linux observations: 50 warm scoped admission samples after five
warmups, P50 21.54 ms / P95 39.68 ms / max 51.15 ms including a fresh DB connection.
Thirty cold application preloads with warm OS cache and synthetic PCM: P50 1.1114 ms /
P95 1.1293 ms. 10000 warm in-memory pins: P50/P95 0.0028 ms; accounted payload 75680
bytes. Two benchmark tests passed in 2.16s. No matched control/confidence analysis,
live inference, RTP, load or soak: PERF-01–06 acceptance remains open. See the
[preflight evidence](validation/platform-preflight-2026-10-25.md) for deployment
inventory, one-message real Telegram adapter acceptance and required cutover order.
Resident voice containers were neither restarted nor used for benchmark inference.

## Delivery history and retry isolation (2026-10-25)

History uses indexed keyset pagination (50 rows, optional status) with metadata only.
A single owner review renders at most one bounded message in the management process;
it shares the exact pure renderer with delivery, without importing the voice runtime.
Approval takes a short job lock and atomically inserts consent/audit. Workers use
SKIP LOCKED, consume at most 32 indexed unconsumed approvals and retain original
workspace/provider rate gates. Review history is capped at three manual rounds; no
poll scans the full consumed-review history to locate work. No media callback, turn
lookup, new process/service/dependency or GPU work is added. Functional tests do not
establish matched real-voice performance or large-history soak acceptance.


## Scoped action dispatch isolation (2026-10-25)

AGP-05 adds no media callback, turn-time lookup or model instance. Atomic fan-out
adds at most four inserts and one scheduler-row insertion to the independent summary
transaction. Action rendering/decryption/HTTP run in another container, capped at
0.5 CPU/512 MiB/64 PIDs, with one sequential in-flight request per process. Durable
jobs have indexed pending/expired lookup, immutable selected output up to 64 KiB,
a 30-second fenced lease, five attempts and bounded 32-job recovery batches.
Least-recently-served workspace selection plus fixed 1/second/workspace and aggregate
20/second Telegram claim caps prevent a single backlog monopolizing dispatch. A 429
uses an aggregate cooldown, trading throughput for safety when bot references overlap.

The renderer caps one message at 4000 UTF-16 units. DNS/connect/IO/whole-request budgets
are 3/3/5/12 seconds, and response bytes are capped at 64 KiB. HTTP never holds a DB
transaction; credentials/authority are checked just before sending state is committed.
Cancellation or lost acknowledgement cannot trigger an automatic second POST. These
bounds and functional tests do not establish matched real-voice P50/P95, backlog
soak/capacity, real bot quotas or PERF acceptance. Measure those before live migration.

## Scoped credentials and post-call isolation (2026-10-25)

Provider selection during a turn uses the pinned workspace/reference and cached
client only. Encryption/decryption and scoped DB checks occur in node preflight/
readiness refresh, with a one-second credential IO budget and fixed 16-client bound.
Each refresh adds a bounded credential DB check per target; the existing 1.5-second
whole-refresh budget is unchanged. Two-second credential freshness starts before IO,
not after it. Pending IO preserves a still-fresh value; failure/cancellation clears
that connection's access, and missed refresh expires automatically. No media callback,
additional per-turn DB lookup, model instance or user tuning control is introduced.

This is a bounded revocation/availability tradeoff: storage loss can block later model
requests on existing calls, while an already-dispatched request may finish. Connection
revocation is not immediate distributed cancellation. Shared connections preserve
per-runtime model/preset options; unrelated tenants never share API keys/state.

The independent worker serializes scoped summary jobs, uses per-job clients and closes
them after work/cancellation. Its existing 60-second DB lease covers the bounded
20-second model task plus input/credential/finalization IO. Docker limits CPU to 0.5,
memory to 512 MiB and PIDs to 64, without GPU or exposed ports. Management HTTP stays
in its separate container. Functional isolation/lifecycle tests and image builds are
not PERF-01–06 throughput/latency/soak acceptance; matched credential-refresh overhead
and concurrent summary workload measurements remain required before live rollout.

Date: 2026-10-25. Owner-required design constraints; not measured acceptance.
Scope: AGP-02–09 / M1–M5, requirements §3,7,10,12,15 and US-01/04/05/07.
Extends [ADR 0011](ADR/0011-self-service-voice-agents.md) and the
[platform design](VOICE_AGENT_PLATFORM.md). Netgsm is the only carrier in scope.

## Non-regression contract

Preserve the existing accepted voice behavior and response speed when adding
configuration, users, tools and management traffic. Separate architecture overhead
from deliberate user changes: a larger model, longer prompt or slow external tool
can take longer and must be measured as a distinct agent workload, not hidden in
an infrastructure comparison. Neither the current baseline nor this design proves
the requirements' absolute P50 <1000 ms / P95 <1800 ms or barge-in <250 ms targets.

Re-measure the actual Linux deployed build/configuration before implementation.
The [2026-10-24 baseline](validation/response-latency-2026-10-24.md) is historical,
warm/sequential, 25 calls/50 turns, with output-port rather than handset timings.
Later endpoint changes mean it must not be reused as today's control measurement.
Record commit/source hashes, runtime settings, pinned models, driver, hardware,
provider route, prompt/tool schemas, input fixtures, database state and host load.
Use sanitized outputs; record all failures/cancellations, never only successful turns.

## Mandatory process and container boundaries

| Component | Application/deployment | Work it may perform |
|---|---|---|
| Management HTTP API | Separate `services/app-api` app, own entrypoint/image and Compose service `management-api` | Authentication, configuration CRUD, validation, job enqueue, paginated reads |
| Post-call/management jobs | Separate worker entrypoint and Compose service `action-worker`; may reuse API image | Summaries as budgeted, Telegram/HTTP jobs, manifest validation and asset job coordination |
| Voice runtime | Existing native Linux gateway and Python agent/ASR/EMA processes initially | SIP/RTP, turns, bounded tool calls and live speech |
| PostgreSQL | Existing separate Compose service with bounded per-role pools | Durable configuration, calls, notes and jobs |
| Future frontend | Independent static build/deployment; no backend embedded in voice runtime | Calls the management API only |

The repository already has app-api health/migration code; extend it as an independent
application rather than embedding an HTTP router in the agent process. Compose
currently contains PostgreSQL only: management-api and action-worker containers are
planned, not installed. Pin image/base/dependencies when implementing. No Docker
socket, GPU device or SIP/RTP ports for either HTTP API or action-worker. Internal
service calls use existing private gRPC; HTTP is never in the audio/turn data path.
Any new HTTP listener must be a separate application and Docker service. Outbound
webhook requests belong to action-worker and do not require a new inbound listener.

Use private container networking and separate DB roles. Keep API port local/private
behind the authenticated HTTP ingress; Cloudflare carries no SIP/RTP. Give API and
worker their own CPU/memory/PID/DB connection limits, restart policies, health checks
and bounded concurrency. Do not use container host networking just to reach native
services: configure a narrow reachable private endpoint and firewall it explicitly;
container localhost is not native-host localhost. No public management-to-gRPC path.

Initial isolated-test budgets: management-api 1 CPU/512 MiB, worker 0.5 CPU/512 MiB,
DB pools at most four API connections and two worker connections, two concurrent
outbound deliveries and one metadata job. These are test starting limits, not measured
production sizing. Reserve voice/DB capacity first and tune from CPU/RSS/queue/lock
measurements. OOM/restarts must not disturb voice. HTTP overload is rejected/queued
at bounded limits; it cannot consume all host RAM or DB sessions. Separate processes
alone do not guarantee isolation on a shared host, GPU, disk, DB or provider account.

## Voice path and configuration loading

Publish immutable release manifests, compile prompts/tool schemas, validate mappings
and prepare audio before activation. No prompt compilation, catalog discovery,
MCP OAuth, model download or greeting synthesis on an answered call's path.

At call initialization, resolve the active binding and persist the release snapshot
in one bounded consistent DB transaction outside SIP/media callbacks. Look up compiled
objects/assets by release ID+digest in a bounded workspace-aware cache. Preload ready
releases onto eligible call nodes before binding them; if missing, resolve before
answer under the setup deadline or reject new admission. Never answer with the wrong
agent or fall back to an old owner because a cache is cold. Keep the three-second
ringing policy separate from response latency. Initialization remains within the
existing two-second preparation deadline; changing that bound needs validation.

Cache only immutable compiled data and safe pools; conversation, agent instances,
credentials, playback and cancellation state stay call-local. Bound cache memory and
entries; active releases are pinned until calls finish. Cache eviction may delay new
admission, never change active context. No shared mutable SDK agent/model settings.
Persist release IDs for reproducibility and validate artifact digests. Multiple
workspaces with identical text do not automatically share private cache entries.

During a turn, use the call's frozen configuration; no new management HTTP request,
profile database read or tool catalog fetch is introduced. Existing note/history IO
remains bounded and transactional. Persist tool/action outcomes outside media IO.
Security checks cannot be removed to meet latency: use a separate lightweight
revocation state updated from authoritative storage, checked at every privileged
execution. Initial maximum freshness age is two seconds; fail closed for new
privileged operations when freshness cannot be established. Publication and grant
revocation expose propagation status; do not promise instantaneous distributed
revocation. A strict immediate revocation request waits for node acknowledgement
or fences the node. A write already dispatched cannot be recalled.

API restart/outage must not end calls or prevent new calls when required DB, prepared
release and voice dependencies are healthy. DB failure can still block admission or
note persistence: this is an existing shared dependency, not eliminated by API
separation. A failed save cannot be announced as successful. API worker jobs must
not run migration/DDL on user requests; migrations run as controlled deployment
operations with lock/statement budgets and rollback review.

### Native timing configuration implementation

AGP-03 now transfers six bounded timing/turn integers in the existing initialization
reply (schema-v1, now maximum 256 bytes including native calibration). Native setup validates once and stores an
immutable call-local value before readiness. Session and SpeechBridge consume this
value with no new RPC, per-turn serialization/DB/HTTP read, thread, media queue or
model instance. The 1.8-second setup and existing bounded cleanup budgets remain.
Legacy launch settings cannot silently replace managed release timing. Functional
SIP/RPC timing tests establish enforcement/isolation, not the PERF non-regression
gates or human conversation quality. Full routed integration remains pending.

### Native conversation calibration implementation

The same admission reply now includes typed native calibration; the total gateway
envelope is bounded to 256 bytes. Validation occurs before readiness and consumers
retain immutable per-call values. No new service round trip, model reload/pass,
allocation on media callbacks, retained queue/history size or per-turn lookup is
introduced. Existing scheduling hints remain bounded by the ASR worker's unchanged
budget; a hint-enabled candidate still needs measured work/latency/quality comparison.

Historical implicit-v1 calibration is frozen, not retuned during loading. Optional
explicit presets are new disabled revisions. Synthetic configuration/isolation and
legacy CPU/SIP regression tests do not replace the failed historical pause-quality
acceptance or PERF-01–06. Full routed Session integration remains pending.

## Background work isolation

- Telegram/HTTP delivery starts after durable finalization. Remote delay, retries or
  an endpoint outage never holds the caller or an agent turn. Bounded fair queues,
  backoff, retention and workspace quotas prevent retry storms and disk exhaustion.
- Summaries retain their own provider concurrency/token budget below live turns.
  Global account limits are shared even across containers. Reserve live headroom;
  pause/reduce summaries when live queues or 429 rates rise. Avoid a second unbounded
  API client pool that bypasses the shared budget.
- Publishing does not regenerate every prompt. Rebuild only affected artifacts by
  content/revision key; deduplicate jobs, cancel obsolete drafts and bound retries.
- Initial EMA asset creation runs only in an explicit idle/maintenance window with
  voice admission drained. Native GPU work may not be preemptible: checking that
  the line is idle once is insufficient. Keep the old release active until a planned
  preparation window; never launch a second EMA process. Concurrent background
  synthesis may be enabled only after measured scheduler/non-regression acceptance.
- Provider/MCP verification and synthetic UI tests are explicit, rate-limited jobs
  with their own budgets. Never stress the live GPU from a preview button. Read-only
  prompt/HTTP previews do not invoke a model or external service.
- Use indexed/paginated call queries, bounded ranges and no transcript-wide unbounded
  scans. Defer bulk export/retention/backups to controlled low-load windows. API/worker
  DB roles have separate connection and statement-time limits. Transactions never
  hold locks over external HTTP or model calls.

## Measurements and release gates

Capture stage timings with monotonic clocks, opaque call/release IDs and bounded
asynchronous metrics. Distinguish INVITE→ready/answer, actual speech endpoint→first
substantive RTP, ASR final, agent preparation, provider/tool wait, first TTS chunk,
playout/underflow, interruption stop and post-call queue/delivery. Keep output-port
proxies explicitly labeled until RTP/handset evidence exists. Do not add stage
percentiles to invent end-to-end percentiles. Report P50/P95/P99 only with sample
counts and confidence limits appropriate to the workload.

Proposed regression gates, to be tested rather than represented as current results:

| Metric | Gate |
|---|---|
| Added per-turn configuration/dispatch overhead, deterministic local services | P50 ≤5 ms and P95 ≤20 ms; no per-turn HTTP/config DB dependency |
| Warm call binding/release snapshot lookup | P95 ≤50 ms; total initialization still within setup deadline |
| Matched full voice path with unchanged prompt/model/tools | Target no increase; upper 95% confidence bound of candidate minus control ≤20 ms for P50 and ≤50 ms for P95 |
| Interruption stop | No new failed interruption; P95 increase ≤10 ms and existing absolute target tracked separately |
| Media correctness | No new underflows, dropped frames, wrong-profile speech, stale generation output or cross-call leakage attributable to platform work |
| Resource stability | No OOM/deadlock/unbounded queue; no retained-state growth after settled churn; resource deltas reported |
| API/worker outage or saturated HTTP load | Active voice continues; new voice admission independent of HTTP availability; identical regression gates |

The small positive bounds are measurement/engineering tolerances, not permission
to conceal a slowdown. Investigate any repeatable increase. If intervals are too
wide to establish a gate, report inconclusive and extend/repeat matched sampling;
never turn noisy provider variance into a pass. No latency gain compensates for a
quality, security, note persistence or cancellation regression.

## Test sequence

1. PERF-01 / M5: record fresh warm baseline from the actual deployed configuration.
   Same fixtures, codecs, model, prompt, provider routing and hardware in comparison.
2. PERF-02 / M1,M4: deterministic real SIP/gRPC fixture tests isolate release lookup,
   tool dispatch, cold/warm cache, memory bounds and cancellation overhead. These
   are infrastructure results, not real-model quality or speed evidence.
3. PERF-03 / M2–M5: matched real CUDA/API A/B runs, alternating control/candidate
   batches in an idle scheduled window; retain failed runs. At least 100 eligible
   turns per variant across the same scenario set, with call/scenario-blocked
   confidence analysis. Increase samples if the result is inconclusive. No second
   EMA worker; reuse resident models and avoid live caller contention.
4. PERF-04 / M5: repeat with management reads/writes/publication requests at admitted
   limits and overload rejection, 1000 queued synthetic actions, slow/unavailable
   fake Telegram/webhooks, DB lock pressure, API/worker kill/restart and credential
   revocation. No uncontrolled external load test; real provider sends remain small
   and explicitly scoped. Asset jobs must remain queued while live admission is on.
5. PERF-05 / M1–M5: a minimum 30-minute voice soak with background load and a separate
   churn run beyond 128 calls/4096 generations. Check settled RSS/VRAM, DB pools,
   cache reclamation, disk/log growth and per-workspace fairness. Single-call tier
   first; overlapping 2/3/5 calls depend on CAP work and get separate qualification.
6. PERF-06 / M1,M5,M6: limited carrier canary after isolated gates, preserving old
   binary/config/release and measuring handset/transport separately. Observe real
   call quality, then widen deliberately. No new concurrency limit in this redesign.

Deploy compatible DB/consumers before new bindings. Readiness includes release
assets and supported tool/model capability, not API HTTP 200 alone. On regression,
stop new admission to the candidate, drain calls, pause affected jobs and restore
the known-good release/binaries. Preserve notes, execution journal and frozen action
payloads; rollback never replays external writes. API deployment/restart does not
restart speech workers. Existing carrier reachability and quality gaps remain open.

## Status

Planning only. No new Docker image/service, resource-limit change, benchmark,
capacity claim, DB migration or live restart in this task. The existing 24 passing
configuration-storage tests are not performance evidence. Record future results
with PERF task IDs in PLAN and CALL_TEST_PLAN, separated by environment.


## AGP-03 isolated admission observation — 2026-10-25

The new asynchronous admission repository was measured on primary Linux against
synthetic scoped data with a restricted routing DB role: 50 sequential calls after
five warmups, fresh connection for each call, P50 28.50 ms, P95 38.07 ms, maximum
39.26 ms. Run `pytest -q -s tests/benchmark_number_routing.py` in the management test
environment with the private test DSN. This covers lookup/validation/snapshot commit
only. It does not cover native initialization, actual asset preload, inference,
RTP, parallel contention or matched legacy comparisons. PERF-01–06 remain pending;
do not treat being below the proposed 50 ms lookup target as full gate acceptance.
See [call validation evidence](CALL_TEST_PLAN.md).

## AGP-03 prepared-cache observation — 2026-10-25

The Python cache now moves file IO, WAV decoding and prompt compilation before
admission, uses immutable workspace/release/digest entries, and pins active calls.
Defaults bound payload to 16 MiB / 16 entries and preparation to two concurrent
threads with no third-load queue; object overhead is entry-bounded, not measured
RSS. A cancelled waiter keeps its worker reservation until work completes. Failed
loads preserve usable entries and all-pinned capacity rejects new preload.

Primary Linux, `pytest -q -s tests/benchmark_prepared_releases.py`: 30 measured
application-cold loads after five warmups, with warm OS cache and synthetic one-second
speech files plus 400 ms greeting pad: P50 1.0599 ms, P95 1.0922 ms, max 1.1479 ms.
10,000 in-memory pin/unpin pairs: P50 0.0028 ms, P95 0.0029 ms, max 0.0114 ms.
Accounted entry payload was 75,512 bytes. No settings/filesystem IO occurs on pin.
This excludes maximum-duration packs, DB/SIP, native playback, inference, RTP,
contention with real calls and a matched legacy baseline. PERF-01–06 remain pending;
these observations do not establish end-to-end latency or capacity acceptance.

## AGP-03 native prepared-output bounds — 2026-10-25

Private setup now transfers complete pinned PCM to the native worker with the
original setup deadline (capped at 1.8 seconds), cancellation and a 1,000,000-byte
reply ceiling. Each clip is at most 480,000 bytes; the maximum valid pair passes
the actual Python/C++ transport test. Setup serialization and native immutable
storage copy bounded data: this is not zero-copy, and transient gRPC allocations
are additional to the retained per-call payload. Measure peak RSS and simultaneous
maximum-pack setup during the pending capacity gate.

PreparedPlayback.render uses the existing PJMEDIA buffer, a per-call cursor and
lock-free cancellation/accounting. It does no allocation, filesystem/DB/network
IO or locking; the existing PJMEDIA port lifecycle group lock remains unchanged.
Real PJSIP-port tests pass, and legacy PCMA/PCMU dialogue regression
passes, but no routed INVITE, real inference, matched latency or saturation result
is claimed. No readiness writer or live activation is enabled by this component;
PERF-01–06 remain open.

## AGP-03 isolated native setup scheduling — 2026-10-25

The explicit loopback setup test profile runs OpenCall/InitializeCall/GetPreparedAudio
on one worker per admitted session, sharing a bounded loopback channel. All three
operations consume the same 1.8-second admission budget; no per-step reset. Ready
workers sleep until cancellation without polling. The SIP event loop handles
ringing, ACK, CANCEL, overload and hangup while setup is pending.

Cleanup is also off the SIP thread, with two sequential RPCs capped at 250 ms each.
Keep the admission reservation until the worker finishes, including after the SIP
dialog disconnects, so repeated cancellations cannot create unbounded workers.
No queued replacement or detached background thread is introduced. Lost cleanup
acknowledgements do not certify DB cleanup; lease expiry/reconciliation still apply.
Two-call synthetic RTP isolation and overload responsiveness tests are functional
evidence, not five-call/GPU/production latency or capacity qualification. The actual
service remains not-ready, and PERF-01–06 remain open.


## Native lifecycle persistence isolation evidence (2026-10-25)

The isolated setup worker now reports SIP ACK/end to scoped PostgreSQL repositories.
Prepared audio starts after ACK without awaiting persistence; SIP BYE stops playback
and receives a response while the persistence worker drains. The delayed-answer test
observes media within a 250 ms audio-pump window while the answer RPC is still pending,
and asserts BYE handling below 200 ms. Each answer/end RPC is bounded to 500 ms;
release is bounded to 250 ms. Cleanup retains the admission slot, bounding worker
count under churn. No DB/model/HTTP operation was added to the 20 ms media callback.

This is deterministic isolation evidence with synthetic PCM and local SIP/DB. It
is not a measured production voice latency distribution, GPU/provider A/B, soak or
capacity qualification. PERF-01–06 remain open. Clock synchronization, lost-ACK/end
recovery and delayed/failed persistence must remain in the release regression set.


## AGP-03 recognition vocabulary isolation (2026-10-25)

Spelling aliases compile at private call configuration, outside the audio/turn path;
each decode receives a call-local reference. No model reload/copy, new inference pass,
management HTTP lookup or per-turn DB read is introduced. Configuration retention is
bounded by the existing 128 ASR leases, eight short aliases/2048 UTF-8 JSON bytes per
lease (plus Python/regex overhead), and release/300-second expiry. Existing single
inference admission and non-preemptible decode draining remain intact. Empty aliases
explicitly override legacy worker defaults. The Linux-only existing partial-hint
optimization was preserved and tested: repeated hints yield coverage at 600/1600 ms
and final 2000 ms for two seconds of input, without decoding on every hint.

This is functional isolation/budget evidence with scripted inference. Native handoff,
GPU quality comparison, matched latency/CPU/RSS measurements, concurrent-call/soak
and PERF-01–06 gates remain pending. Do not activate strict ASR mode on the live
legacy gateway before the native consumer is implemented and accepted.


## Native recognition handoff bounds (2026-10-25)

The isolated CallSetup worker now includes ASR OpenCall/ConfigureCall in the existing
1.8-second admission deadline, without resetting it between services. The gateway
cannot reach local ready/answer if ASR rejects configuration, is old/unavailable,
returns false or exceeds that deadline. SIP CANCEL/shutdown calls TryCancel and
returns without waiting for network cleanup. ASR release adds at most 250 ms to
bounded worker cleanup (up to 1 second for ASR release + answered end + agent release);
the admission slot remains held until the worker finishes. Unknown open/release
acknowledgements remain explicitly unconfirmed and require lease expiry/reconciliation.

Reuse the existing 16 KiB speech channel for ASR, not the larger prepared PCM channel.
The immutable binding is shared with normal turn/interrupt/cancel consumers; no
per-turn config/DB/HTTP lookup, model reload, queue or thread is added. Existing Linux
partial-hint and endpoint diagnostics were preserved, including their turn-detector
header/source dependencies. These are bounded functional tests, not new production
latency percentiles, GPU/carrier evidence or capacity qualification. PERF-01–06 remain open.


## Native agent/TTS lease handoff bounds (2026-10-25)

TTS OpenCall is included in the same 1.8-second setup budget; it cannot extend
admission by restarting the clock. One additional immutable binding per consumer
and metadata on existing RPCs introduce no per-turn DB/HTTP/config lookup or inference
pass. ASR, TTS and agent conversation channels retain 16 KiB limits; prepared PCM stays
on its separate larger channel to avoid widening conversation message admission.

TTS release adds at most 250 ms to setup-worker cleanup: at most 1.25 seconds for TTS,
ASR, answered end and agent release, plus any already-running 500 ms answer report.
Signaling cancellation only updates atomics/cancels contexts and does not wait for
these RPCs. Admission retains the slot until cleanup completes. A lost token/release
reply is explicitly uncertain. There is no new queue, model instance, background
application worker or GPU operation. Consumer cancellation/join must precede owner release when
integrating the full Session conversation. Synthetic SIP/ASR/TTS lifecycle evidence
is not a matched production latency, quality, capacity or soak result; PERF-01–06 stay open.


## Pinned synthesis capability bounds (2026-10-25)

Synthesis.ConfigureCall is one additional setup RPC within the existing shared
1.8-second deadline. The gateway bounds the configuration to 512 bytes; the worker
validates bounded identifiers and fixed PCM format, then stores an immutable profile
with the release/digest under one of the existing maximum 128 leases. Reconfiguration
cannot change a pin; explicit release and expiry discard it. Each phrase performs
only an in-memory pin lookup after lease validation. No HTTP/DB/disk read, model
reload, new inference stage, queue, worker or resident model is added.

Worker capabilities are captured after normal weight verification and CUDA warm-up;
the acceptance tests use scripted backend capabilities and model PCM. Native setup
rejects old/mismatched workers and handles cancellation without blocking SIP/media.
The separate management environment imports/compiles profiles without RPC bindings.
This establishes functional isolation, not new GPU, carrier, matched latency/quality,
soak or capacity evidence. PERF-01–06 remain open and live services remain unchanged.


## Pinned output budget bounds (2026-10-25)

OutputBudget adds four bounded integer settings plus schema identity to the existing
256-byte initialization envelope, with no new RPC. Publication and completed speech
tools reuse the existing phrase policy for at most 400 reply characters. Native text
validation counts UTF-8 scalars on the agent reader thread before its existing bounded
queue; no work is added to media callbacks. Per-call settings are immutable in memory.
No HTTP/DB/disk lookup, new inference pass, model, queue or enlarged transport limit.

Operators can only narrow the current 240-character/1024-byte phrase, 16-phrase and
4096-byte turn ceilings. Existing eight-slot phrase/TTS queues, audio duration and
message ceilings remain. Functional tests cover independent presets, UTF-8 boundaries,
rejected output, cleanup and unchanged legacy dialogue. These are not matched latency,
real model quality, capacity or soak measurements. PERF-01–06 remain open; tuning and
live activation require their existing qualification gates.


## Routed Session consumer lifetime (2026-10-25)

The opt-in native conversation profile reuses existing SpeechBridge, immutable pins,
queues and service channels. No extra inference, per-turn config/management IO, media
allocation or audio-callback blocking. The prepared greeting still starts immediately
after ACK while the existing ReportCallAnswered write runs in parallel. Conversational
capture requires both greeting completion and successful answer persistence (500 ms
RPC cap). A failed write closes the call before any model/tool turn. This preserves
the existing first-audio behavior without weakening the scoped storage boundary.
Production latency distributions still require matched measurements.

Termination time is captured immediately. Lease release waits on the setup worker for
speech quiescence (including generation invalidation and playback receipts), not just
playout completion. Existing bridge cancellation/deadlines apply; the previously stated
1.25-second setup cleanup cap starts after consumer quiescence and is not a total
shutdown bound. Admission remains reserved until cleanup completes. Agent EndCall waits
for active turn cleanup within its existing 1.8-second budget; native end has its own
shorter 500 ms RPC deadline and reports uncertain cleanup on failure. No new worker/queue
is introduced. Functional BYE responsiveness and CPU interruption tests do not establish
PERF-01–06 throughput/latency/soak, real CUDA/API quality or carrier readiness.


## Node-local preload/readiness coordinator (2026-10-25)

Activation is outside admission and turns. One bounded operation claims a release,
uses the existing at-most-two-thread asset loader, pins its payload, and performs
ASR/TTS ConfigureCall probes with temporary leases. There is no speech/model inference,
new model instance, media worker, queue or dependency. Existing cache entry/payload
ceilings also bound readiness targets; busy activation is rejected instead of queued.
Failed preparation retains no ready permit. Known lease cleanup is attempted on
cancellation; a lost open token retains the existing expiry limitation.

Activation has a five-second work budget plus bounded withdrawal cleanup. Each speech
RPC is capped at 500 ms; DB operations use a one-second total budget with 500 ms
statement, 100 ms lock and 700 ms transaction limits. Initial dependency freshness
starts before the final health/storage checks. This does not change the existing
1.8-second call setup budget. Call admission adds only an in-memory identity/expiry
check after its existing route/cache pin; no additional per-call or per-turn IO.

Warm refresh performs two private health RPCs, one asynchronous storage health/privilege
query sequence, and one bounded DB renewal per target. It runs no sooner than 500 ms
after the previous refresh, does no work without targets, and has a 1.5-second total
budget. All local expiry values use the refresh start time, never completion, so slow
checks cannot extend stale evidence. The local two-second expiry is stricter than the
ten-second DB visibility TTL. Failure closes new local admission; existing calls keep
their pinned settings. No prepared audio reload, TTS ConfigureCall, provider request,
management HTTP or turn-path DB read is introduced by refresh.

This bounded background DB/RPC work still needs matched resource/latency measurements;
functional tests do not establish PERF-01–06. Model/client structural readiness does
not prove external API access/quality. Successor receipt IDs fence old writes, but
strict immediate distributed revocation still requires the planned acknowledgement/
node-fencing protocol. This admission freshness is not per-tool grant revocation.

## Explicit managed startup (2026-10-25)

The isolated managed launcher reads a bounded 64 KiB deployment file once and selects
at most 16 exact releases within the existing cache limits. Preflight is sequential,
outside media/admission, and all targets must pass a final refresh before serving.
No file watcher, per-call configuration read, new model, service or dependency is added.
The exclusive agent port is reserved before claims so an overlapping listener cannot
split call-local state. Restart revalidates assets and dependencies; this is not an
atomic zero-downtime deployment protocol.

Warm work is the existing readiness loop plus scoped stale-call reconciliation every
30 seconds. Its fixed 600-second age exceeds the engine's 300-second hard ceiling;
it does not add IO to media callbacks or active turns. Stop closes local admission
before awaited cleanup, finishes bounded readiness withdrawal, cancels generations,
allows the existing two-second RPC stop grace and releases resources. Receipt cleanup
may add up to the bounded per-target DB timeouts; stop is not immediate call draining.
The process does not run legacy summaries/Telegram. Functional startup, restart,
reconciliation and cleanup tests passed; PERF-01–06 and real API/CUDA remain pending.


Telegram connection authoring update (2026-10-25): the new encrypted destination
store is used only by the independent management application. No Telegram lookup,
decryption or network operation was added to admission, media callbacks, turns or
the summary loop. Creation has a per-workspace serialized cap of 100 rows. Existing
provider-envelope behavior remains compatible. Linux functional/process tests passed;
this is isolation evidence, not a new latency/capacity benchmark. Delivery/grant checks
will belong to the separate action worker in the next AGP-05 slice.


Reviewed-action publication update (2026-10-25): target/grant validation happens in
independent management transactions, with at most four action references and 1000
grants per agent. Draft/consent/publication share draft-row locking before target
locks; target locks are sorted. No HTTP, secret reads or action DB work is added to
media callbacks or turns. Empty action lists preserve historical release digests.
V2 action releases cannot preload until delivery is integrated; this is a capability
gate, not latency/capacity acceptance. Runtime dispatch revocation must be implemented
in the separate worker before removing that gate.

## 2026-10-26 — Queued resident EMA preparation

AGP-06 implements the explicit maintenance-window path above. Only the fixed local
TTS worker opens after gateway drain and all-worker quiescence; no concurrent voice
inference or second model process is admitted. Host coordinator: 0.5 CPU/256 MiB;
HTTP remains separate. Session/file/process fences, bounded speech/duration and
progress/RPC deadlines, workspace quotas, retry bounds and 60-second spacing contain
preparation work. Fresh cleanup, gate-open acknowledgements and managed-route
readiness precede native reopening. Incomplete evidence leaves admission closed.

One real resident generation took 4.252 seconds with no calls active; this is a
functional measurement, not P50/P95 or a no-regression/soak claim. Preparation briefly
pauses new calls, which the UI states before requesting work. Existing call behavior
is unchanged; full PERF-01–06 acceptance remains pending.

## 2026-10-26 — Typed HTTP action isolation (AGP-08 candidate)

HTTP rendering/DNS/TLS happens after call finalization in the existing limited
action worker. No media callback, per-turn lookup, new broker, model process or
HTTP service is added to voice execution. The durable finalizer projects only the
reviewed existing scalar fields. HTTP job failures remain independent of summaries,
other actions and calls; immutable events do not adopt later draft edits.

At most four actions per agent; flat body 16/query 8 fields; reviewed action 4 KiB,
review 16 KiB, outgoing JSON 64 KiB and encoded query 4 KiB. The existing sequential
scheduler shares its aggregate 20 claims/s and one/s/workspace limits across Telegram
and HTTP. The legacy bucket name stays `telegram`; Telegram cooldown conservatively
also affects HTTP. No per-receiver rate claim or new parallel sender is introduced.
Existing 0.5 CPU/512 MiB/64 PID worker limits, 30-second leases, two-second permission
freshness, bounded DNS/connect/exchange and crash recovery apply. Response bodies
are neither read nor retained, and unknown writes never automatically replay.

Functional Linux integration/browser checks validate separation and bounds, not
CPU/latency non-regression, GPU capacity or real network interoperability. PERF-01–06,
shared DB pressure/queue soak and approved external receiver acceptance remain open.

## 2026-10-26 — Declared output cost boundary (AGP-08 candidate)

Definitions compile into immutable release/runtime data. Media callbacks and active
turns do not extract fields, read output rows, call management or invoke extra tools.
The same post-call summary request carries at most eight bounded field descriptions;
existing summary input, model token, timeout and worker resource ceilings are unchanged.
There is no second inference request or increased retry budget. Near-limit outputs
may fail validation within those budgets; do not silently raise them per tenant.

Finalization performs one additional scoped query only for configured tool sources,
using the existing call/ordinal index and eight-invocation hard ceiling. It selects
only successful pre-end results for exact pinned aliases. Values cap at 1 KiB/field,
512 string characters, eight scalar array items and finite magnitude 1e12. Existing
HTTP 64 KiB body/4 KiB query and review/grant bounds remain; statuses count toward field
limits. Source schema changes require a new release, not a mutable runtime lookup.

Functional Linux SDK/database/browser evidence validates bounds and isolation, not
real extraction accuracy or a P50/P95/no-regression/capacity claim. Shared CPU/DB/queue
load and PERF-01–06 still need measured acceptance before production expansion.

### Summary-condition candidate cost

Each finalized call evaluates at most four closed predicates using already loaded
answered/end timestamps and terminal summary status. No extra query, model request,
network operation or media/turn-path I/O is introduced. Unmatched actions do not add
queue or dispatch-scope rows. This structural bound is not measured latency or live
load acceptance; the existing non-regression gates still apply.

### Opt-in transcript cost boundary (AGP-08 candidate)

Default-off or unmatched intent adds no transcript query/copy. Matching intent adds
one post-call scoped query with 101-row lookahead and 8192 SQL characters per row
(worst-case roughly 3.3 MiB UTF-8 before reduction), then caps exported text at 8 KiB
and 100 rows. Existing transaction/resource deadlines and queue isolation remain.
No additional summary request, per-turn lookup or audio-path allocation is introduced.
Final event and selected jobs retain an extra bounded text copy under existing storage
policies; this slice does not implement cleanup/retention automation. Structural bounds
and synthetic tests are not measured CPU/DB/latency non-regression or load acceptance.

### No-answer/interrupted candidate cost boundary

Answered finalization adds only a bounded predicate over existing outcome metadata.
Unanswered end/cancellation/reconciliation adds one scoped indexed snapshot/release
query with conditional queue insertion in its existing transaction. Default releases
produce no extra job. Opted-in jobs reuse the independent bounded worker, skip model
preparation/inference and do not read utterances/notes/tool results. No new daemon,
media callback work or native protocol exchange. This is structural isolation, not
measured cancellation latency, DB saturation or non-regression acceptance. Existing
PERF-01–06 gates remain before production expansion.


## Scoped summary HTTP 429 recovery candidate — 2026-10-26

Observed real provider throttling now has a bounded post-call recovery path. Only an
explicit SDK rate-limit error can defer work. The existing database claim/lease carries
the cooldown; no worker sleep, new queue/service, media callback work or migration is
added. Minimum delay is 60 seconds; accepted Retry-After seconds/dates can extend it
to 300 seconds. Invalid or longer server delays are terminal rather than retried early.
The third total claim is final on another 429. Clients are closed between attempts and
credentials/release/input are rechecked. No event/action is queued before finalization.

This increases the scoped summary request budget to at most three total claims for
provider throttling, superseding the earlier no-increased-retry-budget statement for
this case only. It does not change model/provider, live-turn retry settings, deadlines,
CPU/memory/GPU limits, per-job output bounds, or action-delivery idempotency. A queued
job does not block unrelated eligible jobs. Tests prove functional isolation, not a
provider-wide scheduler, aggregate quota, load, latency distribution or soak acceptance.
Those remain rollout gates. [Evidence](validation/summary-quality-2026-10-26.md).
