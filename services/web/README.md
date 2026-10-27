# Alojan management frontend

AGP-06 / M2,M5, ADR 0011, requirements §1/12/14–16. The owner approved the
flat mockups on 2026-10-26 and selected a private preview before a public domain.
Next.js App Router and generated shadcn/ui components call the existing scoped API.
This is an independent HTTP service, outside SIP/RTP, inference and call handling.

## Delivered slice

- Native registration/login, secure session, logout and password change.
- Three-step first-use journey: account creation, optional first agent draft, and
  preparation checklist. Saved drafts resume through the workspace after reload.
- Workspace-scoped agent listing, creation and full draft preservation on edits.
- Identity, instructions, approved model/EMA selection, speech wording and note tool.
- Telegram action creation/removal, schema-based output selection, exact destination
  review, explicit owner grant/revocation, write-only connections and delivery metadata.
- Pending number claims, explicit verified-number/release binding and reviewed routing stop.
- Reviewed provider/Telegram connection revocation; dependent agents must select a new connection.
- Saved greeting text and prepared greeting/unavailable audio playback, durable audio
  preparation requests/status, prepare/publish review and missing-asset blocking.
- Scoped, paginated call list with agent filtering and direct-link detail: historical
  identity, timing, summary, latest note/confirmation and notification outcome.
- On-demand, paginated finalized transcript; unsent assistant text is excluded.
- Scoped performance view with agent filtering and per-call timings: P50/P95,
  excluded/missing sample counts and bounded-window explanations.
- Owner-reviewed delivery retry with exact target/message, explicit duplicate-risk
  consent, stale-review recovery and lost-response idempotency.
- Bounded release history and owner-reviewed rollback to an immutable prior release,
  with version conflicts and uncertain responses requiring a refreshed review.
- Candidate MCP connection/discovery controls, reviewed agent tool selection,
  typed fixed parameters and exact owner permission/revocation, including old grants.

Draft saving never changes the bound release. Publication and number assignment are
separate actions. Version conflicts preserve unsaved input. Hidden configuration
is retained when saving the complete draft. Credentials and sessions are never
put into browser storage; the API owns the HttpOnly/Secure/SameSite cookie and
checks workspace permissions, exact Origin, CSRF and optimistic versions.

Real-provider OAuth acceptance, the HTTP action builder and public email recovery remain follow-up work. The self-service
publication journey is verified through synthetic voice/operator/routing boundaries;
new-agent carrier acceptance and public launch remain separate. One qualified voice is available;
technical engine settings remain system-owned.

## Build and test on the primary Linux host

Use the Node and browser image digests pinned in `Dockerfile` and
`tools/validate-web.py`. Source directories are copied without `node_modules`,
`.next`, test output or secrets. Install with `npm ci`; run `npm run typecheck` and
`npm run build` within the Node container, limiting it to two CPUs and 2 GiB.
`npm run build` uses webpack for a repeatable standalone server build. Formatting
uses the one-off pinned `prettier@3.8.3`; it is not a runtime dependency.

The backend rewrite is **build-time configuration**. Production defaults to
`http://127.0.0.1:18081`. For isolated browser validation build with
`ALOJAN_MANAGEMENT_URL=http://127.0.0.1:18181`, then from the repository root run:

```sh
PYTHONPATH=services/app-api:services/voice-contracts:generated/python \
  ~/.local/bin/uv run --frozen --with httpx==0.28.1 --env-file .local/dev.env python tools/validate-web.py
```

The harness checks the built rewrite before starting, migrates an isolated schema,
uses a restricted DB role, creates synthetic accounts and credentials, and runs
real HTTPS browser tests against an independent API container. It drops its schema,
role and containers in `finally`; synthetic screenshots/traces remain in `.local`
and ignored test output. No serving voice process, network model or delivery worker is
started. A private file bridge runs one queued preparation with a synthetic generator
and operator/node fixtures only in the disposable schema; it validates call pinning
and stopped-number rejection without SIP traffic. No test bypass API is exposed. Certificate verification is bypassed only for its local synthetic TLS.
It requires the management image already built by the platform validation step.
The harness pins the MCP-capable candidate image; `ALOJAN_WEB_MANAGEMENT_IMAGE` can
select a newly validated candidate explicitly. It never updates the serving image.
Eleven browser-only MCP/OAuth fault/role/mobile contracts intercept API responses; the other
19 scenarios use the real restricted API, including MCP selection and consent.

