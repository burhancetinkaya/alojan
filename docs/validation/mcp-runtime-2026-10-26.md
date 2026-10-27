# MCP release and call runtime — 2026-10-26

AGP-07 / M4–M5, ADR 0011, requirements US-08 and §9.3/12/14–16.
This completes the candidate read-tool execution slice; builder/OAuth and real
approved-server/carrier/performance acceptance remain open.

## Result

- Migration 0022 binds each immutable version-3 release to its exact MCP consent.
  Preparation/publication and rollback check current consent/review/connection;
  rollback cannot replace revoked historical consent with a newer grant. Shared
  consumers validate exact tool/schema/fixed-parameter snapshots and scope. Existing
  non-MCP versions 1/2 and empty-draft digests remain compatible.
- The existing managed node optionally uses a dedicated MCP SQL role and exact
  operator endpoint allowlist. Independent readiness refresh supplies two-second
  permission freshness, including owner/review/connection/latest-discovery checks.
  Expired preparation entries are reclaimed within a sixteen-entry cache. A revoked
  agent loses admission without withdrawing unrelated healthy releases.
- Actual Agents SDK tools expose only selected aliases and runtime fields. Fixed
  values cannot be overridden. Each invocation uses a fresh MCP session, approved
  public DNS/IP pinning and verified Host/SNI, bounded response/SSE, no redirect,
  proxy, retries or on-call catalog discovery. Only approved structured JSON reaches
  the model; text/resources, invalid outputs and literal credential echoes do not.
- Node/turn/call budgets are 4/2/8; deadline is four seconds with bounded cancellation
  cleanup. Call route, active/answered state, turn and permission freshness fence
  execution. Non-cooperative cancelled work retains capacity until it exits and
  cannot publish a late result into a newer turn.
- A restricted asynchronous journal records immutable scoped invocation identity
  and one terminal outcome. No raw inputs are persisted. Invalid output contents
  are not stored. `started` is unconfirmed; success is not proof of spoken delivery.
- Summary preparation uses only model credentials. A revoked MCP grant does not
  block summaries or independently authorized Telegram enqueueing. No new HTTP
  service, model instance, media callback work or per-turn permission query was added.

## Linux evidence

Tests used disposable PostgreSQL schemas and restricted service roles on the
primary Linux host. Speech WAVs/inference and external HTTP peers were synthetic.
The actual pinned Agents/MCP SDKs and readiness gRPC coordinator were exercised;
there were no external MCP requests or Telegram sends.

- Compatibility suite: **265 passed in 128.25s**, covering discovery/selection/runtime,
  old releases, readiness, number routing, scoped records, summaries, managed startup,
  actions, voice jobs/packs and legacy upgrade.
- Additional combined MCP/Telegram and non-cooperative cancellation regressions:
  **2 passed in 3.60s**, before the final focused run. No action delivery ran.
- Final runtime/selection suite: **71 passed in 56.78s**, including the combined
  action, late cancellation, malformed JSON and repeatable diagnostic SQL regressions.
- After removing a redundant journal index (the scoped unique key already supplies
  it), final schema/combined-action/diagnostic checks: **3 passed in 4.06s**. The
  management image was rebuilt and its restricted-container validation rerun.
- Ruff check and format check passed for all **18 changed Python files**. Tracked
  and new-file whitespace checks were clean. The graph was refreshed without a
  persisted artifact: 6464 nodes / 22403 edges.
- Real restricted management-container HTTP validation passed: registration, scoped
  drafts, qualification/number guards, MCP queue and session revocation. Its temporary
  container/roles/schema were cleaned up by the validator.
- The independent frozen voice-preparer environment imported its worker successfully.
  The separately built frozen action-worker image imported MCP/summary modules with
  networking disabled. Management and worker builds used one CPU/768 MiB limits.

Suites overlap; do not add their counts. Initial test harness issues (missing pinned
HTTP overlay/generated import path and mismatched fixture APIs) were corrected; they
were not counted as passes. Review/testing caught automatic SDK post-call catalog
fetching, unrelated-release readiness invalidation, column-level journal forgery and
uncancelled late-work capacity retention. These have regression coverage. Deep JSON
argument decoding is explicitly fenced before schema validation.

## Deployment boundary

The candidate management image is
`sha256:09f0229f72db240826e115aa102f408edf1e742af713fd7bdeeb94691744a42f`
(`alojan-management:mcp-runtime-20261026`). The final worker candidate is
`sha256:ba5e1b215b0c035a323c7a641e8d3082d7ed2f402665a89abe6ee6598ea85e88`
(`alojan-action-worker:mcp-runtime-20261026`).
The earlier management `95724abe3da1…` and worker `e16053a14695…` images were
intermediate candidates, superseded by the identities above. No production schema
migration or serving restart occurred. The serving management
image remains `fe5937be5928…`, web `0028bb053007…`; live schema remains through 0019.
Migrations 0020–0022, MCP roles/endpoints and candidate images are not activated.
Existing Kübra/EMA/Telegram, routing/capacity and disabled second-number setup remain
unchanged. Maintained design documents are mirrored into the private Linux review
folder to preserve independent root-document edits; source copies were selective.

## Limits / next work

Next: MCP builder connection/selection/parameter/consent UI and its end-to-end journey;
OAuth is still pending. Real approved-server TLS/implementation tests need a separately
approved endpoint. HTTP post-call actions (AGP-08) and public-launch gates remain open.

Drift detection compares the latest explicitly recorded discovery, not unannounced
remote implementation changes. Read-only capability review remains an operator trust
decision. Revocation is bounded by two-second local freshness; already-sent requests
cannot be retracted. No new GPU, real-model, carrier, multi-call load or latency
acceptance is claimed. Browser journeys were not repeated because no UI changed.
