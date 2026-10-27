# Typed HTTP post-call candidate — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.3/12/14–16.
Ponytail full: reuse native authentication, scoped database, exact owner grants,
immutable release/event jobs, bounded delivery worker, HTTP dependency and Next/shadcn.
No new service, broker, template interpreter, model or per-agent process.

## Result and review

Implemented immutable workspace HTTPS destinations with optional encrypted bearer
credentials, owner-only creation/revocation, typed flat JSON/query source or scalar
literal mappings, null/omit/fail semantics and synthetic request previews. The owner
reviews exact method, destination, data mapping, headers and auth mode before consent.
Saving/reviewing sends nothing. Historical Telegram schema/digests remain compatible;
HTTP/mixed reviews use schema 2. Existing releases pin the original action intent.

The existing independent worker resolves and pins public DNS, keeps original TLS
identity, rejects proxies/redirects and bounds request/time/resource use. It rechecks
the exact grant, current owner/workspace/connection and intent before sending. Accepted
2xx status headers record HTTP acceptance, not downstream business completion. Response
bodies are ignored. Proven unsent connection failures may retry; uncertainty never
replays automatically. Explicit reviewed retries keep the same payload, destination
and job UUID idempotency key. Independent actions cannot replay successful siblings.

Migration 0024 adds immutable/RLS HTTP connections, adapter-specific generated scoped
foreign keys, HTTP acceptance receipts and bounded retry storage. Management cannot
read stored HTTP secrets; only the actions role can. No default permission/job/send
is seeded. The PostgreSQL example creates only a disabled synthetic target and rolls
back; it has no lasting effect. Scripts are PostgreSQL 17, not SQL Server T-SQL.

Reviewed affected source/callers/tests, role grants, migration state transitions,
legacy digest compatibility, browser forms and full change delta including new files.
Two boundary regressions were found and fixed during review: target metadata or URL
encoding can exceed the draft's review bounds, which now returns a clear 400; and
JSON-escaped near-limit requests can require four times their outgoing size inside
retry review storage. The latter was reproduced as a database CheckViolation before
raising only the bounded review cap to 320 KiB. Outgoing JSON remains capped at 64 KiB
and encoded query at 4 KiB. A real persisted unknown-job retry proves exact request
and key reuse for a near-limit escaped body.

## Primary Linux evidence

- Compatibility suite: **187 passed in 163.58s**, covering HTTP actions, grants,
  delivery/retries, drafts, releases, prepared releases, summaries and MCP/OAuth
  consumers. Real disposable PostgreSQL schemas and restricted roles; synthetic
  external transports. This preceded the final bounds-only review corrections.
- Expanded HTTP suite: **16 passed in 7.00s**. Added mixed HTTP/Telegram isolation,
  privilege checks, generated target/immutable guards, private/mixed IPv4/IPv6 DNS
  rejection and mapping limits.
- Subsequent bounds/grant suite: **26 passed in 16.61s**. Validates oversized expanded
  target/query reviews fail with 400 rather than a server exception. Suites overlap;
  their counts are not additive.
- Final HTTP/Telegram delivery, retry and grant suite: **95 passed in 106.22s**.
  Includes near-limit escaped-request persistence/retry and the rollback-only SQL
  example. This is the final 0024 migration and current source; the HTTP subset
  contains 20 tests. Counts overlap earlier suites.
- Final HTTPS browser harness against the final management candidate: **31 passed
  in 55.4s** (20 real restricted-API journeys and 11 intercepted MCP/OAuth UI
  contracts). HTTP creation/mapping/preview/grant/revoke/mobile passed without sends.
  Evidence: `.local/web-validation-13b355632b764e7eb539b5320619e927` on Linux.
  Earlier browser passes were 31 in 50.6s and 53.1s; not additional scenarios.
- Pinned Linux Node 22.23.1 TypeScript and Next production build passed. Separate
  management, action-worker and production web images built. Restricted management
  container validation passed with actual least-privilege database roles; frozen
  action/summary/HTTP worker imports passed with network disabled. Independent frozen
  voice-preparer import also passed, without adding optional HTTP dependencies to it.
- Final Ruff check/format covers 21 affected Python files. Prettier 3.8.3 covers seven
  affected UI/test files. Whitespace checks include untracked files. Source hashes
  match Mac/Linux for all 31 manifest paths; maintained documentation is separately
  staged under Linux `.local/agent-platform-design-review/implementation/`.
- Graph refreshed without persistence: 6,741 nodes / 23,979 edges. No graph artifact,
  credentials, raw caller data, audio capture or unrelated workspace changes included.

Earlier diagnostic runs are not acceptance: initial module collection revealed a
circular HTTP/MCP contract import, fixed with a lazy endpoint validator; an early
scripted edit removed a neighboring class, restored before tests. The first combined
run passed 79 with three test failures: one synthetic status expectation and two
legacy permission probes using INSERT SELECT * against newly generated columns.
The probes now target the actual insert permission. A later test command omitted the
existing legacy httpx 0.28.1 test extra and failed collection; corrected frozen runs
include it. Final regression additions also fixed an E731 test helper lint error.
The near-limit retry test initially failed as described above; the SQL example passed.
These failures are not hidden in final success counts.

## Candidate identities and rollout

| Application | Candidate image |
| --- | --- |
| Management | `sha256:31ee0fbc54b41151f23d057d930b130f726c492068fc916524311909de65551e` |
| Action/summary worker | `sha256:97a002657ab7ed1aab968a7325c9fef6c8286960ee80c091d5a1e5b5432fa602` |
| Web | `sha256:1e7f497b6474c3cf442e8b3a214f0e91fa1b450e84f80eaf26c4a1ab7fd9d258` |

No serving migration/restart, external webhook/MCP/provider request, Telegram message,
SIP/RTP call, synthesis or voice/model change. Candidate migrations 0020–0024 and
compatible consumers require coordinated activation/re-provisioning. No ingress or
serving environment was replaced. Kübra/EMA and the disabled second-number mapping
retain their prior state. No commit, push, PR or merge was performed.

## Remaining AGP-08 scope and acceptance

This is the existing 23-scalar-event-field slice, with answered-call condition, flat
body/query fields and optional static business labels. It does not implement declared
custom extraction schemas, approved tool-output projections, optional transcript
policy, additional event filters, nested mappings or dynamic paths. Those planned
features cannot be accessed through arbitrary source paths or prompt instructions.

Real receiver TLS/idempotency/authentication and business acceptance remain untested.
Idempotency only helps if the receiver honors it. Shared scheduler quotas conservatively
cover Telegram and HTTP in the existing legacy provider bucket; no per-receiver quota
or throughput guarantee is claimed. No live traffic soak, P50/P95 non-regression,
concurrent-call capacity or new carrier/GPU acceptance. AGP-07 approved-provider/MCP
acceptance and public-launch gates remain separate. Next independent work is declared
validated extraction and approved output projection, followed by remaining event policy.