## MCP builder (candidate only)

In Connections, owners add an exact HTTPS endpoint with no authentication or a
write-only Bearer token. Saving does not contact the endpoint. Discovery requires
confirmation of the server and uses the separate worker; status refresh only reads
the stored result. The operator must allow the endpoint and review individual read
capabilities before they become selectable. This screen cannot approve remote code
or infer rights from an MCP annotation. The candidate OAuth flow is described below.

In the agent's Tools tab, select a connection and reviewed tool, give it an alias and
usage guidance, and optionally fix top-level parameters. Reviewed closed schemas
render typed scalar, enum, object and bounded-list controls; unspecified fields
remain model inputs. Remote descriptions are escaped text. The API remains the
authority for schema/value bounds, catalog drift, tenant rights and release validity.

Apply changes, save the draft, then review exact endpoints, tools, fixed values and
runtime/output fields. Only owners can grant permission; editors can configure and
inspect. A changed or uncertain permission response closes the review and reloads
grant state without automatic resubmission. Publish and bind separately.

Removing a tool from a draft does not revoke published permissions. Previously
issued grants remain listed and can be explicitly revoked by ID, even after the
selection is removed. Revocation can withdraw affected releases from new-call
admission; requests already sent cannot be recalled. Connections are immutable:
replacing credentials requires a new connection and a reviewed release.

No browser requests are added to SIP/RTP or per-turn inference. No dependency,
engine setting or additional production service is introduced by this UI slice.
Candidate backend migrations 0020–0023 and runtime services must be rolled out
together before enabling these screens in the private preview. See
[MCP UI evidence and remaining gates](../../docs/validation/mcp-ui-2026-10-26.md).

## Private preview

Build `services/web` as the Docker context and pin the resulting image ID in
`ALOJAN_WEB_IMAGE`. `infra/compose.web.yaml` supplies the separate non-root,
read-only web and TLS services. Set `ALOJAN_WEB_TLS_DIR` to a private directory
containing `cert.pem` and `key.pem` (UID 1000-readable, mode 0600 key). Both
listeners bind loopback. The web service is limited to 0.5 CPU/512 MiB; TLS to
0.25 CPU/64 MiB. There is no voice dependency or public port publication.

Set management `ALOJAN_PUBLIC_ORIGIN=https://localhost:13443`, preserving every
other environment value and secret. Back up its configuration, then recreate only
`management-api` using its existing project/configuration. Keep the other services
running. Launch the web compose project separately and verify both health checks.
Do not use `--remove-orphans` with any partial compose configuration.

Forward local port 13443 to the same loopback port on the authorized host over SSH
and open `https://localhost:13443`. The preview uses a self-signed, 30-day
localhost certificate; browsers require an explicit exception. It is not a trusted
public certificate. Production needs a real domain/certificate and matching API
origin. A laptop sleep or lost SSH connection can close the private preview tunnel;
reopen it using the same port. No internet tunnel or public preview was created.

Owner initial credentials are in a private ignored file, never documentation or
logs. Change the password through Account after first login. Existing native
operator recovery remains available; this UI does not invent an email-reset flow.

Rollback: stop only the `alojan-web-preview` project and restore the backed-up
management origin/configuration, recreating only management. No DB migration or
voice rollback is required for this frontend slice.


## Prepared audio and Telegram consent

Mount the trusted voice asset store read-only into management and set
`ALOJAN_VOICE_ASSET_ROOT` to that container path. This serves existing validated
WAVs only; it never starts synthesis. The selected clip is loaded as a bounded
private blob and revoked on draft changes/unmount. The document CSP allows this
blob only as media. Missing audio remains a publication blocker.

In Call aftermath, add a Telegram action, select its connection and fields, then
save the draft. Review the exact server-returned target and fields before explicitly
granting permission. Publish and bind a version separately. Removing an action from
a draft does not revoke the standing grant of a serving version. For the current
saved configuration, open its permission review to revoke the matching grant; this
can stop notifications from versions that use it. Existing in-flight sends may finish.

See [validation](../../docs/validation/web-actions-2026-10-26.md). The synthetic browser
harness also uses a separate synthetic call workspace with one bound number and
one uncertain delivery. Retry requests remain unconsumed; transport is an in-memory
fake. Nothing is sent externally.

