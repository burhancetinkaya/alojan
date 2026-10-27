# Scoped response performance UI — 2026-10-26

AGP-06 / M2,M5, P1; ADR 0011; requirements §2/3/12/14–16.

## Delivered behavior

The workspace has a Performans page with agent filtering; call detail has an
on-demand timing section. Both use the authenticated read-only performance API.
The table explains median/P95, individual metric sample/missing counts, excluded
turns, limited windows, last imported observation and insufficient sample size.
It distinguishes server output estimates from handset arrival. No target compliance
or full-sample coverage is inferred merely from having recorded observations.

The existing native gateway emits content-free per-turn latency logs; these were
not previously stored with managed call history. Migration 0019 adds `call_latency`
with immutable observations, forced workspace RLS and composite scope/call/release
foreign key. The private importer maps the existing gateway identity to the same
stable call UUID as initialization. Only known routes on the configured node are
eligible; it never initializes calls or adopts legacy/unscoped data. Numeric/status
fields are allowlisted, identities/content/unknown fields are not persisted in payloads.
No voice runtime, speech callback, inference/model setting or public contract changed.

A dedicated import role has route identity/node reads and timing inserts/counts only;
no caller, transcript, credential, timing-payload read or update/delete privilege.
The collector runs a short-lived container from the pinned management image every
minute, with 0.25 CPU, 128 MiB, read-only filesystem, no capabilities/HTTP listener/
Docker socket. The host-side user oneshot has a 45-second deadline and 256 MiB cap.
Existing gateway logs are read by the host's authorized Docker user. No raw capture
is retained by the importer. Overlapping ten-minute windows replay idempotently.

## Bounds and measurement definition

- At most 10000 input log lines/batch, 4096 characters/timing record and 1000 stored
  observations/call. Durations are integers 0–600000 ms; legacy -1 becomes NULL.
- One observation per call/generation; an advisory import lock serializes overlap.
  This does not lock live call rows or block audio callbacks.
- API examines at most the latest 200 scoped calls and returns aggregates from at
  most 5000 observations. Explicit older-call/truncation flags accompany the counts.
- Completed, normal response turns with zero gateway error are eligible. Failed,
  cancelled, interrupted and recovery/music/reminder cases cannot become fast samples.
  Each metric's missing values are excluded individually, not converted to zero.
- P50 is median; P95 uses nearest-rank ceil(0.95*n). VAD-end-to-audio includes the
  endpoint's silence estimate; it is not measured caller-stop-to-ear latency. The
  pipeline stages overlap and must not be summed. No new real latency benchmark.

## Validation

Primary Linux, pinned dependencies/images:

- Ruff formatting/checks passed for modified Python files. An initial harness lint
  check caught two missing E402 annotations for its existing sys.path bootstrap;
  corrected before browser execution. No skipped/failing tests counted as passed.
- Final Python suite: **51 passed in 32.29s** across call latency, call management,
  number routing, native auth and existing latency-report tests. Initial narrower
  suite had 18 passes in 13.73s; final suite supersedes it.
- Coverage includes malformed/oversized values, duplicate keys, ignored content,
  missing durations, failed/recovery exclusion, exact median/P95, replay deduplication,
  unknown/wrong-node routes, workspace/agent isolation, viewer reads, denied SQL
  privileges, rejected HTTP filters/methods, batch rollback and per-call/read limits.
- `npm run typecheck`, isolated frontend build and production image builds passed.
- **13 HTTPS browser scenarios passed in 22.5s**, zero retries/skips. Synthetic
  performance fixture distinguishes five observations, two excluded turns, two valid
  samples and one missing sample. Checks filtering, empty workspace, per-call lazy
  loading, foreign-scope denial and mobile horizontal bounds. All existing scenarios
  also passed; no network model, voice worker or external delivery ran in the harness.
- Desktop/390px mobile screenshots inspected. `bash -n scripts/import-latency.sh`
  and `git diff --check` passed. Scoped changes reviewed with existing contracts;
  independent work preserved. No commit/push/PR/merge performed.

Private synthetic browser evidence:
`.local/web-validation-d644d77147c04722b364a9eac0f0199b/`.
Build/test/rollout/health receipts: `.local/performance-ui-20261026/`.

## Deployment and owner smoke

Backed up PostgreSQL before additive migration. 0019 applied in **0.058s**;
20 migrations now applied, existing call count preserved. Regranted narrow management
reads and provisioned a fresh non-superuser/non-bypass import role. Credentials are
private ignored files, never public docs or logs.

Deployed only the two HTTP services:

- Management: `sha256:fe5937be5928b08f6857bf44e1ae42572fc882efd10e87dbc066375e59aa06bd`.
- Web: `sha256:8c4e331ee962d7a4a1f0aac0508d48210ecbe7e9c312c8ce8cb9b8ecc015ec45`.

Eight peer containers retained IDs and health; no gateway/agent/ASR/TTS/background
restart. Eleven application containers running, nine configured health checks healthy;
summary/delivery workers do not configure health checks. Admission open, resident
voice preparer active and no audio-preparation maintenance window. Import timer active,
last oneshot Result=success/ExecMainStatus=0.

Explicit bounded historical bootstrap examined 150 gateway log lines and imported
**16** known-route timing observations, with zero malformed/unowned entries. This
is historical diagnostic data, not 16 new test turns. The routine ten-minute import
then succeeded. Replays do not change observations or queue notifications.

Deployed owner browser smoke passed: native login, existing Kübra instructions/model,
release history, existing EMA audio decode, all navigation, existing populated call
transcript/sent result and the populated performance table. A request interceptor
rejected all configuration mutations. Zero browser errors/configuration writes,
new calls, rollback/rebind requests or external sends.

Rollback: disable the import timer and let the current oneshot finish; restore
management `sha256:67ff3c43c3e110d8c00cab773e1dbfb606a11026efda27adb0959b7716607413`
and web `sha256:1b9d6a010a30f25aaa016ac4dc801b41c5f329948dcece8c1742336d11cd5b53`
from backed-up private compose configuration. Recreate only management/web. Retain
the additive timing table for inspection; no voice rollback or deletion required.

## Limits and next step

This is bounded diagnostic collection: downtime beyond the ten-minute overlap,
log rotation/tail caps or per-call ceilings can leave gaps. The API never claims all
turns were captured. A future capacity rollout must qualify throughput/retention.
No new GPU, handset, soak, matched latency or simultaneous-call acceptance; serving
capacity remains one. The second number is still disabled. Next: remaining AGP-06
self-service journey acceptance, then staged MCP/HTTP connection/tool workflows.
