# Management MCP implementation evidence — 2026-10-27

Mapping: MCP-01–06, AGP-06/07/09, M4–M5, requirements §11.3, accepted ADR 0012.
The owner authorized implementation and `<DEPLOYMENT_HOST>` through a Linux
Cloudflare Tunnel. **Public HTTPS deployment and basic client acceptance passed.**
The full voice/publication/activation and matched performance gates remain open.

## Primary Linux deployment and public acceptance

Final source synchronized after a remote comparison, with differing originals retained.
Primary Ubuntu host, isolated database/browser fixtures:

- **217 passed in 160.10s**: tokens, HTTP MCP, credential handoffs, call search,
  release status, authentication, calls, drafts, preview, releases, number routing,
  grants, outbound MCP/OAuth, delivery, connections and voice/publication jobs.
- **45 browser tests passed in 1.3m** against the production Next build and restricted
  API role. Typecheck, production build, Ruff, whitespace and nginx validation passed.
- The first browser runs exposed missing MCP endpoint fixture configuration and an
  extra registration consuming the shared five-attempt abuse budget. The fixture now
  creates a separate synthetic token user; production rate limits were not relaxed.

Built and deployed Linux amd64 images:

- API: `sha256:5f30131b75d94781ffd80ced654c2e24e1a8521be051535f3c487b5fd1aab86f`.
- MCP: `sha256:8c8e61102ca1835b26ea6f5818581ceb48f92b9e053e8825ac874299eb359312`.
- Web: `sha256:ebc8a32f50f173a5473cf27e547a8604776b18f798d6b1af96646b10ca09097a`.

Verified a private database backup, applied migrations 0027–0029 (30 ledger entries),
and refreshed restricted management grants. Nine existing voice/background containers
retained their identities; profiles, publications and number-binding fingerprints stayed
unchanged. An initial Compose failure (an unquoted comma split a tmpfs entry) restored
API/web images automatically; the corrected configuration was inspected and retried.
Additive migrations were retained. No voice container restart was needed.

The owner approved the final public exposure after reviewing the prepared route.
The existing host-network tunnel now has one additional hostname,
`<DEPLOYMENT_HOST> → http://127.0.0.1:13080`. Existing routes were preserved.
The independent nginx ingress routes web and `/mcp` to loopback services. The public
API/browser/MCP origins agree; the API trusts only the local ingress for Cloudflare
client-IP authentication budgets. No database or internal API listener is public.

Public HTTPS evidence:

- Login HTTP 200, anonymous MCP HTTP 401, actual Chrome login screen rendered.
- Installed **Codex CLI 0.163.0-alpha.10.2** discovered the server and 26 permitted
  tools with bearer authentication and no discovery error.
- Installed **Claude Code 2.1.87** reported Connected over the public HTTPS URL.
- Official MCP SDK created, read and updated one synthetic agent draft; an identical
  write retry returned the same result and exactly one agent. Scoped call query
  returned the synthetic workspace's empty call list.
- Fifteen sequential list calls: median **184.0 ms**, maximum **220.9 ms**, including
  the Cloudflare network path. This small smoke sample is not a voice/load benchmark.
- Revoking the test token made the next public MCP request return 401. The synthetic
  account was disabled; its audit/draft records remain. Claude Code also rejected the
  revoked token in a new connection attempt. No live number, real call,
  external provider action or notification was changed.

Client checks used temporary configuration and no model turns. Mutation acceptance
used the official SDK, not a model conversation in either CLI. No user client settings
were permanently changed. Temporary test credentials were held in ignored mode-0600
files and removed after revocation; they never entered evidence.
Linux logs/backups: `.local/management-mcp-linux/`; browser fixture evidence:
`.local/web-validation-cc9d76de485748a588f86a94158d5abd/`.


## Implemented

- Personal token creation/list/revocation UI and API; copy-once 256-bit secret,
  verifier-only storage, workspace/role/scope binding, expiry/password revocation,
  shared rate budgets and separate browser/bearer processing lanes.
- Separate frozen Python MCP app and resource-limited Docker service. Official SDK
  Streamable HTTP, strict hosts/origins, no cookie fallback, bounded requests and
  upstream responses, secret-free errors and no-store responses.
- [51 explicit tools](../MANAGEMENT_MCP_OPERATIONS.md), with underlying business
  authorization: agent configuration, connections, tool discovery/grants, prepared
  audio preview, publication/number activation and calls/deliveries/performance.
- Atomic operation-key retries, conflicting reuse rejection and seven-day replay.
  Expired payloads compact lazily; key identities remain as non-reexecuting tombstones.
- Literal bounded summary/transcript search, filter-bound cursors, scoped ownership
  and separate transcript permission. No caller partial/unsent assistant matches.
- Same-user expiring browser credential handoff. Originating token revocation and
  password changes prevent unfinished handoffs. Completion retries create one
  connection and never return its secret. Existing OAuth consent remains browser based.
- Additive migrations 0027–0029, restricted-role grants, synthetic SQL examples,
  nginx origin template and [setup guide](../../services/management-mcp/README.md).

