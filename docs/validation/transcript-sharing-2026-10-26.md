# Optional transcript sharing candidate — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.4/11/12/14–16.
Ponytail full: extend existing HTTP actions, exact grants, prepared greeting identity,
scoped finalization, immutable delivery and Next/shadcn controls. No new dependency,
service, migration, role permission, model request or media callback work.

## Result and review

HTTP actions opt into `bounded_text.v1` and must map both `transcript.text` and
`transcript.status` into the JSON body. Query and Telegram transcript mappings are
rejected. Default off preserves old serialized digests and greeting text. Release v6,
review v5 and final event v3 protect this new intent. Editing requires new exact owner
consent; active calls and queued jobs retain their pinned intent.

A mandatory sharing notice joins the prepared greeting before the editable question.
Speech identity changes, so publication rejects old audio. The UI explicitly discloses
sensitive data, no automatic semantic redaction, recipient responsibility, bounds and
no raw audio/model reasoning. Preview is synthetic and never sends. The mobile consent
screenshot was reviewed; text wraps within the dialog and the content scrolls.

Finalization queries only eligible final caller and sent assistant rows from the exact
scoped call, ordered by timestamp/id, with 101-row lookahead and 8192 SQL characters
per row. Projection removes controls/bidi, limits 100 rows / 8192 UTF-8 bytes, and
reports complete/truncated/empty. Above a 60000-byte event envelope it substitutes
null / omitted_size_limit before the existing 65536-byte database ceiling. No copy
occurs for disabled or unmatched intent; sibling actions receive only selected fields.

Complete means retained eligible rows fit, not perfect ASR or word-level alignment of
partially played assistant speech. Existing sent-row history semantics apply. This adds
no recording, universal PII classifier, receiver retention guarantee or cleanup job.
Copied event/job text follows existing storage access/lifecycle policies. Existing
exact grants, revocation, bounded requests, idempotency, retries and no replay remain.
Reviewed contracts, consumers, SQL access, fixtures, frontend callers and task delta;
graph-first discovery was supplemented by direct reads where pattern results were empty.

## Primary Linux evidence

- Initial focused transcript/condition/output suite: **24 passed in 17.40s**.
- Broad compatibility: **250 passed in 186.69s**, including transcript, conditions,
  declared outputs, HTTP/grants/delivery/retry, summaries/scoped records, publication,
  runtime, prepared releases, MCP and call management. Real disposable PostgreSQL
  schemas and restricted roles; synthetic external transports only.
- Expanded transcript/SQL suite: **7 passed in 3.62s**, then final **9 passed in
  6.67s** after adding disabled-copy and event-envelope tests. Counts overlap.
  The envelope test explicitly injects future metadata to exercise the guard separately
  from current sub-budgets, then verifies actual database finalization and synthetic
  worker delivery preserve the summary and emit the null/omitted state.
- Real HTTPS browser harness: **34 passed in 58.0s**, followed by DB invariants.
  Includes real restricted-API journeys and intercepted UI contracts. New journey
  covers opt-in/save/reload/preview/consent/grant/disable and mobile layout. Evidence:
  `.local/web-validation-defa2d351b9e438dbe96f3c1a761ddb9` on Linux.
  Harness reports zero production writes and zero external sends.
- TypeScript and Next production builds passed on pinned Node 22.23.1. Management,
  summary/action worker and production web images built. Restricted management image
  validation passed; frozen summary/delivery imports passed with network disabled.
- Final Ruff check/format: ten Python files. Pinned Prettier 3.8.3/TypeScript checks
  cover the four changed UI/type/test files. No new dependencies or lock changes.
- Refreshed graph without persistence: 6,875 nodes / 24,927 edges. Private synthetic
  screenshot/evidence stays ignored; no real transcripts, credentials or graph artifacts.

Initial lint rejected imported pytest fixture aliases shadowed by test arguments
(F811). Module aliases resolved the fixture import correctly; subsequent checks passed.
This diagnostic failure is not counted as a pass or a production failure.

## Candidate images and activation

| Application | Image |
| --- | --- |
| Management | `sha256:734ec04d2aa223f48ea826433996cee345d00b6a6a7f286a130de269a720f9f1` |
| Summary/action worker | `sha256:5db9842cc916d5885c1575baebccd3dca3cd4392fc78d70933480ae069e3a39c` |
| Web | `sha256:7acd80b79903152d6e4945fdf841faa09c2516893bcd9f15a3c372ffef5bebd3` |

All 15 source hashes match Mac/Linux; task added-line and full Git diff whitespace
checks passed, including untracked files. Source changes are synchronized to the authorized Linux checkout. Maintained docs
are staged separately under `.local/agent-platform-design-review/implementation/`.
All release-v6/review-v5 readers need coordinated activation before opted-in publication,
including voice/preparer/readiness consumers. Prior candidate migration/provisioning
chain remains required; this slice adds no migration or privilege. Read-only PostgreSQL
example creates no connection, grant, job or request.

No serving migration/restart, ingress/environment replacement, real provider/model/MCP,
webhook/Telegram request, synthesis or SIP/RTP call occurred. Existing Kübra/EMA and
the disabled second mapping were not changed. No commit, push, PR or merge.

## Remaining acceptance

No-answer/interrupted lifecycle filters remain AGP-08 work. Real model extraction,
MCP/provider/receiver interoperability, coordinated activation, measured latency/load,
carrier/public-launch gates remain open. Synthetic tests do not certify performance
or concurrent-call capacity. This evidence completes only the transcript-sharing slice.
