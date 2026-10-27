# Platform migration preflight and Telegram adapter acceptance

Date: 2026-10-25. Ponytail full; ADR 0003/0011, AGP-05/09, PERF-02,
M1/M4/M5, requirements §9–12 and US-07/08. This is partial acceptance,
not authorization to bypass the remaining voice/performance gates.

## Observed deployment

Read-only inspection of the primary Linux host found seven healthy Alojan
containers: gateway, agent, ASR, EMA TTS, legacy Telegram, legacy health API and
PostgreSQL. The voice image family is `lifecycle-20261024`, sourced from the
preserved `.local/call-lifecycle-release` snapshot. Despite the native development
profile, the current resident carrier deployment is containerized. Do not replace
it using assumptions about a native resident process.

The live schema has exactly `0001_initial.sql`, `0002_agent_summary.sql` and
`0003_telegram_outbox.sql`; all three checksums match the current checkout.
At inspection there were 29 ended calls, 29 completed summaries, eight delivered
legacy notifications and no active call or pending notification. These are point-in-time
counts, not an admission fence. No private record contents were copied.

Existing bot, target, provider and database files have mode 0600. The managed
deployment files `.local/management.env`, `provider.key`, `worker.env`, `delivery.env`
and `managed-node.json` do not yet exist. There are no live platform users,
memberships, profiles or releases because their migrations have not been applied.
The requested ownership transfer is therefore still pending. The unavailable
second DID/Telegram mapping remains absent and disabled.

## One explicitly authorized external message

The owner explicitly approved one fixed synthetic message to the existing bot's
target ending in 2287. At 18:43:58 UTC, the built
`alojan-action-worker:action-retry-validation` image sent that exact message through
the production `Telegram` adapter. The one-shot container had a read-only root,
all capabilities dropped, no-new-privileges, 0.5 CPU, 512 MiB and 64 PIDs. It mounted
only the existing bot/target files read-only and a private evidence directory;
it had no database credentials or access to historical message payloads.

Result: `sent`, exact numeric destination validated, positive Telegram receipt
recorded. The private exclusive-create attempt journal is
`.local/telegram-acceptance-20261025/authorized-single-attempt.json`; repeat invocation
refuses another send. No automatic retry occurred. No token or full target is
recorded here. This establishes real DNS/TLS/SNI, fixed-origin adapter networking
from the built container and Telegram acceptance of this destination. It does not
prove that a person read the message or that the complete scoped summary/grant/queue
path has passed a real external delivery. Those boundaries have synthetic integration
coverage; the real scoped end-to-end canary remains pending.

## Additive migration rehearsal

`tests/test_legacy_platform_upgrade.py` recreates the exact three-migration baseline
in disposable Linux PostgreSQL schemas with synthetic data only. Pending, delivered
and failed legacy notifications, summary states, calls, utterances, confirmed notes,
events and action items are checked column-for-column after upgrade and repeat upgrade.
No user, workspace, profile, number binding, grant, connection, finalization, scoped
action or retry is implicitly created. Historical jobs retain unknown ownership;
the original legacy queue update statements remain usable in that isolated schema.

A deliberate failure after all platform migrations rolls back the entire upgrade,
retaining the original migration ledger and data. A held legacy-table lock causes
the operator-supplied 200 ms lock budget to abort and roll back; applying again after
the lock is released succeeds. The test DSN also sets a 10-second statement budget.
The migration helper does not supply these budgets by default: the deployment DSN
must explicitly set appropriate lock/statement limits while preserving its search path.
Initial focused result: **3 passed in 0.84s**. This is not a production-size lock/DDL
duration benchmark, backup restoration test or production migration.

Expanded migration/profile/scoped-records/delivery-management regression:
**66 passed in 56.36s**, no failures or skips. Initial collection without the optional
HTTP test dependencies failed (`httpx` missing); the successful run used the documented
`--with httpx==0.28.1 --with starlette==1.9.0` overlays. Ruff check and format check pass;
repository diff whitespace checks pass. The graph was refreshed without persisted cache.

Validated worker image identity:
`sha256:4577bece6bf7207fa3c7d4adb09fcfaee153a2afb79f2f771b865fc9d7ad6063`.

## Isolated performance observations

Re-ran the existing benchmark fixtures against disposable Linux schemas, without
touching resident voice processes or invoking real inference:

| Measurement | Samples | P50 | P95 | Maximum |
|---|---:|---:|---:|---:|
| Scoped DB admission, fresh connection per call, after five warmups | 50 | 21.54 ms | 39.68 ms | 51.15 ms |
| Cold application preload, warm OS cache, synthetic PCM | 30 | 1.1114 ms | 1.1293 ms | 1.1526 ms |
| Warm in-memory release pin/unpin | 10000 | 0.0028 ms | 0.0028 ms | 0.0120 ms |

Both benchmark tests passed in 2.16s. Accounted prepared payload: 75,680 bytes.
No matched live control, SIP/RTP timing, confidence bound, GPU/API inference, background
load or soak is included. PERF-01–06 acceptance stays open. The read-only GPU snapshot
was RTX 4080, 4082/16376 MiB used, 0% utilization; it is not a maintenance reservation.

## Required cutover order

1. Preserve current images, Compose/configuration, source snapshot and an independently
   restorable database backup. Complete matched voice/resource acceptance first;
   use an admission-fenced window for GPU preparation, not a one-time idle check.
2. Validate the production migration ledger again, set bounded migration connection
   options, and apply compatible additive schema using operator credentials. Provision
   distinct least-privilege runtime roles and external key storage. Keep HTTP management
   and background jobs in their separate containers with resource limits.
3. Provision the intended owner's authenticated workspace and migrate the existing
   agent into it with explicit provenance. Preserve historical rows and UUIDs;
   never infer historical ownership from a display name. Import credentials as encrypted
   scoped references; do not display tokens or create a standing grant from this
   one-message test approval. Prepare the unchanged model/preset, instructions and EMA
   assets; verify DID ownership before any routing activation. Keep the second line disabled.
4. Before the first managed call, fence new admission, drain active calls and inspect
   pending legacy summaries/notifications. Resolve remaining legacy work explicitly;
   do not replay old results. Stop the old global summary and Telegram consumers.
   Inspection of the preserved deployed `Store.pending()` confirmed that it selects
   all pending jobs without a workspace filter. Its database role bypasses RLS, so
   **it must never coexist with managed summary jobs**, even after additive migration.
5. Start qualified managed voice/readiness and independent scoped workers; verify
   exact release/assets, credentials, grants, roles, health and admission while still
   fenced. Activate only the existing verified number, then perform the limited carrier
   and scoped end-to-end notification canary before widening admission.
6. Rollback fences candidate admission and stops scoped consumption before restoring
   the old route/processes. Do not start the unmodified old summary loop against a DB
   containing pending managed jobs: first establish a tested legacy-only consumer boundary.
   Preserve unknown delivery states, immutable payloads, grants, notes and retry journals;
   rollback must not reset or replay external actions. A database-wide restore is not an
   automatic rollback once new calls/writes exist.

No production schema change, restart, ownership transfer, route activation, model
synthesis, historical replay, push or merge was performed in this preflight.