Audio preparation is explicit through “Sesi hazırla”. The UI shows durable queue
status, polls pending work every five seconds and aborts requests on draft changes
or navigation. Ready audio can be played; retries are bounded. The displayed
maintenance notice explains the brief new-call pause. Publication remains separate.


## Release history and rollback

“Sürüm geçmişi” loads the existing bounded release list on demand (latest 100).
All workspace roles can read; only owners can select a prior release and confirm
its publication. The current publication is labeled separately from number routing.
The selected immutable revision, optional identity/digest and rollback lineage are
shown; no mutable draft is presented as the old release's content.

Rollback creates a new revision from the selected manifest and validates the current
model, assets, connection and action grants. It preserves drafts, number bindings and
pinned calls. Route the new release separately through Numaralar after readiness.
Unsaved drafts block confirmation. Publication versions prevent stale writes; a
failed or uncertain response disables submission until history is refreshed and the
owner explicitly selects again. No automatic retry or rebind occurs.

[Linux/browser evidence](../../docs/validation/release-rollback-ui-2026-10-26.md).


## Registration and first agent

`/kayit` collects the account holder name, email and password. Successful registration
opens authenticated `/baslangic` with the display name prefilled as assistant owner;
the agent identity and instructions are independently editable. The first agent is
created only on explicit form submission through the existing CSRF-protected scoped
API. Model/voice/engine defaults remain server-owned. No new endpoints or migrations.

Skipping creates no agent and displays an empty-state choice. A saved draft leads
to the three-step checklist for voice/model preparation, number verification and
optional Telegram setup. Checklist links open existing management screens; they
never synthesize, publish, bind, grant or send automatically. Reloading a completed
or uncertain creation returns to the saved agent list. Unsaved form text is not
persisted across reloads; passwords/sessions are never put into browser storage.

Repeated submission is guarded while requests are pending. An ambiguous registration
response probes the existing session once; without confirmation it clears the password
and directs the user to login. Ambiguous agent creation disables resubmission and
links to the saved agent list. Ordinary server validation errors preserve the form.
This avoids blind retries without changing the existing creation API contract.

## Lifecycle controls

Owners can stop a bound number from accepting new calls after reviewing the masked
number. Existing calls retain their release and history. To resume, explicitly bind
a ready release again. A concurrent binding invalidates the review; uncertain
responses refresh current state without automatically repeating the mutation.

Owners can close provider/Telegram connections after reviewing the saved target.
Closed immutable connections cannot reopen; create a replacement and update affected
agents. In-flight operations may finish. Cancellation never writes. These controls
use existing scoped/CSRF APIs; number mutation also carries its reviewed version.

[Self-service journey and lifecycle evidence](../../docs/validation/self-service-journey-2026-10-26.md).

## OAuth account connection (candidate only)

Owners select an operator-approved provider and label, then review the exact issuer,
authorization page, resource and scopes before leaving Alojan. The provider receives
only its preregistered client identity and the OAuth request; no Alojan login token.
`/mcp-donus` clears callback parameters from browser history immediately and disables
referrers. A subsequent same-origin request uses the existing Strict session cookie
and CSRF token. A different or expired session, missing issuer, duplicate parameter,
provider error or non-owner workspace fails closed. The code is exchanged once;
an uncertain result asks the owner to inspect connections before starting again.

Account connection does not discover tools, grant tool rights, publish or route an
agent. OAuth credential renewal preserves connection identity; expired/uncertain
refresh requires a new connection and explicit reselection/review. Revocation stops
Alojan use, not the provider's own account authorization. Remove the provider-side
grant separately if desired. No browser storage contains access/refresh tokens.

