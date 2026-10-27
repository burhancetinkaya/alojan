# Management application

AGP-02 / M0,M5, requirements §1, §12, §14–16 and ADR 0011. Native authentication
and scoped agent drafts, immutable release preparation/publication/rollback,
qualified model catalog reads, verified asset import and owner number binding are
implemented. The scoped live runtime, encrypted provider/Telegram connections and
builder frontend, durable audio preparation and scoped call history are available;
MCP/HTTP and full builder acceptance remain pending. A saved draft cannot receive calls.

Anyone may register. Registration atomically creates a user, an enabled private
workspace and its owner membership; it creates no number, agent release, tool
grant or external notification. Owners can publish qualified releases
without an additional platform-operator approval. Number ownership verification
is a separate prerequisite for routing. The second owner-requested number/Telegram
binding remains disabled until its private configuration is provided.

## HTTP contract

All mutations require exact `Origin: <ALOJAN_PUBLIC_ORIGIN>` and JSON. Authenticated
mutations also require the `X-CSRF-Token` returned by registration, login or session
inspection. Sessions use `__Host-alojan; Secure; HttpOnly; SameSite=Strict; Path=/`.
Do not put session tokens into URLs, browser storage or application logs.
Responses with account/agent information use `Cache-Control: no-store`.

| Method and path | Body / result | Permission |
|---|---|---|
| POST `/v1/auth/register` | `login`, `password`, `display_name`; 201 with session and workspace | Public, rate limited |
| POST `/v1/auth/login` | `login`, `password`; 200 with session/workspaces | Public, rate limited |
| GET `/v1/auth/session` | User, workspace memberships, CSRF token | Valid session |
| POST `/v1/auth/logout` | `{}`; revoke this session and expire cookie | Session cookie + CSRF |
| POST `/v1/auth/password` | `current_password`, `new_password`; revoke all sessions | Valid session + CSRF |
| GET `/v1/workspaces/{id}` | Workspace ID/name | Membership |
| GET `/v1/workspaces/{id}/agent-schema` | Strict JSON Schema for editable business configuration | Membership |
| GET `/v1/workspaces/{id}/agents` | Up to the workspace cap of 100 drafts | Membership |
| POST `/v1/workspaces/{id}/agents` | AgentDraft; 201, generated ID and version | Owner/editor |
| GET `/v1/workspaces/{id}/agents/{agent}` | Draft content/version, ETag | Membership |
| PUT `/v1/workspaces/{id}/agents/{agent}` | Full replacement AgentDraft and `If-Match: "N"` | Owner/editor |
| POST `/v1/workspaces/{id}/agents/{agent}/preview` | `{}`; greeting, digest, selected aliases, draft readiness | Membership |
| GET `/v1/workspaces/{id}/agents/{agent}/voice-preview/{clip}` | Current draft `If-Match: "N"`; validated `audio/wav`, clip `greeting` or `unavailable` | Membership |
| GET `/v1/workspaces/{id}/models` | Enabled catalog IDs/revisions/display names, no tuning controls | Membership |
| POST `/v1/workspaces/{id}/agents/{agent}/prepare` | `{}`, draft `If-Match: "N"`; preparation ID and asset readiness | Owner/editor |
| GET `/v1/workspaces/{id}/agents/{agent}/releases` | Latest 100 release IDs/digests, current publication version/ETag | Membership |
| POST `/v1/workspaces/{id}/agents/{agent}/publish` | `preparation_id`, publication `If-Match: "N"` (`"0"` initially) | Owner |
| POST `/v1/workspaces/{id}/agents/{agent}/rollback` | `release_id`, publication `If-Match: "N"`; creates a new release | Owner |
| GET `/v1/workspaces/{id}/numbers` | Own number claims, verification/binding state and current versions | Membership |
| POST `/v1/workspaces/{id}/numbers` | `number` in canonical +90 850 format; creates disabled pending claim | Owner |
| PUT `/v1/workspaces/{id}/numbers/{number}/binding` | `release_id`, number `If-Match: "N"`; binds a verified number to a ready release | Owner |
| POST `/v1/workspaces/{id}/numbers/{number}/deactivate` | `{}`, number `If-Match: "N"`; stops new admission | Owner |
| GET `/v1/workspaces/{id}/calls` | Up to 50 calls, optional `agent`/`after` UUIDs, exclusive `next_cursor` | Membership |
| GET `/v1/workspaces/{id}/calls/{call}/transcript` | Up to 50 finalized rows; ascending UUID cursor, optional `after`; sent assistant speech only | Membership |
| GET `/v1/workspaces/{id}/calls/{call}` | Pinned identity/timing, summary, latest note and delivery metadata; no writes | Membership |
| GET `/health/live`, `/health/ready` | Process / required management migrations | Loopback deployment |

Login names are 3–64 ASCII letters/digits/`_.-`, start with a letter/digit and are
case-insensitive. Alternatively use an ASCII email identifier up to 254 characters:
local part up to 64, alphanumeric segments separated by `.`, `_`, `+` or `-`,
and DNS labels with an alphabetic final suffix. Internationalized/quoted addresses
are not supported. This is a login identifier, not mailbox verification; matching
an email never automatically claims a pre-existing workspace or live agent. Passwords are 8–128 Unicode characters at enrollment/change;
they are never trimmed or truncated. Hashes use stdlib scrypt N=131072/r=8/p=1,
16-byte random salts and constant-time verification. Random 256-bit session
tokens are stored only as SHA-256 verifiers. Idle timeout is 30 minutes, absolute
timeout 12 hours, maximum 10 sessions per account. Password versions prevent a
login racing recovery from creating an obsolete session. Recovery is an audited
private operator CLI; there is no unverified email-based recovery endpoint.

Registration/password work allows five attempts per source per five minutes;
login allows 30/source and 10/login name. Counters are atomic and shared in PostgreSQL,
including rejected attempts. Expired session/counter/invitation cleanup is bounded
and runs in the management process. Two thread slots bound password memory/CPU;
HTTP concurrency is capped at 32, request bodies at 64 KiB and read time at 5 seconds.

Typical failures: 400 invalid fields/configuration; 401 no valid authentication;
403 role/origin/CSRF rejection; 404 missing or unauthorized workspace/object;
409 login unavailable or workspace draft limit; 412 stale draft; 413 oversized body;
415 non-JSON; 428 missing/invalid version precondition; 429 rate limit with Retry-After;
503 database unavailable. Validation responses never include submitted secrets.

Drafts expose identity/inflection forms, instructions, tone, business context,
speech wording, vocabulary, supported model/voice and the fixed `take_note` tool.
Mandatory AI disclosure is prepended to the greeting. Unknown fields, engine
overrides, unsupported models/tools and unsafe template expressions are rejected.
Schemas describe draft authoring, not current voice runtime support. Publication
must still prove all consumers/assets ready. Requests cannot select workspace
roles or authorize tools by inserting fields into their instructions.

Business instructions accept up to 20,000 characters so the existing live assistant's
complete instructions can be migrated without truncation. This does not enlarge the
60,000-byte draft or 32,768-byte compiled prompt ceilings: combined fields and UTF-8
expansion can still fail preparation. Platform rules and granted capabilities remain
mandatory. A migrated business instruction is wrapped with platform/identity context;
its final prompt must be measured separately from the original legacy prompt.

## Linux build and validation

The independent image contains only management code and its frozen dependencies.
It does not import/start the voice agent, ASR, EMA or native gateway. Compose limits
it to 0.5 CPU, 512 MiB and 64 processes; filesystem is read-only except bounded `/tmp`.
The native command binds loopback port 18081 by default. Compose binds inside an
internal bridge and publishes only host `127.0.0.1:18081`; PostgreSQL also joins that
bridge. The private management DSN uses `postgres:5432`. Adding this network to an
existing PostgreSQL container requires a coordinated deployment/recreation; do not
apply the override to the live stack before the rollout gate. HTTPS terminates at
the protected tunnel. Build context is allowlisted to code/locks/migrations; private
`.local`, model files, virtual environments and unrelated code are excluded.

