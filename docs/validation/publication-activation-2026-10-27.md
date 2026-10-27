# Publication activation and restart isolation — 2026-10-27

AGP-03/06/09, M4–M5, ADR 0011, US-01/08. Fixes the two owner-approved P1 findings:
new publications had no runtime activation consumer, and one unavailable explicit
release prevented the entire shared agent process from restarting.

## Behavior and boundaries

Migration `0026_publication_node.sql` adds a nullable node assignment to the current
publication. Management supplies it from trusted `ALOJAN_VOICE_NODE_ID`, never the
request body. Publication/assignment commit together; rollback uses the same path.
Existing rows retain null assignment and their explicit legacy deployment targets.

The private readiness consumer discovers current node publications and enabled
verified number bindings every two seconds after each bounded pass. Bound releases
have priority. Explicit targets remain supported; an empty list is now valid for a
node awaiting publication. Discovery does not bind numbers, generate audio, invoke
MCP tools or call a model. Normal asset/configuration/credential/grant checks remain.
Cold activation has a separate lock from warm readiness renewal. Unavailable releases
remain unready and retry independently; common DB/role/speech checks remain mandatory.
Process health never establishes a particular release's readiness.

Superseded unbound releases retire after active call leases finish. Retirement locks
the readiness receipt and rechecks bindings; local routes are rechecked after DB IO.
Unused provider clients are closed. Existing 16-entry/16 MiB cache ceilings remain;
capacity pressure cannot evict pinned calls. Historical unbound releases can be
republished through rollback for fresh activation. Explicit legacy targets remain
pinned until removed from private deployment configuration.

The readiness role gains node-filtered publication/binding discovery and limited
number metadata reads, without phone digits, user secrets or routing/publication writes.
Management retains workspace isolation and cannot forge readiness receipts.

## Verification

Primary Linux: disposable PostgreSQL schemas, real management/agent code and gRPC
processes, synthetic speech and unused test credentials; no external model/tool calls.

- **147 passed in 125.08s** across publication activation, managed startup, readiness,
  number routing, releases, provider connections, MCP runtime, native auth and voice jobs.
- After the final post-IO active-route retirement guard, the four focused activation
  regressions passed again: **4 passed in 16.82s**. Counts are not additive.
- Coverage includes restricted HTTP publication/binding without restart, old/new call
  snapshots, healthy restart with a revoked unbound agent, empty-node discovery,
  node isolation, warm renewal during cold activation exceeding two seconds, and
  retirement after call release. Ruff and full working-tree whitespace checks passed.
- Earlier harness failures used unsupported synthetic call IDs and omitted required
  RPC deadlines. Corrected test inputs are not evidence of product failure or a pass.

## Linux activation

Source-only derivatives preserve installed dependencies and resource budgets:

| Service | Active immutable image |
|---|---|
| Agent | `sha256:fe708321577d5c60001ce568a9f0481799596112171b96f047882aab5d9f10f6` |
| Management API | `sha256:9a1ea32d192259df2937b1f9b5bf8cf6cf701c9e68180369b0878d69e86be176` |

Stopped the idle preparer under host/database locks, drained native admission, saved
and verified a consistent PostgreSQL backup, applied migration 0026 idempotently and
refreshed management/readiness grants. Replaced only agent/API containers. Business
record/routing fingerprints were preserved. One bound number regained readiness before
admission reopened; preparer resumed. Gateway, ASR, TTS, PostgreSQL, legacy API, web
and all three background worker identities/start times remained unchanged.

Postdeployment agent/API/gateway/ASR/TTS were healthy with zero restarts and no inspected
activation/discovery/startup error markers; management readiness returned HTTP 200.
No model inference, audio generation, remote tool invocation or notification initiated.
The first deploy invocation lacked the generated-protobuf import path and stopped
before mutation; the corrected invocation completed successfully. Private evidence,
backup and old configurations are in `.local/activation-fix-20261027/` on Linux.
Rollback restores compatible images/configuration, never an old DB over new records.

No new carrier handset call, GPU performance comparison, load/soak or full operational
rollback qualification. Those gates and deferred summary quality remain unchanged.
These fixes do not introduce automatic selection between agents.
