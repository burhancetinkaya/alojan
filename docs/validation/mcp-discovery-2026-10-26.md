# MCP connection and discovery backend — 2026-10-26

AGP-07 / M4,M5, ADR 0011; requirements §9.3/12/14–16.
The owner requested continuing the approved plan. This is the connection/discovery
backend slice, not completion of MCP tool execution or the builder.

## Implemented contract

Migration 0020 introduces workspace-scoped immutable connection identities and
leased discovery jobs/immutable terminal snapshots. Connections are anonymous or
bearer-authenticated; encrypted credentials are bound to workspace, connection ID
and `mcp` purpose. Management can insert ciphertext but cannot read it. Endpoint,
authentication and identity cannot be retargeted or reopened after revocation.

Existing origin/CSRF/native-session boundaries protect the new create/list/revoke and
explicit discovery/status APIs. Saving never contacts an endpoint. Concurrent pending
requests reuse one job. Quotas bound workspace connections, pending/hourly requests
and retained snapshots. API readiness now requires migration 0020. The private role
provisioners must run after the migration; existing applied migrations are unchanged.

A separately provisioned consumer, optional Docker overlay and one-job CLI perform
discovery away from voice and HTTP request handlers. The worker has no caller-record,
password, provider-key or Telegram-key privileges. Network operations happen outside
DB transactions. Failed/expired claims never auto-retry; the claim token and lease
fence late completions. Revocation during discovery discards the snapshot. Disabled
workspaces or no enabled owner prevent network access before discovery begins.

The supplied httpx2 transport enforces one canonical HTTPS/default-port DNS endpoint,
checks every DNS answer, rejects private/transition/multicast addresses, connects to
a vetted literal with original Host/TLS SNI, and blocks redirects, ambient proxies
and compressed responses. Every outbound endpoint must first appear in a private
operator allowlist. No credential leaves for an unapproved endpoint. Each discovery
has its own authenticated client/session; no sessions are shared between workspaces.

The existing frozen MCP 2.3.0 SDK implements protocol 2025-11-25 JSON and SSE discovery.
Budgets: 15-second transport, 18-second worker, 30-second claim, ten pages, 100 tools,
256 KiB response/manifest, 64 KiB SSE event and bounded schema depth. JSON Schema
validation never follows external references. Tool names, descriptions, schemas and
read-only hints are hashed; every tool remains `unreviewed`. SDK/server error text
is discarded in favor of fixed codes, and literal credential echoes are rejected.
No tools/call, model callback, dynamic UI code, execution grant or agent release
change is implemented by discovery.

The PostgreSQL example is disabled, credential-free and ends in ROLLBACK. Full API,
constraints, role provisioning, private config and Compose instructions are in the
[management README](../../services/app-api/README.md#mcp-connections-and-discovery-agp-07-backend-slice).
Dependency compatibility and upstream references are in [DEPENDENCIES](../DEPENDENCIES.md#mcp-discovery-compatibility-2026-10-26).

## Validation

Primary Linux host, fresh disposable DB schemas, existing frozen dependencies:

- Focused pre-final suite: **45 passed in 6.38s**, no skips. Covers scoped ownership,
  viewer/editor rejection, CSRF, ciphertext/purpose isolation, immutable snapshots,
  pending deduplication/quotas, restricted worker roles, privilege reprovisioning,
  disabled workspaces, cancellation, lease expiry/fencing and revocation mid-fetch.
- Actual SDK tests negotiate JSON and SSE, paginate tools without calling them,
  verify the pinned IP/original Host/SNI and fixed bearer header, and reject bad
  protocol, schema, repeated cursor, credential echo, mixed public/private DNS,
  compressed/oversized replies and redirects. HTTP transports are synthetic: no
  external server, socket TLS handshake, provider credentials or real network acceptance.
- Final combined suite: **114 passed in 43.71s**, no skips, including 46 MCP cases
  and native auth, provider/Telegram connections, releases, number routing and legacy
  upgrade checks. Final review added a regression against overprivileged management
  roles inserting forged discovery results. The earlier 108-case run passed in 43.83s;
  these overlapping runs must not be summed as unique tests.
- Real candidate management container passed registration, scoped drafts, model/
  number guards, anonymous MCP create/list/queue/deduplication/revoke and logout,
  with a temporary restricted DB login. No discovery worker or outbound network
  was started by this HTTP validator; the queued job/schema were removed afterward.
- Existing HTTPS frontend suite: **18 passed in 44.5s**, no skips/retries, against
  management image `sha256:78871343119f2b713efd0725d4670c5564ea14c692be6de84a481e81ca12904e`.
  Evidence: `.local/web-validation-0c03f14d116a40bcb9a0308e1d7d96ed/`. This preserves
  registration, prepare/publish/bind, permissions, lifecycle controls, history,
  transcript, retry and performance behavior. The final candidate below only adds
  the private role-provisioning guard; HTTP handler code is unchanged, and the final
  container HTTP check plus 114-case suite passed with that guard.
- Both images built successfully. The worker's CLI/import smoke passed in a container
  with network disabled. The optional worker is not started on the serving project.
- Ruff check/format and full scoped diff review passed. Unrelated dirty work preserved;
  no commit, push, PR or merge. The code graph was refreshed without publishing cache data.

Initial focused run: 30 passed, two failures and four setup errors. Corrected the
PostgreSQL DELETE privilege check (table-level, not column-level), adapted actual SDK
v2 snake_case fields and list parameter types, and rebuilt streaming responses so a
prebuffered test response cannot bypass the byte bound. Subsequent 39/40-case checks
passed; final tests add SSE, cancellation and malformed/credential-echo cases.
No initial failures or missing checks are represented as acceptance.

Management candidate image:
`sha256:8f66fbcdc68458bf2cad3950d04692bdab838a34b405e93178d98da74f7e2a2a`.
Discovery worker candidate image:
`sha256:2aaed9efac68d8f763ad7714e3cf442c47a9acc8c938de8ebde6f064974c005a`.
The synthetic browser harness is pinned to the new management candidate.

## Deployment and limits

Source was synchronized to the authorized Linux workspace and tested there.
Migration 0020 has only run in disposable schemas. Serving management, voice,
Telegram and web containers remain unchanged; no existing owner's configuration,
number mapping, external send or live call was touched. Retain the currently serving
images until agent capability/grant/release integration is validated. No live rollback
is needed for these unactivated candidates.

Remaining AGP-07 work: reviewed read capabilities, explicit per-agent selection and
fixed/runtime arguments, owner grants, immutable release pins, schema drift/readiness,
revocation during actual tool execution, bounded/redacted results, builder UI and OAuth.
Real endpoint authorization/credentials and real TLS/server acceptance remain separate.
The endpoint subset currently excludes custom ports, URL queries/escapes, internal
hosts, stdio and OAuth. Expanding it requires deliberate validation, not a bypass flag.
There is no GPU, model, latency, simultaneous-call or carrier acceptance in this slice.