```sh
uv run --frozen --env-file .local/dev.env pytest -q \
  tests/test_native_auth.py tests/test_agent_drafts.py \
  tests/test_database.py tests/test_profile_settings.py tests/test_agent_releases.py \
  tests/test_number_routing.py
docker build -f infra/docker/management.Dockerfile -t alojan-management:agp-auth-review .
uv run --frozen --env-file .local/dev.env python tools/validate-management.py \
  --image alojan-management:agp-auth-review \
  --network alojan-local_default --database-host alojan-local-postgres-1
```

The validator creates/drops a random private test schema, runs a temporary
resource-constrained container on an unused loopback port, with a temporary restricted
DB login, and verifies the actual HTTP email registration/draft/preview/model guard/
logout flow. Supply the existing test database's bridge network and container DNS
name together; omitted arguments retain the earlier host-network diagnostic mode. It manually handles cookies over
loopback for this synthetic server test; it is not browser TLS or carrier evidence.
Neither command upgrades the live schema or restarts a live service.

For deployment, provision a separate non-owner/no-BYPASSRLS database login and a
private `.local/management.env` with `ALOJAN_DATABASE_URL`, HTTPS
`ALOJAN_PUBLIC_ORIGIN` and optionally `ALOJAN_TRUSTED_PROXY_IPS` (comma-separated
literal addresses of the controlled tunnel proxy). Never reuse the migration
superuser as the deployed management login. Provision grants with the migration
credential and `python -m alojan.roles ROLE` (same command environment as recovery).
The existing dedicated role must have no elevated role memberships, object/schema
ownership or unexpected prior permissions. The grants allow authoring/authentication,
but prohibit catalog qualification, prepared-asset writes, number verification and
live call reads. Owner binding is permitted only through the verified/ready checks. Password provisioning remains private operator configuration.
Complete remaining runtime isolation gates before public exposure. The connection secret is mounted read-only,
not baked into the image or Compose environment. No production secret is seeded.

Forwarded client addresses are ignored unless the direct socket peer is explicitly
trusted. Only then is one valid `CF-Connecting-IP` used for rate limiting; never trust
arbitrary X-Forwarded-For. Configure this with the actual isolated tunnel ingress so
unrelated visitors do not share the proxy's address quota. Worker/header transforms
must not undermine this trust boundary. Public tunnel integration remains untested.

Private recovery, after independently verifying account ownership:

```sh
PYTHONPATH=services/app-api uv run --frozen --project services/app-api \
  --env-file .local/management.env python -m alojan.accounts reset-password LOGIN
```

This prompts without echo, invalidates every session and writes an operator audit
event. Never pass passwords as arguments. External messages are not sent.

## Review basis and remaining scope

