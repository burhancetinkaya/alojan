# Qualified platform publication — 2026-10-27

M5-03 / AGP-03/06 / MCP-06; requirements US-02/05/06 and §11–16;
ADR 0003, the Docker runtime amendment and ADR 0011–0014. The owner ended
interruption experiments and authorized deployment verification, publication to
`main`, and removal of all private and example MCP endpoint URLs from Git.

## Release selection and privacy

Consolidated the already qualified platform work with the existing remote-main
Docker/runtime work. Preserved the standard large-v3 manifest and legacy support
modules. Resolved overlapping changes in favor of the verified profile-aware
runtime; removed duplicate definitions introduced by the merge. The rejected
text-corroboration/recovery trial and its executable harness were archived under
ignored `.local/`, restoring the previously serving implementation. Historical
negative results remain documented; no rejected acoustic experiment was promoted.

Removed deployed MCP addresses from maintained documentation and the live-test
fallback. Live Hindsight tests now require a privately supplied endpoint in
addition to explicit opt-in. OAuth/example configuration contains empty endpoint
fields, client setup uses environment variables, and the discovery SQL requires
an operator-supplied variable. Synthetic tests construct reserved destinations;
no copyable sample MCP server URL is provided. Official documentation and package
registry links remain references, not operational endpoint defaults.

Private client configuration is ignored. Ingress now requires
`ALOJAN_MCP_NGINX_CONFIG`: the existing host routing was copied into a private
operator file and the container was recreated against that copy. Repository
synchronization can no longer overwrite the live hostname. Private environment,
connection credentials, MCP/OAuth tokens, phone bindings and agent data were not
published or rewritten. Source-only Docker contexts exclude local environments,
client configuration, captures, credentials and frontend caches.

The publication audit checks private endpoint/email patterns, copyable MCP endpoint
examples, private-key/provider-token formats and private file paths. The complete
source tree and each new commit are scanned before pushing; findings must be empty.
This is a scoped publication audit, not a claim of historical credential erasure or
a formal security certification. Existing remote history is not rewritten.

## Linux deployment evidence

- Source snapshots were saved before synchronization; remote differences were
  inspected and earlier development copies preserved privately.
- Rebuilt gateway SHA-256 equals the serving binary exactly:
  `8b82ea19060bc481138811af7ca79203fe6393a79025ccfa4d2dc5e65ed33e50`.
  The gateway, agent, ASR and TTS did not require recreation.
- Serving Python source hashes match the publication tree for agent/shared contracts,
  management API, MCP transport, ASR, TTS and the updated background-worker image.
- Published frontend image:
  `sha256:ae8683613fec4383622edff14d14734bb7654f944f97f4360f7502729e94975d`.
- Updated summary, delivery and discovery image:
  `sha256:84f3e5ee20a9d3fdd40ccb2609ab910e20b37f513eed7e3fe785e3f894879a2a`.
  Its source-only update preserves the installed dependency image. No active or
  initializing calls, sending/leased actions, processing summaries or running
  discovery jobs were present before recreation. Previous images/configurations
  remain available for rollback.
- Public login with a browser user agent: HTTP 200. Unauthenticated public MCP:
  HTTP 401. Management and MCP health: HTTP 200. All 14 serving containers remain
  running; all configured healthchecks are healthy and restart counts are zero.
  Three background workers have no Docker healthcheck; process/source checks do
  not assert a newly completed external delivery.
- The initial default Python-user-agent public probe received an edge HTTP 403;
  browser-user-agent and direct ingress probes passed. No Cloudflare policy was
  weakened and no new Codex/Claude authenticated mutation was attempted.

## Validation

- Linux native build and **11/11 CTest** passed (3.93 s); pinned clang-format passed.
- Full top-level Python suite: **1,189 passed, 68 skipped, two failures** (464.98 s).
  Both failures were obsolete test setup assumptions: RPC descriptor ordering and
  invoking today's authoring API against migration-v8 tables. Replaced ordinal
  RPC lookup with named methods; seeded historical rows directly for the actual
  migration test, retaining its ownership/backfill/no-delivery assertions.
- Targeted rechecks: **5 contract tests passed** (0.03 s) and **15 scoped record/
  migration tests passed** (12.93 s). No unresolved failure remains from that run;
  the whole suite was not repeated after these test-only corrections.
- The first collection attempt lacked the documented optional test dependency;
  reran with pinned `--with httpx==0.28.1`. Live/provider-dependent tests remain
  explicit skips, not successful integration evidence.
- Frontend TypeScript check and production/test builds passed. **48 HTTPS browser
  scenarios passed** (1.2 min) against isolated schemas and synthetic transports;
  the harness verified zero production writes and zero external sends.
- Ruff lint/format and Git whitespace checks passed. Knowledge graph refreshed.

Private evidence, configuration backups and deployment commands are retained in
`.local/main-release-20261027/` on the authorized Linux host. Browser evidence is
in `.local/web-validation-8ba00cab320344619cd0bd6c8232600b/`.

No new carrier call, room-noise qualification, concurrency/load test, paid model
request or external notification was needed for this publication. Existing acoustic
limitations and separate capacity acceptance remain unchanged.