## Checks and environment separation

Primary Linux, before SSH became unavailable:

- Token/native-auth foundation: **25 passed in 17.10s**.
- Initial HTTP MCP integration: **4 passed in 2.13s**.
- These are early-source results, not acceptance of the final source below.

Supplemental Mac checks with an isolated PostgreSQL 17.4 Docker database and
per-test schemas, synthetic accounts/numbers/audio only:

- Final focused suite: **74 passed in 47.43s** — personal tokens, HTTP MCP,
  credential handoff, call search, native auth, call management, agent drafts,
  voice preview and migrations/database regressions.
- Shared business regressions: **142 passed in 100.39s** — releases, number routing,
  action grants, outbound MCP tools/OAuth, delivery management, provider/Telegram
  connections, voice jobs and publication activation.
- Additional official SDK client test: **1 passed in 1.28s** — initialize,
  list tools and invoke context through the HTTP adapter using the installed client.
  This uses ASGI transport; it is not Codex/Claude cloud network acceptance.
- Real local HTTPS production-Next browser flow: **1 passed in 2.9s** — register,
  issue limited token, reject agent write, complete same-user credential form,
  hide secret after navigation and revoke access. Chromium, no external delivery.
- Web typecheck and production build passed. Ruff and whitespace checks passed.
- Independent MCP Docker image built and started on Mac Docker ARM64:
  `sha256:aa0bcf0040d3bf305321a14159e4d73f88bf40d71d29c5982bc3bc53bc6bb9a5`.
  Container health, unauthenticated rejection and Host rejection passed. This is not
  the Linux deployment image or an amd64/GPU performance result.

Earlier supplemental suites passed as recorded in ignored local logs; they are
not added to the final test totals. One initial new test used an incorrect nested
number-response assertion; corrected to the existing top-level `release_id`.
Review fixed active-token visibility behind revoked history, malformed cursor ID
handling, response-timeout double-start, transcript discovery permissions and old
retry result retention. Regression tests cover the relevant paths.

Logs under ignored `.local/management-mcp-review/`: `final-tests.log`,
`business-regressions.log`, `sdk-client-test.log`, `browser-tests.log`,
`web-build.log`, `image-build.log`. Temporary fixture containers are disposable;
no production data, external notification or live carrier test was used.

## Remaining gates

1. Matched voice baseline versus management load, query-plan/load checks and full
   recovery/soak coverage on the primary host. Process separation and a small HTTP
   sample do not establish measured voice performance equivalence.
2. Real-client conversational create/configure/voice-prepare/publish/explicit activation
   with an authorized verified test number, followed by real call/summary/transcript
   inspection. Existing synthetic publication tests do not replace real inference.

Public ingress and basic client compatibility are complete. Do not mark the entire
MCP-06 acceptance or live-test-readiness goal complete until its remaining gates pass.


## Client and readiness follow-up

The owner clarified that Codex and Claude Code are sufficient. Added separate
client setup choices to the token UI and a [client guide](../MANAGEMENT_MCP_CLIENTS.md).
No inbound OAuth or Claude web connector work is required for this release.

Added `alojan_get_release_status` and its scoped read-only API: current publication,
configured-node acknowledgement/expiry and recommended poll interval. It rejects
foreign/wrong-agent releases and does not reserve readiness or activate numbers.
Activation continues to recheck readiness in its existing locked transaction.

Supplemental Mac follow-up:

- Readiness/API/MCP/number suite: **29 passed in 21.22s**.
- Updated real HTTPS browser flow: **1 passed in 3.2s**. Covers both client settings,
  incorrect password without logout/false uncertain result, credential clearing,
  token issuance, secure connection handoff and revocation.
- Web production build, typecheck, Ruff and whitespace checks passed.
- Actual installed **Codex CLI 0.163.0-alpha.10.2** app-server MCP discovery
  connected over loopback HTTPS and listed the **15 permitted tools** for an
  `agents:read`-only synthetic token. Server identity was `alojan-management` and
  `toolsError` was absent. No model turn or user-visible task was created.
- Actual **Claude Code 2.1.87** `mcp get` reported **Connected** over loopback HTTPS
  using a temporary `.mcp.json` and the synthetic environment token. No persistent
  client configuration was changed. The temporary project directory was removed.
- Test TLS used a private local root and a correctly signed leaf with IP/DNS SAN;
  trust was scoped to the child processes. Certificate verification was never
  disabled. An initial self-signed CA-as-leaf fixture was rejected by Codex; the
  corrected root/leaf fixture passed. This is not public-domain TLS acceptance.
- New private logs: `readiness-tests.log`, `browser-client-tests.log`,
  `client-probe-tls.log`, `codex-probe.json`, `claude-probe.log` under the ignored
  review directory. Recorded CLI output redacts the synthetic bearer value.

Linux SSH was rechecked and still timed out. Primary-host full regression,
performance, Cloudflare deployment and real client mutation/activation on the
public endpoint remain open. Local discovery is not an end-to-end live pass.
