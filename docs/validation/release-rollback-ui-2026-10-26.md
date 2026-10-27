# Release history and rollback UI — 2026-10-26

AGP-06 / M2,M5, P1; ADR 0011; requirements §1/2/11.2/12/14–16.
Owner authorized continuing the approved Next.js/shadcn workspace and Linux rollout.

## Result and semantics

The agent editor opens the existing latest-100 release list on demand. Each entry
shows revision, current-publication marker, optional immutable ID/digest and rollback
lineage. Workspace readers can inspect history; only owners see rollback selection.
Selection opens an explicit review in the same dialog before any mutation. Unsaved
drafts block confirmation. Current-publication and number routing are described
separately so an old release is not mistaken for the currently served phone agent.

The existing rollback API copies the selected immutable manifest into a new release,
checks publication version, model qualification, prepared assets, connection and
current action grant. It does not replace the editable draft, rebind a number or
change pinned calls. Revoked grants cannot be resurrected. Success provides a link
to the existing number assignment workflow. No new API, database migration, runtime
service, dependency or voice-path operation was introduced.

A synchronous submission guard prevents duplicate clicks. Failed/uncertain responses
clear selection and disable confirmation until the user refreshes history and selects
again. The UI never retries a publication automatically with a newer version. A lost
response may mean publication succeeded; the refreshed history shows that result.

## Linux validation

- `ruff format/check tools/validate-web.py`: passed.
- `pytest tests/test_agent_releases.py tests/test_number_routing.py tests/test_action_grants.py -q --tb=short`:
  **44 passed in 25.41s**, no skips. Covers snapshots, scope/role restrictions,
  concurrent publication, model revocation, assets, routing and grant revocation.
- `npm run typecheck` and production build: passed using pinned Node image.
- `tools/validate-web.py`: **12 HTTPS scenarios passed in 21.3s**, no retries/skips.
  Uses an isolated schema, least-privilege management role, synthetic accounts and
  existing pinned management image. Added browser checks prove dirty-input blocking,
  cancellation without writes, a real concurrent publication causing stale-version
  rejection, accepted rollback with a deliberately discarded response, explicit
  recovery, normal success, unchanged draft and unchanged number binding.
- Final isolated DB assertions: five releases in the call workspace, original number
  binding unchanged, current draft instructions unchanged, one unknown action job
  with one fake transport attempt and one unconsumed retry request. No delivery worker
  runs; no external send occurs. Schema/role/containers cleaned up.
- Desktop and 390px mobile screenshots inspected. Dialog stays within viewport;
  content has bounded scrolling and no horizontal overflow.
- Full changed source/fixture integration reviewed; `git diff --check`: passed.
  Existing unrelated dirty/untracked platform work preserved; no push/PR/merge.

Evidence: private `.local/web-validation-a17cc10d5b0e44ee80e54bea2cf09f13/`;
rollout/build/test receipts `.local/release-rollback-20261026/`. Screenshots contain
synthetic data only. These are application/browser checks, not real inference or
carrier performance measurements.

## Deployment and owner check

Built and deployed only `alojan-web:release-rollback-20261026`:
`sha256:1b9d6a010a30f25aaa016ac4dc801b41c5f329948dcece8c1742336d11cd5b53`.
Prior web image remains available:
`sha256:716a805515187a24973ed6e32154cd933a19edbfa96cccd4c04a5ecada272e1e`.
The private compose environment was backed up before replacement. Reverting its
`ALOJAN_WEB_IMAGE` and recreating only `web` restores the prior UI; no DB rollback.

Management image remains
`sha256:67ff3c43c3e110d8c00cab773e1dbfb606a11026efda27adb0959b7716607413`.
Nine `alojan-local` peers retained container identities; no management, voice or
background restart. All eleven application containers running; nine configured
health checks healthy, two action workers do not configure health checks. Admission
open, resident audio preparer active, no preparation window in progress. Web remains
bounded at 0.5 CPU / 512 MiB behind the existing private TLS service.

Owner smoke passed on the deployed preview with an interceptor rejecting every
configuration mutation. It opened and closed Kübra's release history, read the
existing long instructions/model, decoded existing EMA audio, checked navigation,
read an existing populated transcript and sent-delivery result, then logged out.
No browser errors, configuration writes, rollback requests or external sends.
Independent Linux root documentation preserved; maintained notes mirrored into
`.local/agent-platform-design-review/implementation/` with backup.

## Limits and next work

No production release was rolled back or rebound. No new handset, GPU, latency,
soak, simultaneous-call or carrier acceptance; serving capacity remains one. History
is deliberately bounded by the existing API to 100 releases. Source metadata is
shown; a full historical manifest diff is not part of this slice. Public recovery,
latency views, remaining AGP-06 workflow acceptance and staged MCP/HTTP builders
remain open. Next planned slice: scoped P1 latency views.
