# Call lifecycle actions candidate — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.4/11/12/14–16.
Ponytail full: reuse private lifecycle metadata, immutable release/grant intent,
existing leased summary queue, scoped finalization and independent action worker.

## Behavior and review

Both Telegram/HTTP support `no_answer` and `interrupted`. Release v7/review v6 pin
these conditions; old default/summary/transcript-only schemas and digests remain valid.
The editor and exact owner review display eligibility. No-answer disables transcript
sharing and vice versa, with the same server validation: no pre-answer spoken disclosure.

Scoped end/cancellation/reconciliation conditionally inserts a job only if the pinned
v7 release explicitly selects no-answer. Unrouted tombstones have no guessed owner;
default agents create no new job. Duplicate end/cancellation never replays history.
The worker skips model preparation/inference and utterance/note/tool-result reads for
unanswered calls. Event v4 and terminal `not_requested` preserve null summary/note/
answer/duration and unavailable declared outputs. Fabricated summary/extraction input
is rejected. Existing mapping missing-value policy still controls each selected field.

Interrupted means answered/ended and exact native `disconnected` or `failed`. Completed
assistant hangup does not match; ordinary caller BYE does, even after a farewell. The UI
explains that this is not semantic unfinished-task detection. Reconciled missing answer
is observed durable state, not proof that no handset ever answered. No caller/model text
or free-form reason substring controls permissions or eligibility.

Migration 0025 adds terminal states without backfill or historical enqueue. Routing
adds scoped summary-job INSERT, and records adds scoped immutable-release SELECT.
Neither gains delivery/finalization write privileges. Existing route ownership triggers,
RLS, atomic enqueue, lease/token fencing, exact grants and revocation remain. No native,
protobuf, dependency or daemon change; no media callback work. The no-answer SQL guard
explicitly targets release v7 and must be updated with future compatible release versions.

Reviewed all affected callers, contracts, SQL roles, fixtures, frontend consumers and
full task delta. Graph-first discovery supplemented by direct reads where call edges
were incomplete. Existing native outcome mapping was inspected but not changed.

## Primary Linux evidence

- Broad compatibility: **300 passed in 223.43s**, covering lifecycle, conditions,
  transcript, outputs, HTTP/grants/delivery/retry, summaries/scoped records, publication,
  runtime/prepared releases, MCP, call management, private lifecycle RPC, routing and auth.
- Expanded focused suite: **12 passed in 12.49s** (overlaps broad coverage). Includes
  metadata truth table, exact release/review downgrade rejection, changed draft independence,
  no-model no-answer processing and null delivery, normal/failed/caller hangup distinction,
  default no-work behavior, fabricated summary rejection, duplicate fencing, unrouted
  tombstones, aged-record reconciliation, read-only SQL and migration readiness.
- Two focused cases exercise real loopback gRPC through the service with scoped DB roles
  for setup cancellation and end without an answer witness. Readiness/audio/model peers
  are explicitly synthetic; this is not real SIP/RTP or GPU/carrier acceptance.
- Real HTTPS browser harness: **35 passed in 58.2s** plus database invariants. Real
  restricted-API journeys and intercepted UI contracts; new journey covers persistence,
  exact grants, changed eligibility, transcript mutual exclusion and mobile layout.
  Evidence: `.local/web-validation-8f71a7a5df204498a7bfef30bc14574d` on Linux.
  Harness reports zero production writes and zero external sends.
- Restricted management container validation passed. Linux TypeScript/Next builds and
  separate management, summary/action worker and production web builds passed. Frozen
  summary/delivery imports passed with network disabled.
- Final Ruff check/format: 13 Python files. Pinned Prettier 3.8.3 and TypeScript cover
  six affected UI/type/test files. Full task delta, SQL examples and untracked sources
  reviewed. All 21 source hashes match Mac/Linux; task added-line and full Git diff
  whitespace checks passed. Graph refreshed without persistence: 6,910 nodes / 24,835 edges.

Diagnostic failures were test/setup issues, not silently counted as passes: an obsolete
fixture import triggered F401; two expectations used `notify` instead of the fixture's
actual `crm` alias; two added RPC cases used an invalid managed call-ID prefix. Corrected
fixtures passed without weakening production validation. A test frontend build initially
used the wrong environment variable; it was rebuilt with ALOJAN_MANAGEMENT_URL pointing
to the isolated backend before the successful browser run.

## Candidate identities and activation

| Application | Image |
| --- | --- |
| Management | `sha256:33841d4eb748b989cbbfa93d29bd95cd3f0303394e2290d4ed1ed4802b0239f9` |
| Summary/action worker | `sha256:3f8c80214d0a9502825efefa17b65a67469e14f837f6e66a900cb8238e0a06df` |
| Web | `sha256:8badb0606b684b39bf36b69a7007486b1250ff0ff3e8773935f8941ae8635de6` |

Activate the additive schema chain and re-provision routing/records roles, then compatible
v7/v6 readers across management, voice/readiness/preparer, summary/delivery and web.
Keep the new schema states on rollback and preserve queued intent. No automatic live
agent republication/rebinding, data backfill or historical replay. Sources sync to the
authorized Linux checkout; maintained docs stage separately under
`.local/agent-platform-design-review/implementation/`.

This slice performed no serving migration/restart, ingress/env replacement, real model,
provider/MCP/webhook/Telegram request, synthesis or SIP/RTP call. Existing Kübra/EMA and
the disabled second mapping were not changed. No commit, push, PR or merge.

## Remaining acceptance

Real extraction/MCP/provider/receiver interoperability, coordinated activation and
measured voice/management-load/rollback acceptance remain open. These tests do not
establish concurrent-call capacity or P50/P95 non-regression. Public-launch/carrier
and known prior model-quality/latency limits remain separately tracked.
