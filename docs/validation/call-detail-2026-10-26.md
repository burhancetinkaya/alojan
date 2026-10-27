# Scoped call history and detail — 2026-10-26

AGP-06 / M2,M5, ADR 0011, requirements §1/2(P1 dashboard)/12/14–16.
Ponytail full; continues the approved Next.js/shadcn flat design. No new package,
service, model, protocol, inference configuration or voice callback change.

## Delivered behavior

`GET /v1/workspaces/{scope}/calls` returns at most 50 records and a next UUID
cursor. Optional `agent` filtering and an exclusive `(created_at,call_id)` cursor
use two new indexes on immutable route snapshots. Foreign/missing cursors,
unknown/duplicate filters and invalid IDs are rejected; offset/count scans and
unbounded response sizes are avoided. Each history entry uses its pinned release's
agent/owner identity, so changing a draft cannot rewrite history.

`GET /v1/workspaces/{scope}/calls/{call}` returns timing/outcome, caller metadata
with provenance, final summary, latest note/confirmation and delivery outcomes.
One SQL statement observes a consistent detail snapshot without locking call,
note or delivery rows. Pending/failed/missing summaries and absent notes remain
explicit. Sent, rejected and uncertain notifications remain distinct; reading or
refreshing the page never retries a notification. Payloads, bot targets/tokens,
lease claims, raw SIP IDs and instruction text are not exposed by these routes.

Workspace membership and existing PostgreSQL RLS govern every read. Only narrow
SELECT column grants were added; management cannot write call/note/summary state
or read raw SIP/summary lease columns. Unscoped legacy calls remain invisible;
no ownership is inferred or assigned. Read responses use `Cache-Control: no-store`.

The old notifications-only Aramalar page is replaced by an agent-filtered call
list and direct-link detail with back/refresh controls. Caller/model text renders
as escaped plain text, including multiline notes. Existing UI request cancellation,
workspace-keyed components, sessions and styling are preserved. No recordings or
transcript export is introduced by this slice.

## Linux verification

- Ruff check/format, TypeScript and production builds passed.
- **47 tests passed in 45.85s**, no skips: new call API access/legacy isolation,
  read-only grants, input rejection, immutable identity/latest note, pending/failed/
  unanswered states, stable pagination including equal timestamps and concurrent
  insertion, and delivery observation without replay; existing scoped-record and
  delivery-management regression suites also passed. Earlier run: 44/52.67s before
  the three delivery-result cases were added.
- **10 HTTPS browser scenarios passed in 16.3s**, no retries/skips. Includes scoped
  detail navigation/reload, summary/note/no-action display, HTML injection treated
  as text, cross-workspace denial and 390px layout. Existing nine builder/security
  scenarios also passed. Synthetic fixtures create two publications, one routing
  binding and zero delivery jobs in an isolated schema that is dropped afterward.
  No network model, voice process or action worker is started by that harness.
- Desktop/mobile visual review completed. The first mobile screenshot captured an
  in-progress sidebar transition; the test now awaits its completed offscreen
  position before capturing. Earlier browser run also passed 10/15.2s, but the
  final visual evidence is from the corrected capture.
- Real owner HTTPS read-only smoke passed: login, existing long instructions/model,
  already-prepared EMA playback, all navigation, existing call detail, existing
  sent notification and logout; zero browser errors or configuration mutations.
  No personal content/screenshots were retained in maintained evidence.

## Deployment

A private database backup preceded additive migration `0017_call_history.sql`.
History was under 1 MiB with no active calls at preflight; index creation has a
200ms lock timeout and 3s statement timeout. A larger installation requires an
online index rollout. Migration completed in **0.053s**; 18 applied migrations,
existing history unchanged, restricted management grants re-applied.

Only management/web containers were recreated; **eight local peer container IDs
and health were preserved**. The separate audio preparer and voice admission gates
were not changed. This deployment does not prove matched latency/load performance.
Rollback configuration, database backup and sanitized receipts are private under
`.local/call-detail-20261026`. The indexes/SELECT grants are backward compatible
with the previous application images; an application rollback need not remove them.

- Management: `sha256:0c591c9f278f3d9c4e1c8eb94b2119fab1548d4ded62b0754069288bac2b384a`.
- Web: `sha256:d4db2e0e3d65342d3fae52bed71115aa9decc7be7ac18acc53512472842fe10b`.
- Final synthetic browser evidence: `.local/web-validation-6f0e6a9fe6b845bfab5f3d1f10c7ff34`.

Initial private migration command lacked PYTHONPATH and stopped before accessing
the database; corrected invocation passed. An owner-smoke preparation command
failed shell quoting before SSH execution; a saved script replaced it and passed.
Neither failed attempt is counted as validation or a live change.

## Remaining acceptance

Call transcript/latency views, owner-reviewed delivery retry UI, rollback UI and
complete AGP-06 workflow acceptance remain follow-ups. MCP/typed HTTP builders and
public recovery/launch remain staged separately. No new handset call, external
Telegram send, concurrency, GPU quality or matched performance/soak test was run.
The owner's prior real carrier acceptance remains separate and unchanged.
