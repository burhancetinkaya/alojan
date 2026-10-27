# Scoped post-call workers

This independent dependency project/image provides two separate processes and Docker
services. Neither listens for HTTP/gRPC, loads speech models or shares the voice
process's client/cache. Management HTTP remains a separate application/container.

`alojan_agent.summary_worker` consumes scoped leased summary jobs using the historical
release/provider and atomically saves the final event plus its selected action jobs.
It cannot read Telegram credentials or dispatch notifications. Model/credential
unavailability produces a failed/null summary; infrastructure failure/cancellation
preserves the 60-second lease. Finalization cannot invent note confirmation.

`alojan_agent.delivery_worker` claims only immutable action jobs. It reads the pinned
selected fields, grant and encrypted Telegram target; it cannot read transcripts,
provider keys, passwords or sessions. It checks the original grant, enabled issuer
with current owner membership, enabled workspace and target immediately before
committing sending state. Revocation pauses jobs; it never changes their target or
adopts a replacement grant. Already-authorized in-flight requests cannot be recalled.

The scheduler selects the least recently served eligible workspace, at most one
claim/second/workspace and 20/second across the Telegram provider. A complete 429
response with a bounded retry_after imposes a conservative aggregate cooldown, also
covering a bot reused across connections. Each process sends sequentially; these are
upper bounds, not throughput or Telegram quota guarantees. Crash recovery handles
at most 32 expired leases per iteration. Unsent leases can retry; sending leases
become delivery_unknown. Every attempt is fenced and capped at five, including
pre-send crashes. Only proven connection failures and complete 429 rejections retry,
with exponential backoff and the longer provider hint. Terminal jobs are not replayed.

The fixed HTTPS origin is api.telegram.org. Connection-time DNS rejects non-public
addresses; a vetted literal is pinned while TLS still verifies api.telegram.org.
Ambient proxies, redirects, user URLs/headers and response-body logging are disabled.
DNS is bounded to three seconds, connect to three, network IO to five and the full
HTTP exchange to twelve; response bytes are capped at 64 KiB. Sending begins only
within two seconds of the authority check, inside a 30-second job lease. No DB
transaction spans the HTTP request. An accepted receipt needs ok=true, a positive
message ID and the exact approved chat ID. Malformed/oversized replies, 5xx, interrupted
POSTs and wrong receipts become delivery_unknown, never an automatic resend.

Projection copies only the reviewed scalar fields; missing data is literal null.
Rendering produces one plain-text message of at most 4000 UTF-16 units, with no parse
mode and link previews disabled. Fields share the available budget; longer fields
end with an ellipsis. There is no implicit transcript or multipart send.