Password/session choices follow the reviewed
[OWASP password guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
and [session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
Proxy trust follows [Cloudflare's header documentation](https://developers.cloudflare.com/fundamentals/reference/http-headers/).
These references do not constitute an independent security audit.

RLS is enabled/forced on `agent_drafts`; scoped queries and composite foreign keys
also enforce ownership. Existing profile/voice tables still require the coordinated
runtime/RLS migration in AGP-03. Do not expose a generic DB endpoint or enable
multi-user live routing from these drafts. Formal OpenAPI, membership/invitation UI,
scoped credentials, automatic drained-window asset synthesis, actual carrier proof and
all AGP-03–09 native runtime/performance/carrier gates are still outstanding. The current
preset covers bounded model/generation/speech budgets; CFG-08–18 consumer coverage
is not complete. No live model catalog entry is qualified by a migration/example.


## Immutable publication and prepared audio

Migration 0006 adds immutable preset/model definitions, preparation snapshots,
verified asset manifests and releases; current publication is a separate pointer.
RLS is forced on preparations/assets/releases/publications. Migration 0007 adds
email login identifiers without modifying applied 0004 or creating any accounts.
[Disabled SQL catalog example](../../infra/examples/agent_catalog.sql) is repeatable.

Preparation locks the draft, validates its expected version, pins the qualified
catalog revision and computes a speech identity from fully rendered text, EMA
revision, sample rate and greeting pad. Repeated preparation of the same version
is idempotent. Instructions-only changes can reuse the same workspace's audio;
renaming the assistant/owner or changing spoken text requires different audio.
Identical text in another workspace does not grant access to its prepared files.
Preparations/releases are bounded to 1000 per agent pending a reviewed archival policy.

Publication requires an owner, unchanged prepared draft, still-qualified catalog
revision and matching ready assets. It creates profile revision + release + current
pointer + audit in one transaction. A stale publication precondition returns 412;
stale preparation/unqualified model/missing or invalid audio returns 409. Failures
retain the old publication. Rollback creates a new release of the old manifest;
it does not edit history or overwrite the current draft, and revoked model versions
cannot be rolled back into use. These APIs do not activate a phone number.

The trusted operator/asset-worker import path accepts only a v1 `VoiceManifest`
(`alojan_contracts.assets`) and exactly `greeting.wav`/`unavailable.wav` in a private
pack directory. It validates text/model hashes, file hashes, PCM16 mono 8 kHz,
20 ms frame alignment, bounded duration, complete non-silent audio and the greeting
silence pad. It installs under `STORE/<workspace UUID>/<speech digest>/`, fsyncs and
atomically renames before inserting the immutable ready record. Files are never
overwritten; concurrent identical installs are safe. The store and source parents
must be private operator-owned directories. Invalid packs cannot mark assets ready.

```sh
PYTHONPATH=services/app-api:services/voice-contracts \
  uv run --frozen --project services/app-api --env-file .local/asset-worker.env \
  python -m alojan.voice_assets --scope WORKSPACE_UUID --preparation PREPARATION_UUID \
  --pack PRIVATE_GENERATED_PACK --store PRIVATE_ASSET_STORE
```

For migration, an operator may reuse an existing trusted EMA pack when its exact
spoken texts, model revision, sample rate and greeting pad match the draft/preset:

```sh
PYTHONPATH=services/app-api:services/voice-contracts uv run --project services/app-api \
  --frozen python -m alojan.voice_pack --scope WORKSPACE_UUID \
  --draft PRIVATE_DRAFT_JSON --preset PRIVATE_ENGINE_PRESET_JSON \
  --source TRUSTED_LEGACY_EMA_PACK --store PRIVATE_STAGING_STORE
```

This converts the retained EMA generator manifest to the release asset contract,
validates original text/audio hashes and complete WAV structure, and uses the existing
immutable workspace/speech-digest installation path. Source text is stripped exactly
as in the legacy generator before comparison; identity or punctuation differences are
not silently normalized. Audio bytes remain unchanged. A mismatch requires a fresh
EMA pack during a fenced preparation window; it never triggers inference automatically.
Hashes prove integrity, not provenance: this is an operator-only command for known
sources, not an upload endpoint. The source files must be regular files, not symlinks.
It creates no database asset row, preparation, qualification, release, grant or binding.
Use the existing import command only after its normal qualification/preparation checks
are satisfied. Offline repackaging itself does not reserve the GPU or interrupt calls.

This imports already generated trusted audio and performs no inference. Byte/hash
checks do not prove that a voice actually spoke the declared text: trusted generation
provenance and listening/quality checks remain necessary. Automatic generation must
use the resident EMA under an acknowledged drained maintenance window, not a second
model or API-triggered GPU job. That scheduler/native handshake is still pending.
Prepared-file health/distribution and call-local loading belong to AGP-03/06. Do not
qualify the production catalog until those consumers and performance gates pass.


## Number ownership and call admission foundation (AGP-03)

Migration 0008 adds scoped immutable verification evidence and binding history,
short-lived node readiness acknowledgements, and immutable call-to-release pointers.
New numbers always begin pending/disabled. Only canonical `+90` followed by `850`
and seven ASCII digits is accepted; HTTP does not guess carrier prefixes or parse
SIP URIs. Workspace claims are capped at 100. Two workspaces may submit the same
unverified number so a guess cannot reserve someone else's line. Only one verified
owner can exist globally. Neither entered caller ID nor a matching login/email is proof.

Private operator commands record **already established** ownership and routing
evidence, using opaque case IDs rather than credentials, phone captures or transcripts:

```sh
PYTHONPATH=services/app-api:services/voice-contracts \
  uv run --frozen --project services/app-api --env-file .local/migration.env \
  python -m alojan.number_verification verify --scope WORKSPACE_UUID --number NUMBER_UUID \
  --version N --operator OPERATOR_REF --ownership-evidence OWNERSHIP_CASE --routing-evidence ROUTING_CASE
```

`revoke` instead accepts `--reason CASE_REF` and no ownership/routing arguments.
These commands require private cross-workspace operator authority (superuser or
BYPASSRLS), never the management login. Verification/revocation increments the
number version and leaves admission disabled. Re-verification or transfer requires
no unended calls for that DID, including revoked prior owners' calls. Historical
snapshots remain with their original workspace. IDs, workspace and DID are immutable.

The owner then binds an explicit published release using the latest number ETag.
Binding checks ownership, scope, model qualification and a matching ready digest on
the deployment's `ALOJAN_VOICE_NODE_ID`. Users cannot choose the host or submit
readiness. Missing host configuration or readiness prevents binding. Readiness is
valid for at most 30 seconds from its protected acknowledgement time; the separate
`checked_at` column exists only for row-lock privileges. No producer is enabled yet:
the native preloader must attest actual cached artifacts/consumer compatibility and
renew readiness before deployment. Do not manufacture production ready rows.

Publishing a new agent release does not change number bindings implicitly. Rebind
explicitly. Deactivation stops new admission while retaining previous bindings and
call snapshots. ETag checks serialize concurrent owner changes; initialization locks
the same number row so it observes one complete binding. No fallback to Kübra exists
in the new repository for an unknown/disabled/unready number.

`alojan_agent.routing.CallRouter` implements asynchronous PostgreSQL admission outside
media callbacks. It discovers scope from a trusted canonical DID, records the call
and immutable release reference in one transaction, and returns a frozen `PinnedRoute`
with serialized manifest content. Equal initialization retries return the original
snapshot even after rebinding; changed DID/source/caller hint/node or ended-call
reuse is rejected. A legacy unscoped call cannot be claimed by initialization.
No management HTTP or inference request occurs. Database connection/query/lock/
transaction budgets and an outer 1.8-second deadline bound setup. Existing call-slot
admission must precede this repository when integrating the private gateway RPC.

`cancel_unanswered` handles cancellation before or after the setup transaction,
including a pre-initialization ended-call tombstone. It never queues summaries or
notifications and never ends an already active call. Tombstones have no workspace
until a verified admission exists and must remain excluded from user call views.
The initialization result is not proof of answer, media readiness or capacity.

Provision a separate admission DB role with `python -m alojan.roles ROLE --purpose routing`.
It has narrowly granted global reads of the verified number directory and call routing
metadata to discover the scope. Release/binding access still uses transaction-local
RLS; the role has no BYPASSRLS, account access, binding/verification writes or notification
permission. Do not reuse this credential for user HTTP access. Management role grants
cannot mark nodes ready or change number verification status.

**Remaining native integration:** trusted PJSIP called-field extraction, private
`InitializeCall` RPC authentication/wiring, node preload/acknowledgement, call-local
prompt/assets/settings consumers, answer/activation, late-CANCEL cleanup and abandoned
initialization reconciliation. Existing live sources have later lifecycle changes
and must be preserved during that integration. Database/repository tests do not
establish SIP behavior, model readiness or voice performance. Production mappings,
owner-account migration and the disabled second number remain unchanged.


Migration 0009 adds forced RLS for conversation records and a scoped finalization
queue; it does not grant management users call-record access or expose a new route.
Dedicated private worker roles are provisioned with `--purpose records` and
`--purpose summaries`. See the [agent integration boundary](../agent/README.md#scoped-records-and-finalization-agp-0305-staged)
and [read-only SQL example](../../infra/examples/scoped_call_records.sql).
Live migration remains gated on legacy-role review and coordinated worker upgrades.

## Write-only provider connections

Migration 0011 adds workspace-RLS provider_connections. Owners use
`POST /v1/workspaces/{scope}/provider-connections` with exactly provider=openrouter,
label and api_key. Application encryption uses an external Fernet key. Keys never
appear in responses, manifests or audit payloads. GET lists id/provider/label/enabled
only. POST to `.../provider-connections/{id}/revoke` takes an empty object and permanently
disables the connection. Existing CSRF/origin/session/body-size/scope checks apply.
Editors/viewers cannot create/revoke. Editors may select a workspace connection in
a draft; publication remains an owner action. There is no token-read endpoint.

Set model_connection in the draft to the returned UUID. Draft writes and publication/
rollback reject foreign or revoked references. Identity/ciphertext are immutable;
replacement requires a new connection/release. No in-place key rotation is implemented.
Historical unbound manifests retain their digests but cannot deploy on a managed node.
Management can INSERT ciphertext but cannot SELECT it. The separate credential reader
can only read scoped connections/workspace state, not users/calls. Missing encryption
configuration returns 503 on creation, never plaintext fallback. The optional
compose.credentials.yaml overlay mounts the external key into the independent API
container. See DEV_SETUP for runtime/worker settings and the key lifecycle.


## Telegram connection storage (AGP-05 foundation)

Migration 0012 adds workspace-RLS `telegram_connections`. Owners create a fixed bot/
chat pair with `POST /v1/workspaces/{scope}/telegram-connections` and exactly `label`,
`chat_id` and `bot_token`. The label is printable, trimmed and 1–80 characters.
`chat_id` is a canonical nonzero signed decimal string with absolute value below
2^52; mutable usernames, URLs and numeric JSON values are rejected. Bot tokens have
bounded syntax validation only: the API does not contact Telegram or prove bot/chat
access. This is stored configuration, not a verified or deployable action.

GET on the collection returns only id/label/chat_id/enabled to workspace members.
POST to `.../telegram-connections/{id}/revoke` with `{}` permanently disables it.
Owner authorization, session/CSRF/origin/body limits and a serialized lifetime cap of
100 connections per workspace apply. Database triggers prevent target/key changes and
re-enabling; replacement requires a new connection and subsequent action authorization.

The existing external credential key encrypts tokens with a distinct `telegram`
purpose as well as workspace/connection identity. Provider envelopes retain their
previous encoding. Management can insert ciphertext but cannot read it. None of the
current voice, summary or provider-credential roles can read Telegram tokens; no
Telegram reader is provisioned before its execution consumer exists. Responses and
audit omit credentials. Missing key configuration rejects creation with 503.

Saving/revoking a connection neither sends a message nor grants permission. Agent
selection, field review, explicit owner grants and release binding are described below;
finalized-event jobs and network delivery remain the next AGP-05 slice. Legacy global Telegram settings
are not read or migrated by these endpoints. Migration 0012 must precede role
provisioning and this management version; readiness requires both credential migrations.
See [metadata-only SQL example](../../infra/examples/telegram_connections.sql).


## Agent post-call action review and authorization (AGP-05)

Migration 0013 adds immutable `action_grants` and a same-workspace/same-agent release
foreign key. Apply it before deploying this management version and re-provision the
management role. No grants are seeded and no historical events are replayed.

An agent draft accepts `post_call_actions`, a list of zero to four Telegram actions.
Each has a unique `alias`, a workspace `connection_id`, an explicit nonempty `fields`
list and fixed adapter `telegram.send_message.v1`, event `call.finalized.v1`, condition
`answered`, and missing-value policy `null`. The agent-schema endpoint lists the 23
allowed scalar field paths. Raw transcripts, tokens, arbitrary paths, expressions,
URLs, caller-approved permissions and model-selected triggers are rejected. Selecting
a caller/called number requires its provenance field; summary fields require summary_status.
An empty list is omitted from serialization to preserve historical v1 digests.

Example draft fragment (synthetic connection reference, not an authorized send):

```json
{
  "post_call_actions": [{
    "alias": "owner_handover",
    "connection_id": "00000000-0000-4000-8000-000000000001",
    "fields": ["agent_name", "summary_status", "summary.subject", "summary.summary"]
  }]
}
```

All routes below are under `/v1/workspaces/{scope}/agents/{profile}`:

| Route | Behavior |
|---|---|
| GET `/action-review` | Returns draft_version, review_digest and exact agent/workspace, adapter/event/filter/missing policy, fixed chat ID/connection label and selected fields. No token or network request. |
| POST `/action-grants` | Owner-only explicit consent, with exactly draft_version and review_digest from the displayed review. Rejects changed drafts/reviews, disabled/foreign targets and unprivileged users. |
| GET `/action-grants` | Lists id/digest/enabled metadata for up to 1000 grants belonging to this agent. |
| POST `/action-grants/{id}/revoke` | Owner-only empty-body request, irreversibly revokes that grant. |

The frontend must display the review's destination, operation and data scope before
submitting the explicit authorization request. Saving a draft or publishing without
this authorization does not create permission. One grant covers the exact bounded
set of actions; revoke it to stop the set, or edit/review/authorize a new subset.
Unchanged prompt/voice edits may reuse the same grant because the reviewed external
operation/data scope is unchanged. Changed fields, target, alias or agent require a
matching grant. Identical concurrent consent requests return one active grant; a
lifetime cap of 1000 grants per agent includes revoked grants.

Publication rechecks enabled target, grant, issuer account and owner membership.
Action-bearing releases use manifest schema v2 and pin the exact grant ID and reviewed
configuration; the FK and manifest checks bind it to the same agent/workspace. Rollback
rechecks the original grant, never substitutes a new grant for a revoked one. New
consent after revocation permits a new publication only. An inactive issuer's still-
enabled grant must be explicitly revoked before replacement consent. Metadata enabled
means not explicitly revoked, not proof of current target/issuer validity.

Action review reports delivery_available=true as adapter capability, and publication
returns deployment_status=requires_delivery_worker. Neither flag probes worker health
or confirms remote bot/chat access. V2 releases compile/preload only with their exact
workspace, and finalization schedules immutable jobs in the summary transaction.
The separate delivery service enforces the original live authority and destination
immediately before sending; editing a draft or granting new consent cannot broaden
queued jobs. See [worker behavior](../action-worker/README.md) and
[deployment prerequisites](../../docs/DEV_SETUP.md#scoped-telegram-delivery).
These management APIs themselves never send a message or replay historical events.

See [read-only SQL diagnostic](../../infra/examples/action_grants.sql).

## Delivery outcomes and reviewed retry (AGP-05)

Migration 0015 adds immutable retry consent/history and a bounded consumption marker.
Re-provision management and actions roles. Management reads scoped selected output
for owner review but cannot change queue state or read Telegram ciphertext. Its
UPDATE(id) permission exists solely for PostgreSQL row locks: the immutable-intent
trigger rejects actual ID changes. Worker state/reset privileges remain separate.

Routes below extend `/v1/workspaces/{scope}/agents/{profile}`:

| Route | Behavior |
|---|---|
| GET `/deliveries` | Members read metadata only, newest first; up to 50 rows plus next_cursor. Optional status enum and after UUID cursor; no offsets, arbitrary filters or payloads. |
| GET `/deliveries/{job}` | Members read current outcome, receipt/failure code, retry_queued and up to three prior approved rounds. |
| GET `/deliveries/{job}/retry-review` | Owner only; exact original target/configuration, bounded rendered message, payload digest, current state/generation and duplicate-delivery warning. Returns review_digest, can_retry and blocked_reason. No send or state change. |
| POST `/deliveries/{job}/retry` | Owner only, Origin/CSRF/JSON protected. Requires exactly request_id UUID, displayed review_digest and accept_duplicate_risk=true. Returns 202 accepted; stores consent and audit atomically, never sends inline. |

Show the warning and exact destination/message **before** collecting a fresh, unchecked
confirmation. Ask the owner to reconcile against the actual Telegram chat first.
Never auto-submit on page load, infer consent from a prompt, or default the confirmation
to accepted. An unknown outcome is not evidence of failure: a retry may duplicate a
message. The warning applies to all manual rounds, preserving uncertainty even when
a later attempt fails before sending. The review text is plain data; render as escaped
text, never HTML/Markdown instructions. Ordinary list/detail responses omit message,
payload, claim tokens and bot tokens. Owner reviews contain only selected output,
not raw transcripts. All responses keep the existing no-store headers.

Retry accepts only failed, paused or delivery_unknown jobs, with current original
connection/grant/issuer authority and no already queued request. Sent, pending,
leased and sending jobs cannot retry. At most three manual rounds are allowed; each
has the existing five-attempt ceiling. attempts counts the current round; retries
records each preceding round's outcome/count. A queued request does not change the
outcome until the worker consumes it. Reuse the **same request_id and body** after a
lost response: this returns the prior acceptance without another audit/send, even
if the worker has since completed. A different body/actor/job with that ID conflicts.
A fresh request needs a fresh review; generation prevents stale-review reuse after
an unknown → retry → unknown cycle. New concurrent IDs cannot queue another round.

The original call/release/action/fields/bot/chat never change. Later draft edits do
not change this review. Revoked immutable grants/targets cannot be restored by a new
grant or by retry; temporary issuer/workspace loss must first be resolved by the
existing authorized operator flow. Worker dispatch rechecks original authority and
the retry requester's enabled owner membership. It also compares approved message,
action and payload digest before HTTP; stale rendering fails closed.

There is no endpoint to claim an unknown delivery succeeded, supply a replacement
receipt, edit output, reroute an old event or reset queue rows. Declining retry leaves
the original outcome intact. A separate frontend, real Telegram permissions/delivery
acceptance and live migration remain pending. Read-only diagnostics:
[retry metadata](../../infra/examples/action_retries.sql).


## Prepared voice preview (AGP-06)

Set `ALOJAN_VOICE_ASSET_ROOT` to a private trusted store mounted **read-only** in the
management container. The optional setting leaves other endpoints compatible when
absent; audio returns 503. The preview route authenticates membership and the agent,
requires the current draft ETag (428 absent, 412 stale), and uses its qualified
model/preset/speech identity. Missing ready metadata returns 409. File unavailability,
corruption and symlinks return a sanitized 503. No paths or private text enter logs.

The server reads only one of two fixed filenames under UUID/digest directories,
verifies the manifest/file digest and bounded PCM structure, and returns at most
500,000 bytes with `Cache-Control: no-store`. The existing two-operation HTTP limiter
also bounds these requests. File work occurs after the DB transaction closes. No
Range API, raw audio recording, download token, upload, inference or shared asset
access across workspaces is introduced. The browser fetches with the version header
and destroys its blob URL when editing/navigating. New audio generation still needs
the separately planned acknowledged maintenance window.

## Audio preparation requests

`GET/POST /v1/workspaces/{scope}/agents/{profile}/voice-preparation` requires draft
If-Match. POST additionally requires the normal Origin/session/CSRF envelope and
an empty JSON object. Response status is missing/queued/preparing/ready/failed,
with attempt and sanitized failure_code. Only owner/editor can enqueue; no audio
work occurs in HTTP. Apply migration 0016 and updated management grants. See the
[private preparer](../voice-preparer/README.md) for execution and recovery.

## Call history read model

Migration 0017 indexes immutable route snapshots by workspace/time and profile/time.
Re-apply `grant_management` with the private operator DSN to add narrow SELECT
columns; existing RLS excludes foreign and unscoped legacy history. No call writes,
raw SIP identifier access, new worker or media-path query is granted. Detail reads
use a single SQL statement without row locks. Cursor ordering uses snapshot creation
and call UUID; displayed timestamps come from the call itself. Unknown/duplicate
filters are rejected. Reading an outcome cannot dispatch or retry a notification.

Back up before applying the additive migration. Its short lock/statement timeouts
fail closed; a large populated history requires an online index rollout. Existing
application images remain compatible with the added indexes and grants. See
[Linux rollout evidence](../../docs/validation/call-detail-2026-10-26.md).

Transcript migration 0018 adds a partial `(call_id,created_at,id)` index for finalized
caller and sent assistant rows. Re-apply `grant_management` for narrow SELECT
columns; writes and generation IDs remain denied. Empty aligned text with positive
sent audio is returned as empty, not invented. Pages are bounded to 50 rows; refresh
starts over rather than pretending live rows form a frozen transcript snapshot.
No recording URL, transcript export or unscoped historical reassignment is added.
The frontend retry dialog consumes the existing owner-only review/retry contract;
it does not introduce a new delivery endpoint or permission bypass.

## Scoped response timing (AGP-06/P1)

Migration 0019 adds immutable, content-free `call_latency` observations with a forced
workspace RLS read policy and composite route/release foreign key. Reapply
`grant_management` after migration. `GET /v1/workspaces/{scope}/performance` accepts
only optional `agent` and `call` UUID filters; duplicate/unknown filters are rejected.
All workspace reader roles may use it; foreign identities return 404. The response
contains aggregate counts/distributions only, never gateway identities or content.

The window is the newest 200 scoped calls, with at most 1000 imported turns per call
and 5000 samples per response. Limits/truncation are explicit. For completed normal
response turns with no gateway error, P50 is the median and P95 is the nearest-rank
95th percentile. Each metric separately counts missing values; failed, interrupted,
cancelled and recovery turns remain counted but are excluded from distributions.
Server VAD-end-to-audio is an estimate, not handset latency or acceptance evidence.

`python -m alojan.latency --node NODE` consumes at most 10000 lines on stdin,
recognizes existing gateway `turn_latency` records, retains only bounded numeric
fields/status/kind, and maps the gateway identity to its existing immutable route.
Unknown/unowned routes are ignored; nothing creates/claims calls. Replays are
idempotent per call/generation; overlap is serialized outside the live path. Use a
fresh dedicated role provisioned by `grant_ingest(dsn, role, node)`, not management or
administrator credentials. The role cannot read callers, transcripts, tokens, model
credentials or timing payloads and cannot update/delete samples.

The deployed collector runs once a minute in an isolated container using the pinned
management image, 0.25 CPU and 128 MiB; no HTTP listener or Docker socket inside it.
See [setup](../../docs/DEV_SETUP.md#background-response-timing-import) and
[evidence](../../docs/validation/performance-ui-2026-10-26.md). No media callback,
voice process, inference setting or serving release changes for this feature.

## MCP connections and discovery (AGP-07, backend slice)

Migration `0020_mcp_discovery.sql` adds immutable scoped connection identities and
leased discovery jobs. Apply migrations before provisioning/reprovisioning management
roles and starting the candidate image; readiness now requires migration 0020.
This slice does not enable MCP tools on agents or modify published releases.

| Endpoint under `/v1/workspaces/{scope}` | Contract | Permission |
|---|---|---|
| GET `/mcp-connections` | Up to 50 identities; no credential reads | Membership |
| POST `/mcp-connections` | `label`, `endpoint`, `auth_type`, `token`; 201 | Owner |
| POST `/mcp-connections/{id}/revoke` | `{}`; irreversible identity disable | Owner |
| GET `/mcp-connections/{id}/discovery` | Latest job ID/status/fixed failure code/unreviewed manifest | Membership |
| POST `/mcp-connections/{id}/discovery` | `{}`; 202, reuses pending job | Owner |

Origin, CSRF and workspace isolation apply. Saving never contacts the endpoint.
Auth is initially `none` with `token:null`, or `bearer` with a write-only 16–512
printable ASCII credential encrypted under a separate `mcp` purpose. Never put
credentials in a URL. Changing endpoint/auth requires a new identity. OAuth is not
implemented and unsupported auth values are rejected.

Endpoints currently require canonical lowercase ASCII DNS names, HTTPS/default 443,
an explicit simple absolute path, and no query, fragment, URL credentials, explicit
port or percent escapes. Internal endpoints and arbitrary stdio commands are unsupported.
Discovery also requires the exact endpoint in a private operator allowlist. Network
resolution is checked for every request; all returned addresses must be public.
The worker connects to a vetted literal while preserving original Host/TLS SNI;
redirects, ambient proxies and compressed responses are rejected.

Quotas per workspace: 50 retained connections (including revoked), four pending jobs,
ten requests/hour and 100 retained discovery jobs. Terminal snapshots cannot change.
There is no automatic cleanup that could invalidate future pinned manifests; raising
retention requires a reference-aware cleanup design. Discovery uses a 30-second
claim lease, a 15-second transport budget and an 18-second worker budget; expired
claims fail closed and require a new explicit discovery request. No network request
runs inside a database transaction or management HTTP handler.

Discovery supports the pinned MCP 2025-11-25 Streamable HTTP protocol, JSON and SSE,
up to ten pages/100 tools, 256 KiB response/manifest and 64 KiB SSE events. Schemas
are bounded and validated without external references. Names, schemas, descriptions
and read-only hints are hashed, but every tool remains `unreviewed`. Remote
annotations confer no execution permission. Literal credential echoes are rejected;
remote error text is not exposed. Cancellation/lease loss cannot commit partial data.

### Independent discovery worker

The optional `infra/compose.mcp-discovery.yaml` runs a separate 0.25 CPU/256 MiB
container using the existing frozen action-worker image. It has no HTTP listener,
GPU mount, call admission dependency or serving-process change. Use a dedicated DB
login with grants from the private migration identity:

```sh
PYTHONPATH=services/app-api:services/voice-contracts \
  uv run --frozen --env-file .local/dev.env python -m alojan.mcp_roles --role <dedicated-role>
```

Its private `.local/mcp-discovery.env` contains its scoped-privilege database DSN.
Workspace owners can save canonical public HTTPS MCP endpoints directly; discovery
and execution require no operator endpoint file or address approval. Runtime DNS/IP
pinning, private-address rejection and fixed credential destinations remain mandatory.
The key file uses the existing private credential key; management can seal but cannot
read stored MCP ciphertext.
The worker cannot read passwords, caller records, provider keys or Telegram keys,
create connections, authorize tools, or update connection identities.

The CLI accepts `--once` for an explicit one-job run. The process suppresses SDK/HTTP
log propagation and only records fixed error codes. Revocation blocks jobs not yet
started and discards a result if the connection was revoked during discovery;
already-started network requests may finish. Disabled workspaces/no enabled owner
are rejected before network access. Deployment remains pending until the remaining
agent-selection/grant/readiness work; current serving images stay unchanged.

Agent tool selection, reviewed capability grants, fixed/runtime argument separation,
schema drift invalidation, call execution and OAuth are subsequent AGP-07 work.

## Reviewed MCP selection and consent (AGP-07 authoring slice)

Migration `0021_mcp_tool_grants.sql` adds scoped immutable operator capability
reviews and per-agent owner grants. There are **no default approvals**. The HTTP
management role can select reviews but cannot create, modify or reactivate them;
the discovery worker cannot approve capabilities or create owner grants.

Operators inspect the actual implementation, destination and data permissions
before recording a read-only capability. Server annotations are hints, never proof.
Use private migration credentials, not the management service role:

```sh
python -m alojan.mcp_review --scope "$WORKSPACE_ID" approve-read \
  --connection "$MCP_CONNECTION_ID" --tool-digest "$REVIEWED_TOOL_DIGEST" \
  --reviewer 'operator-id' --evidence 'Reference to the completed implementation review'
python -m alojan.mcp_review --scope "$WORKSPACE_ID" revoke --review "$MCP_REVIEW_ID"
```

The digest must match a tool in the latest successful discovery. Reviews bind the
workspace, immutable connection, source discovery and exact description/input/output
schema digest. Reviewer/evidence text must contain no credentials or caller content.
Only read operations with qualified schemas can be reviewed; writes remain unsupported.

- `GET /v1/workspaces/{scope}/mcp-connections/{connection}/tools`: discovered
  metadata and the matching enabled `review_id`, or null for unreviewed/changed tools.
- Existing agent create/update accepts `mcp_tools` (at most eight). Each item has
  `connection_id`, `review_id`, a unique `mcp_` alias, optional `guidance` (1000
  characters), and `fixed_arguments` (8192 bytes). No credential or permission fields.
- `GET /v1/workspaces/{scope}/agents/{agent}/mcp-review`: current draft version,
  complete destination/tool/parameter review and digest. Model-visible input schema
  excludes fixed properties. The response explicitly says `execution_available:false`.
- `POST .../mcp-grants` with exactly `{draft_version,review_digest}`: owner-only
  consent for that review. Stale drafts/reviews fail. Concurrent identical requests
  return the same grant. Prompt text and tool selection alone confer no authority.
- `GET .../mcp-grants` lists grant IDs/digests/enabled state; `POST
  .../mcp-grants/{grant}/revoke` accepts an empty object and permanently revokes it.

Supported schemas are closed objects with named properties, required fields, nested
objects, bounded arrays (up to 100 items) and bounded strings (up to 4096 characters),
plus scalar types/enums and numeric min/max. Maximum schema depth is six and size
16 KiB. References, regex, general combinators and arbitrary additional properties are
unsupported. The bounded qualification revision below adds nullable scalar unions. Fixed values are validated at
save/review. The shared argument composer rejects fixed-field overrides, undeclared
fields and invalid runtime values, then validates the complete combined request.
Parameters are nonsecret business configuration; authentication stays in the encrypted
connection. No parameter values are copied to audit records.

A new discovery cannot add tools to a selection. A changed selected tool fails review;
unchanged selected tools survive unrelated additions. Pending/failed discovery,
revoked connections/reviews and a grant issuer who is no longer an enabled owner
block authorization. Historical grants remain immutable and do not silently retarget.

**Execution integration:** migration 0022 and the runtime stage below supersede the
original compiler gate. Catalog/consent responses still return
`execution_available:false`: a draft or permission receipt is not a node-readiness
receipt. No UI or production activation is included. MCP-free serialization preserves
historical digests. OAuth and real approved-server acceptance remain separate.

## MCP release pinning and execution (AGP-07 runtime slice)

Apply `0022_mcp_execution.sql` to an isolated candidate schema before provisioning.
Publication embeds the exact owner grant and operator-reviewed tools in manifest
version 3; versions 1/2 remain supported for existing agents. Preparation/publication
require current consent, connection and review. Rollback requires the original grant;
a new consent cannot silently resurrect an older revoked release. The complete tool
grant is limited to 64 KiB and the existing complete release budget stays 128 KiB.
The composite grant foreign key and manifest scope/profile checks bind ownership.

`mcp_tool_executions` records an immutable call/release/tool/turn identity and one
terminal outcome. It stores only validated structured outputs, never raw arguments,
server text/resources or credentials. Management receives scoped metadata read access,
not tool outputs or execution writes. A remaining `started` row means completion is
unconfirmed; it must never be presented as successful. Success records a validated
remote result, not proof that speech was delivered to the caller.

Provision a fresh non-inheriting login role with private migration credentials:

```sh
python -m alojan.mcp_execution_roles --role "$MCP_EXECUTION_ROLE"
```

This role can refresh scoped permissions/read encrypted MCP credentials and write
bounded execution evidence. It cannot change grants, reviews, connection/call state,
read account passwords/caller identities, forge terminal inserts or delete evidence.
Management provisioning rejects inherited column-level journal-write privileges.
See the [agent runtime contract](../agent/README.md#mcp-call-runtime-agp-07) for the
explicit node environment, readiness, cancellation and egress limits. Reapply management
grants after migration. Candidate images/migrations must not replace serving services
until the complete builder and rollout acceptance gates are satisfied.

## OAuth lifecycle (AGP-07, candidate)

Migration **0023** extends the immutable workspace connection with `auth_type=oauth`.
`mcp_oauth_flows` binds a ten-minute attempt to workspace, owner, original session,
hashed state/code, encrypted PKCE verifier and exact provider/redirect snapshots.
`mcp_oauth_credentials` stores purpose-bound encrypted access/refresh credentials,
expiry, refresh schedule, generation and a fenced worker lease. RLS and composite
workspace foreign keys apply. No access/refresh token is returned by the HTTP API.

- `GET /v1/workspaces/{scope}/mcp-oauth`: approved public provider metadata.
- `POST` at that path: owner-only `{provider_id,label}` starts an attempt and returns
  `authorization_url`; exact Origin/CSRF checks apply.
- `POST .../mcp-oauth/complete`: owner-only `{state,code,issuer}` consumes the original
  session's attempt once. A completed identical callback is idempotent within expiry;
  uncertain token exchanges cannot be replayed. No callback GET performs a write.
- Existing connection list returns `auth_status` for OAuth connections; existing
  discovery/revoke APIs apply. Expired or ineligible credentials fail readiness.

This is a restricted preregistered **public-client authorization-code + PKCE S256**
subset of [MCP authorization 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization),
following [OAuth security BCP](https://www.rfc-editor.org/rfc/rfc9700.html).
No dynamic client registration, client secret, implicit flow, automatic scope expansion
or remote revocation endpoint is implemented. Operator-pinned resource and AS/OIDC
metadata must confirm the exact issuer, resource, endpoints, minimal scopes, `S256`,
`code`, `none` token-endpoint authentication and authorization-response `iss` support.
Every authorization/token request includes the resource. Returned tokens must be
Bearer, 1–4096 printable ASCII characters, with 60–86400 second expiry and exactly
requested scopes (omitted scope follows OAuth's requested-scope semantics). Initial
refresh tokens are optional; refresh must rotate to a different refresh token.
Providers outside this subset require a separately reviewed implementation.

Copy `infra/examples/mcp-oauth-providers.json` to the ignored private
`.local/mcp-oauth-providers.json` and replace every synthetic value after provider
registration. Register exactly `${ALOJAN_PUBLIC_ORIGIN}/mcp-donus`; the registry
contains public metadata, never client secrets. The provider must accept that exact
origin/certificate; the private localhost preview is not a public-domain acceptance.
No separate resource endpoint allowlist is required. OAuth provider registration
still defines metadata/token URLs; the owner-selected endpoint policy does not alter
OAuth issuer/client registration. The shared bounded transport pins public DNS/IPs and TLS host,
disallows redirects/proxies/compression, and caps JSON responses at 32 KiB.

Combine `infra/compose.mcp-oauth.yaml` with the existing management, credentials and
MCP-discovery overlays. It supplies the same read-only registry to both services and
adds a separate outbound network to the otherwise internal management service.
Management HTTP remains separately contained. Registry changes require worker/API
restart; revoke affected connections before removing/changing a provider. Do not
use registry-file deletion as immediate access revocation. No new daemon is needed.

The existing discovery worker renews one due credential before one discovery job;
its resource limits still apply. Refresh is scheduled 60 seconds before the stored
expiry where possible (at least one second after creation for very short lifetimes),
with ten seconds of expiry skew. Runtime readiness requires over 30 seconds remaining;
its prepared permission cache expires after two seconds. Short expiry/backlog or
worker failure withdraws readiness rather than sending expired credentials. Refresh
network I/O never runs in the media callback or tool turn. A thirty-second claim and
eight-second exchange deadline fence worker races. Uncertain rotation or lost lease
requires reconnect; it is never blindly replayed. In-flight tool responses reject
both their originally sent token and the newly rotated token if echoed.

Re-run management, discovery and execution role provisioning after migrations:
management can insert credentials but only read credential metadata; the executor
can read access tokens but not refresh tokens; only the dedicated discovery/refresh
worker can rotate them. Flows are invisible to either worker. Normal account/owner,
scope, connection and tool-grant eligibility still applies on every readiness refresh.
Local revocation cannot recall already sent requests or revoke the provider's grant.

OAuth callback URLs must never enter ingress logs. The preview nginx config disables
access logging and suppresses callback error request URLs; preserve this policy in a
public ingress. Do not add callback analytics, third-party assets or URL-bearing traces.

[Migration and safe status-query examples](../../infra/examples/mcp-oauth-status.sql)
and [validation evidence](../../docs/validation/mcp-oauth-2026-10-26.md).

## Typed HTTP post-call actions (AGP-08 candidate)

Requires migration 0024 and re-provisioned management/actions roles. Existing native
workspace authentication, owner checks, Origin/CSRF protection and request limits
apply. Authoring/review never performs network requests.

- `GET /v1/workspaces/{scope}/http-connections`: bounded metadata for members.
- `POST .../http-connections`: owner-only exact `{label, endpoint, auth_type, token}`;
  `auth_type` is `none` with null token or `bearer` with a write-only token. HTTPS
  canonical DNS destination, port 443, fixed path, no query/fragment/URL credentials.
  At most 100 immutable connections per workspace, including closed entries.
- `POST .../http-connections/{id}/revoke` with `{}`: irreversible local revocation.
  Pending sends pause; already-authorized in-flight sends cannot be recalled.

Use the existing agent draft `post_call_actions`, review/grant/publication APIs.
HTTP and Telegram share the four-action cap. A current HTTP draft entry is:

```json
{
  "alias": "crm",
  "adapter": "http_request.v1",
  "connection_id": "00000000-0000-4000-8000-000000000024",
  "event": "call.finalized.v1",
  "condition": "answered",
  "method": "POST",
  "headers": {"X-Data-Team": "support"},
  "body": {
    "call": {"kind": "source", "source": "call_id", "on_missing": "fail"},
    "subject": {"kind": "source", "source": "summary.subject", "on_missing": "null"},
    "status": {"kind": "source", "source": "summary_status", "on_missing": "fail"},
    "active": {"kind": "literal", "value": true}
  },
  "query": {}
}
```

This is declarative data, never executable templates. POST/PUT/PATCH only; body has
1–16 flat fields, query 0–8; destination keys are ASCII identifiers up to 40 chars.
Sources are the existing 23 scalar event fields. Numbers/booleans preserve types;
missing source values require `null`, `omit` or `fail`. A missing required value
fails only its job. Summary fields require `summary_status`; phone fields require
the corresponding provenance field. No implicit transcript, secret, raw tool result,
audio, arbitrary model output or cross-call lookup is available.

Scalar literals are bounded to 2048 serialized bytes. Action configuration, including
reviewed target metadata, is bounded to 4096 bytes; a complete review to 16384 bytes.
Only four static printable `X-Data-*` business headers (256 chars each) are accepted.
Authentication, Host, Content-Type and idempotency headers are platform-owned. JSON
body is at most 64 KiB and encoded query at most 4096 bytes; never truncate an HTTP
payload. Expanded invalid review bounds return `invalid_action_intent` (400).

Review schema 2 pins target/method/mapping/headers/auth mode and fields; historical
Telegram-only reviews remain schema 1 with unchanged digests. The review response
adds `synthetic_previews` beside the signed review; fake values have no authority and
send nothing. Exact owner consent still applies to the review digest. Dispatch
checks the original grant, current enabled owner/workspace/target and pinned intent.
Secrets remain encrypted with purpose `http`; only the action worker may read them.

Delivery metadata adds nullable `http_status`. HTTP success means a complete 2xx
status header, not business completion. Response bodies are ignored. Retries keep
the original job UUID as `Idempotency-Key`, event, target and request; the receiver
must actually implement idempotency. Unknown outcomes never replay automatically.
The existing retry review exposes the exact rendered request without bearer secrets.
Retry review storage is capped at 320 KiB to accommodate two JSON escaping layers
plus bounded metadata; the outgoing body/query caps stay unchanged.

This slice does not implement custom extraction schemas, tool-output projection,
transcript sharing, dynamic paths, nested mappings or additional event conditions.
See [worker behavior](../action-worker/README.md#http-delivery-agp-08-candidate)
and [Linux evidence](../../docs/validation/http-actions-2026-10-26.md).

## Declared post-call outputs (AGP-08 candidate)

Agent drafts accept optional `outputs` (up to eight). Empty lists are omitted from
serialization to preserve historical digests. Each definition has unique ASCII
`name` (lowercase letter, digits/underscore, at most 32 characters; model-reserved
names rejected), `type`, `source`, `description` (1–160 printable characters), plus
nullable `tool_alias` and `path`. The editor exposes business fields, not technical
model tuning. Supported types: `string`, `number`, `boolean`, `string_array`,
`number_array`, `boolean_array`.

`source=conversation` uses only the already bounded conversation and durable note in
the existing summary request; tool_alias/path must be null. `source=tool` selects an
existing MCP alias and an explicit output-schema property path (1–4 object levels,
no array indexes, wildcard, arbitrary JSONPath or unreviewed properties). The tool
must be an operator-reviewed selected read capability and the property's declared
type must match. Nullable primitive schemas and numeric integer properties are
supported. Complex/union object traversal is rejected rather than guessed.

```json
{
  "name": "products",
  "type": "string_array",
  "source": "conversation",
  "description": "Product names explicitly stated by the caller; unknown means null.",
  "tool_alias": null,
  "path": null
}
```

Values are bounded to 1024 serialized UTF-8 bytes per field; strings to 512 characters,
arrays to eight items, finite numbers to absolute value 1e12. Boolean is never accepted
as a number. Invalid values become null/failed; unknown values become null/missing.
Missing or malformed extraction as a whole fails all conversation output fields,
without discarding a valid independent summary or successful tool projection. A model
parse/failure can fail the summary as well; no extra model retry/request was introduced.

HTTP mapping adds `outputs.<name>` and `output_status.<name>`. Selecting a value
requires mapping its status too. Declared values go only into the JSON body, never
query strings; status values may be used in queries. Existing null/omit/fail semantics
remain. Unknown names are rejected when saving. Tool bindings and selected definitions
are included in action review v3; changed description/type/property or tool connection/
review/fixed parameters invalidates reuse of the old output grant. Synthetic previews
preserve types and use no real call data. Telegram retains its existing scalar catalog.

Releases with outputs use version 4; finalization adds event version 2 with `outputs`
and `output_status` objects. Statuses: `done` (typed value, not truth/quality assurance),
`missing`, `failed`, `unavailable` (no eligible successful tool invocation). Each tool
field comes from the highest invocation ordinal that succeeded before the call ended,
inside the same scope/call/release. No fallback to another call, current draft, new
schema or new invocation. Latest successful invocation is explicit, not the most
recently completed asynchronous request. Only declared properties enter the event.

Scoped call detail returns nullable `outputs` and `output_status`; old calls have null.
Raw MCP outputs remain unavailable to management. The summary role gains column-limited
read access to execution records under existing workspace RLS; the API/actions/records
roles still cannot read raw tool outputs. Re-provision the summary role before enabling
v4 releases. No table migration or new service/dependency is needed. Coordinated
consumer/API/worker/web activation is required; old consumers reject new capabilities.

Example: [read-only PostgreSQL fragment](../../infra/examples/declared-outputs.sql).
[Evidence and limitations](../../docs/validation/declared-outputs-2026-10-26.md).

## Post-call summary conditions (AGP-08 candidate)

Telegram and HTTP `condition` accept only the following values:

| Value | Eligibility after an answered call ends |
| --- | --- |
| `answered` | Summary processing has terminated, whether it succeeded or failed; unchanged default. |
| `summary_ready` | Finalization has `summary_status=done`. This does not promise model accuracy, confirmed notes or completed external work. |
| `summary_failed` | Finalization has `summary_status=failed`, including unavailable credentials/model failure. Missing summary fields still follow the mapping's null/omit/fail policy. |

Conditions use durable finalization metadata, never caller/model instructions or a
substring in the hangup reason. No boolean expressions, arbitrary paths, no-answer
or interrupted-call condition is supported. `summary_ready` does not require every
optional extracted output to be present; per-field output statuses remain independent.

A non-default condition requires action-review v4 and release v5. Existing default
Telegram/HTTP/output schemas and digests are unchanged. The exact condition is in
consent, immutable release and job intent. Draft changes do not alter active calls
or queued jobs; changing conditions requires fresh review/consent before publication.
Unmatched actions create no delivery row; a matching action with missing required
mapped data may still fail rendering. No implicit fallback send occurs.

No new database migration/permission is needed. All release readers and action workers
must understand v5/v4 before activation. See the [read-only example](../../infra/examples/post-call-conditions.sql)
and [evidence](../../docs/validation/action-conditions-2026-10-26.md). The later lifecycle section adds no-answer/interrupted policies. Optional transcript
sharing is described below.

## Optional transcript sharing (AGP-08 candidate)

An HTTP action can set `transcript_policy: "bounded_text.v1"` and must map both
`transcript.text` and `transcript.status` into its JSON body. Query mappings and
Telegram transcript fields are rejected. Omitting the policy preserves historical
serialization. Exact owner review v5 pins the policy, destination and mappings;
release v6 pins it for the call. Review/preview never sends a request.

The mandatory greeting adds a fixed sharing disclosure before the editable question.
Changing sharing intent invalidates the prepared speech identity; old greeting audio
cannot publish the new release. After an eligible answered call ends, only final caller
and assistant rows with sent audio are selected in chronological order. Export caps
at 100 rows / 8192 UTF-8 bytes; control/bidi characters are removed. Status is `complete`,
`truncated`, `empty`, or `omitted_size_limit`. The last two have null text; existing
null/omit/fail mapping policy applies. `complete` means eligible retained text fits,
not a guarantee of perfect ASR or complete heard speech. Partial assistant playback
uses the same sent-row eligibility as call history, not word-level audio alignment.

No new raw-audio recording, semantic PII redaction, receiver retention guarantee or
retention cleanup is introduced. Existing workspace access/retention controls still
apply; copied final-event/job text shares their storage lifecycle. Only opted-in actions
receive transcript fields. Saving a later draft cannot alter pinned calls or queued
jobs. Real receiver acceptance remains pending. [Example](../../infra/examples/transcript-sharing.sql)
and [evidence](../../docs/validation/transcript-sharing-2026-10-26.md).

## Call lifecycle conditions (AGP-08 candidate)

`no_answer` and `interrupted` extend Telegram/HTTP conditions with action review v6
and release v7. Existing default/summary/transcript-only schemas/digests are unchanged.
No-answer means a scoped ended call with no persisted answer timestamp and final
summary state `not_requested`; no summary model is invoked. Unrouted cancellations
have no authorized recipient. Existing historical calls are never scanned or replayed.
Reconciled missing-answer events reflect observed records, not proof no handset answered.

Interrupted requires an answered ended call and the exact private native outcome
`disconnected` or `failed`. `completed` does not match. A remote BYE after a normal
farewell still counts; this is explicit in the UI. Caller/model prose never determines
eligibility. Summary success/failure still applies independently for these answered calls.

Unanswered final event v4 carries null summary/note/answer/duration and null declared
outputs with unavailable states; existing missing-field policy applies to delivery.
No-answer cannot opt into transcript sharing because disclosure cannot be played.
Sibling answered/transcript actions remain valid but cannot match the unanswered event.
A changed draft or condition cannot redirect pinned jobs. Synthetic preview illustrates
mapping shape, not a predicted call result; no-answer actual conversation fields are null.
Migration 0025, compatible consumers and refreshed private roles are required before
activation. [Read-only examples](../../infra/examples/call-lifecycle-actions.sql) and
[tests](../../docs/validation/call-lifecycle-actions-2026-10-26.md).


## Bounded remote schema qualification (AGP-07 candidate)

Operator review now accepts a deterministic `bounded.v1` qualification of common
remote schemas: scalar-plus-null `anyOf`/type unions, ignored `default` annotations,
and the output-only `x-fastmcp-wrap-result:true` annotation. Wrapped results remain
opaque strings; the executor does not interpret embedded JSON or instructions.
Missing object closure becomes `additionalProperties:false` only with explicit
properties. Explicit arbitrary properties, references, regex, general combinators
and nullable objects/arrays remain unsupported. Qualification imposes/intersects
4096-character strings and 100-item arrays, retaining smaller declared limits,
required fields, enum and numeric constraints. Six-level/16-KiB schema limits and
existing argument/result byte limits remain. Impossible minimum/ceiling combinations
are rejected. No default is injected: omission and explicit null are different.

The original manifest/tool digest remains unchanged. Qualified catalog entries and
release bindings additionally carry `schema_policy`, `input_schema`, `output_schema`.
The exact owner review pins these fields plus the fixed/exposed arguments in MCP
review v2; release v8 is required. Legacy strict bindings/review v1/digests are unchanged.
Consumers recompute qualification and reject missing, tampered or downgraded policy.
Fixed values validate against the qualified input, runtime arguments exclude fixed
properties, and combined requests/results validate against the same pinned bounds.
Declared output paths and the GUI consume the qualified output schema.

This adds no migration or automatic operator/owner grant. Roll out compatible readers
before publishing v8. The no-answer enqueue guard includes v8; old consumers cannot
safely consume those releases. Real Hindsight read acceptance and limits are recorded
in [evidence](../../docs/validation/mcp-schema-2026-10-26.md).


## Deliver2.ai-compatible schemas (AGP-07, deployed 2026-10-27)

Discovery accepts negotiated `2025-06-18` and `2025-11-25`. New `bounded.v2`
bindings preserve/enforce `uuid` and explicit-offset `date-time` formats and allow
omitted output schemas (`output_schema:null`). Such tools accept bounded JSON objects
from structured content or one JSON text block; they cannot supply typed post-call
output fields. Arbitrary text/media is unsupported. Declared output schemas remain
mandatory validators when provided. Existing 8-KiB result, depth, time and capacity
limits remain; use narrow filters and small pages. Date-time excludes leap seconds.

New bindings require grant v3 / release v9; older digests remain unchanged. Deploy
compatible API, runtime, background readers and host preparer before publishing v9.
The UI shows absent output fields without failing. No database migration is needed.
See [Linux/browser/live-provider evidence](../../docs/validation/mcp-deliver2ai-2026-10-27.md).

## Instruction variables

Drafts accept optional `prompt_template` (UI: Instructions → instruction variables):

```json
{
  "instructions": "You are {{agent_name}}, assisting {{owner_name}} for {{team}}. Today starts {{today_start}}; now {{current_datetime}}.",
  "prompt_template": {
    "version": 1,
    "timezone": "Europe/Istanbul",
    "variables": [{"name": "team", "value": "Example team"}]
  }
}
```

Merge these fields into the full draft when creating/updating through HTTP or the
management MCP; retain the expected version/operation key. Custom names match
`[a-z][a-z0-9_]{0,47}`; at most 16 values of 1,000 characters each and 8 KiB combined
JSON. Reserved names are `agent_name`, `owner_name`, `timezone`, `current_datetime`,
`current_date`, `current_time`, `today_start`, `yesterday_start`, `yesterday_end`.
Timestamps include UTC offsets; `yesterday_end` is the last microsecond before today's
local midnight. Use the destination tool's documented inclusive/exclusive bounds.

Values are literal, non-secret business configuration, visible to authorized draft
readers and sent to the selected model. Only the main instructions field is expanded;
greeting/prepared audio, summary templates and tool guidance retain their existing
contracts. Malformed/undefined names fail validation. No template means legacy
literal handling; removing it does not rewrite instruction text. Version-10 releases
pin definitions and timezone. All consumers/preparer must support v10 before rollout.