Provider setup, exact supported protocol subset and staging gates are documented in
[management OAuth](../app-api/README.md#oauth-lifecycle-agp-07-candidate).

## HTTP connections and post-call mapping (AGP-08 candidate)

Bağlantılar now includes owner-only fixed HTTPS targets with optional write-only
bearer credentials. Creating a connection sends no request. Closing it requires
review; uncertain creation disables resubmission until the saved list is refreshed.

Each agent's Çağrı sonrası tab can combine Telegram and HTTP within the four-action
cap. HTTP offers POST/PUT/PATCH, source or scalar-literal JSON/query fields, explicit
null/omit/fail behavior and restricted static business headers. Selecting summary
or phone fields adds their status/provenance field. Typed mapping and exact endpoint
are visible before granting; the synthetic request preview uses no real caller data
and cannot send anything. Saving a draft, approving and publishing remain distinct.

Owners inspect the exact original request and duplicate-operation warning before
manually retrying an uncertain delivery. Secrets are never included in review/browser
storage. Access, target/mapping limits and immutable intent are enforced by the API.
Existing standalone Next container and shadcn components are reused.

Primary Linux final: 31 browser checks in 55.4s (20 real scoped-API journeys, 11 intercepted
MCP/OAuth UI contracts). The new HTTP journey covers connection, typed mapping,
synthetic preview, consent/revocation and 390px layout without external requests.
[Final evidence](../../docs/validation/http-actions-2026-10-26.md).
Custom extraction, tool-output projection and additional event conditions remain
next AGP-08 work; this UI is not evidence of live receiver acceptance.

## Declared conversation/tool output editor (AGP-08 candidate)

The Çağrı sonrası tab now includes up to eight named business fields with descriptions,
scalar/simple-array types and conversation or selected-tool sources. Reviewed tool
schemas supply fixed property choices; server-side validation rejects unsupported paths
or type mismatches. No technical model settings are exposed. Mapped names/removal stay
locked until their HTTP references are removed, avoiding dangling destinations.

HTTP body selectors include declared values and automatically add their status mapping.
Query selectors exclude declared values. Exact output definitions/tool bindings and a
synthetic typed preview appear in owner consent. Editing the configuration requires a
fresh draft save/review; no preview sends or additional tool calls occur. Scoped call
detail shows escaped values and clear missing/failed/unavailable states. Old call data
continues to render without custom fields.

[Linux browser and integration evidence](../../docs/validation/declared-outputs-2026-10-26.md).
This remains candidate-only; real model quality and external receiver acceptance are
separate from synthetic browser/database validation.

## Post-call condition controls (candidate)

Each Telegram/HTTP action shows “Ne zaman gönderilsin?” with all answered calls,
summary ready, or summary failed. The default preserves existing behavior. Both the
editor and owner-review dialog explain/show eligibility; a changed condition clears
the displayed grant and requires saving plus a fresh exact review. Unmatched calls
do not produce delivery rows. Summary success is distinct from extracted-field
availability and real external delivery. The later lifecycle section adds no-answer/interrupted options. Transcript sharing is described below.

Real scoped-API browser checks cover HTTP persistence/reload/changed-consent and
Telegram publication/revocation with the chosen condition, including mobile review.
[Evidence](../../docs/validation/action-conditions-2026-10-26.md).

## Explicit transcript sharing control (candidate)

Each HTTP action has an initially unchecked sharing control. Enabling adds paired
text/status body fields; disabling removes them and the policy. Query selectors never
offer transcript fields. The editor and exact recipient review explain the 100-row /
8 KiB limit, sensitive data/no automatic redaction, no audio/reasoning and mandatory
greeting disclosure. A fresh compatible prepared greeting is required for publication.
The real API browser journey verifies enable/save/reload/review/grant/disable, greeting
preview and mobile layout. [Evidence](../../docs/validation/transcript-sharing-2026-10-26.md).

## Unanswered/interrupted condition controls (candidate)

Both adapters offer unanswered calls and caller-hangup/failed-call conditions. The UI
explains that unanswered calls have no summary and caller hangup can be an ordinary
farewell. Exact owner review repeats the selected condition and covers routed calls,
not only answered conversations. No-answer selection disables transcript opt-in;
existing sharing disables the no-answer option until the owner removes sharing.
Server validation enforces the same rule. Call history labels terminal `not_requested`
as “Özet istenmedi”. The real API browser test covers persistence, exact grants, condition
changes, mutual exclusion and mobile layout. [Evidence](../../docs/validation/call-lifecycle-actions-2026-10-26.md).


## Qualified MCP parameter controls (candidate)

Reviewed qualified catalog entries expose the bounded input/output schemas separately
from the original remote manifest. The parameter editor uses the bounded schema;
nullable scalar controls distinguish a fixed null, a fixed typed value, and an omitted
fixed value that remains available to the agent. No remote default is silently copied.
The permission dialog explains bounds and server defaults; declared output selection
uses qualified properties. A real scoped-API browser journey covers save/edit, null vs
omission, string bounds, exact v2 review/digest changes and permission creation.
[Evidence](../../docs/validation/mcp-schema-2026-10-26.md).