Deploy only after migrations through 0014 and re-provisioning the summaries and
separate actions roles. See [setup](../../docs/DEV_SETUP.md#scoped-telegram-delivery).
The opt-in infra/compose.worker.yaml supplies independent containers, each limited
to 0.5 CPU, 512 MiB and 64 PIDs with no published ports/GPU. The delivery process
requires ALOJAN_ACTIONS_DATABASE_URL and the external credential key; it never reads
legacy Telegram environment values. `--once` may perform a real external write;
use only an explicitly accepted destination/environment. There is no placeholder
health endpoint: inspect worker exit/log events and scoped queue state.

Schema-v2 compilation/preload now supports action-bearing releases. API capability
flags do not prove that the delivery process is running or a real bot/chat works.
The management API now exposes scoped delivery metadata and owner-reviewed retries
under migration 0015. It stores immutable approval with the exact rendered text,
original destination and duplicate warning. The worker atomically consumes at most
32 unconsumed approvals per iteration, reopening only the same terminal job for its
next generation. At most three owner-approved rounds are allowed, each with five
attempts; original authority and the requester's enabled owner membership are checked
before dispatch. Renderer/action/payload drift blocks sending. History preserves the
prior uncertainty; no approval can claim a receipt or change an old destination.

History and pending approval lookups are indexed. API consent/audit and worker
consumption/reset are separate atomic transactions; no management call performs HTTP.
UI and the HTTP adapter are implemented in later candidate slices below; historical
replay and PERF/carrier acceptance remain separate. Never edit a terminal job directly; use the reviewed owner API.

## HTTP delivery (AGP-08 candidate)

The existing delivery process also dispatches `http_request.v1`; no extra service,
queue, speech model or media-path I/O. Migration 0024 adds scoped HTTP targets and
adapter-specific generated foreign keys/receipts. Re-provision management and actions
roles before coordinated activation. The actions role alone reads HTTP ciphertext;
management writes but cannot read it, and summaries/records/routing/MCP roles cannot.

A pinned request contains fixed HTTPS origin/path, POST/PUT/PATCH, up to four static
`X-Data-*` business headers, typed flat JSON body and encoded scalar query. Body cap
64 KiB, query cap 4096 bytes. Rendering is deterministic and fails on mismatched types,
missing required fields or excess size. It never truncates the outgoing HTTP data.
Credential-free, clearly synthetic request previews belong to management review.

Connection-time DNS has a three-second bound and rejects the whole answer set if
any IPv4/IPv6 address is non-public. Pin a vetted literal while retaining original
Host/TLS SNI and certificate verification. No ambient proxy, redirect or response-body
interpretation/logging. One connection per request; connect three seconds, I/O five,
overall exchange twelve. Existing 30-second leases and two-second authorization
freshness apply. No database transaction spans the remote request.

A 2xx response records `sent` plus `http_status`, meaning HTTP acceptance only.
3xx/4xx (including 429) are terminal `failed`; 5xx, interrupted writes and unreadable
responses are `delivery_unknown`. Only proven connection failures automatically retry
within existing attempt/backoff caps. An explicit owner-reviewed retry reuses exact
request/event/target and the stable job UUID `Idempotency-Key`. This helps only when
the receiver honors it; even PUT/PATCH are not blindly replayed after uncertainty.

HTTP and Telegram conservatively share the existing aggregate scheduler bucket
(named `telegram` for storage compatibility): at most 20 claims/s total and one/s
per workspace, fair workspace scheduling, sequential requests and bounded lease
recovery. Telegram cooldown also slows HTTP. These are upper bounds, not performance
acceptance or per-receiver quota discovery. Separate provider buckets require measured
capacity/receiver policy before expansion. Existing Compose CPU/memory/PID limits stay.

Selecting HTTP does not replay old calls. Failure of one action cannot reopen a
successful sibling. Draft edits never change queued intent. Revoke pauses pending
work, not already sent requests. Real receiver interoperability, load/latency and
coordinated activation are pending; [evidence](../../docs/validation/http-actions-2026-10-26.md).

## Declared output finalization (AGP-08 candidate)

The existing summary worker uses one structured model response for summary plus
conversation fields only when such fields are configured. A tool-only configuration
keeps the historical summary shape. No new model request, tool invocation, service,
transcript storage or turn-path work. Input/output tokens, timeout and 60-second
summary lease retain existing engine bounds. Extracted data has no execution authority.

Finalization reloads the original release and validates each output independently.
It selects at most eight already stored, successful MCP invocations by exact scope,
call, release and selected alias, with completion no later than call end; highest
invocation ordinal wins per alias. Existing call/ordinal index and eight-call execution
ceiling bound this query. Only explicitly declared properties are copied. Malformed,
missing or unavailable values become null plus per-field status. Event, summary and
action fanout remain one transaction; retries cannot replay a finalized event.

Release v4 / event v2 / action review v3 require matching consumers. Re-provision the
summary role for limited execution-column SELECT under existing RLS. It gains no write
right to tool evidence or credentials; delivery still reads only projected job fields.
Original grants/current authority and exact HTTP request retry checks remain in force.
Revocation prevents future tool invocations; already stored historical results do not
require a new invocation or renewed MCP credential to summarize. Outbound action
permission is checked separately immediately before dispatch.

This candidate uses synthetic model/tool peers in validation; extraction accuracy,
external interoperability and performance/load acceptance remain pending. Values are
schema-validated, not independently verified facts. Existing configured-token echo
rejection remains at MCP execution; no universal secret/PII classifier is claimed.

## Summary-conditioned fan-out (candidate)

At finalization, evaluate each pinned Telegram/HTTP action's closed condition against
answered/ended timestamps and terminal summary status. `answered` remains the default;
`summary_ready` selects done and `summary_failed` selects failed. A nonmatching action
creates no job, and a call with no matching action creates no dispatch-scope entry.
This bounded check handles at most four actions inside the existing transaction; it
adds no query, network request, model request or live media work. An absent/nonterminal
summary status fails validation rather than broadening eligibility.

Review v4 and release v5 protect new condition intent. Original-target retries and
live revocation remain unchanged; retries never re-evaluate current drafts or replay
unmatched/historical events. The later lifecycle section adds no-answer/interrupted calls; optional transcript sharing is described below. [Validation](../../docs/validation/action-conditions-2026-10-26.md).

## Bounded opted-in transcript delivery (candidate)

For matching HTTP actions with `bounded_text.v1`, finalization performs one scoped,
chronological utterance query (101-row lookahead, each SQL text clipped to 8192
characters), reduces it to 100 rows / 8192 UTF-8 bytes, and stores event v3 atomically.
No transcript query/copy occurs when disabled or all opted-in conditions are unmatched.
Only each action's explicitly selected fields enter its immutable delivery payload.

The event envelope guard replaces text with null / `omitted_size_limit` above 60000
serialized bytes, preserving the existing 65536-byte database ceiling. This is an
additional transcript guard, not a replacement for other field budgets. Renderer
validates state/text consistency; existing exact grants, revocation, request limits,
lease fencing, idempotency and reviewed retry apply. No new model request, media work,
role privilege or historical replay. Release v6/review v5 consumers must be activated
together. [Contract](../app-api/README.md#optional-transcript-sharing-agp-08-candidate).

## Unanswered and interrupted lifecycle (candidate)

The existing queue also finalizes explicitly opted-in unanswered calls. Scoped end,
setup cancellation and aged-record reconciliation atomically insert one job from the
original v7 release; unrouted tombstones and default answered-only agents insert none.
The worker skips model preparation/inference, transcript/note reads and tool projection,
then commits event v4 with `not_requested` and only matching no-answer jobs. Summary
and extracted-data injection are rejected. Lease, scope, immutable intent and retry
fencing are unchanged. `not_requested` is terminal, not a failed model invocation.

Interrupted is answered plus exact durable `disconnected`/`failed`; it includes normal
caller BYE. Neither model prose nor failure-code substrings control actions. Reconciliation
records are observed lifecycle evidence, not proof of what a disconnected caller heard.
Migration 0025 adds states only, without backfill/replay. Apply routing/records role
changes and all v7/v6 readers together. [Contract](../app-api/README.md#call-lifecycle-conditions-agp-08-candidate).
