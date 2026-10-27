# Bounded MCP schema and Hindsight read acceptance — 2026-10-26

AGP-07/08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
Ponytail full: extend the existing shared schema evaluator, grants and parameter
editor; no new service, dependency, migration or executable plugin mechanism.

## Behavior and review

`bounded.v1` narrows common remote JSON schemas to the existing closed/bounded subset.
It supports scalar-plus-null unions, discards default annotations without applying
values, and recognizes the output-only FastMCP wrapped-result annotation. Missing
closure requires explicit properties. String/array bounds intersect platform limits
(4096 characters / 100 items); required fields, enums and declared numeric constraints
remain. Unsatisfiable minimum/ceiling combinations, arbitrary properties, references,
regex, general combinators and nullable containers remain rejected. Six-level/16-KiB
schema ceilings and argument/result byte limits are unchanged. Wrapped string contents
remain opaque untrusted data; no automatic JSON-to-command or nested output expansion.

Raw schemas/tool digests remain exact. Qualified bindings pin policy and effective
input/output schemas in MCP review v2 and release v8. Consumers recompute them and
reject tampering/downgrades; legacy strict grants/digests remain unchanged. Fixed values
are excluded from model arguments, override attempts fail before network, and effective
input/output validators enforce bounds at execution. No remote default is inserted.
The catalog, typed/null parameter editor, exact consent and declared-output path
selection consume the same effective schemas. Null and omission are distinct.

No-answer enqueue supports v8 as well as v7; both scoped end and setup cancellation
were tested. Final review caught unsafe capability-version inspection before malformed
MCP authorization validation; the order was corrected and null/list/string grant
regressions added. Full affected production/caller/test/config delta was inspected.

## Primary Linux evidence

- Broad compatibility: **234 passed in 123.43s**. Covers qualified/legacy MCP,
  discovery, OAuth, execution, output extraction contracts, lifecycle, publication,
  readiness, prepared releases and owner grants. Synthetic network/model fixtures.
- Expanded schema/lifecycle check: **23 passed in 8.10s** (overlapping), including
  v8 unanswered end/cancellation and no tool executions for those calls.
- Final consumer-boundary review check: **112 passed in 86.49s** (overlapping), including
  malformed grant rejection, legacy publication/runtime, number routing, outputs,
  action grants and no-answer compatibility. No skipped cases in these runs.
- **Real Hindsight acceptance: 1 passed in 3.97s.** Restricted discovery worker found
  39 tools in 1.277s. Exactly one real `list_banks` call succeeded in 0.794s using the
  production DNS-pinned TLS/SDK executor. Fixed random unmatched query, limit 1, offset 0;
  response had zero banks and total zero. Fixed override and revoked-grant attempts were
  blocked without further remote calls. Local grant revocation was explicitly refreshed;
  this test does not measure the background revocation propagation distribution.
- Exact inspected tool digest:
  `c8b1ccfffd82acf2c6e4242c04ba6fe7e0b880a5e8cc7055b8626f683ecbfc43`.
  Read semantics checked against the official
  [Hindsight MCP reference](https://github.com/vectorize-io/hindsight/blob/main/skills/hindsight-docs/references/developer/mcp-server.md).
  This is not an attestation of the deployed server binary/source revision.
- Final real HTTPS browser: **36 passed in 1.0m**, with scoped API/DB invariants and
  zero production writes or external sends. Includes null/fixed/omitted editing, bounded
  field, raw vs qualified schema persistence, v2 review and changed digest. Evidence:
  `.local/web-validation-7acd5aa2a77f43baa8c8b86023bfd0a5` on Linux. An earlier
  candidate also passed 36 browser cases; totals are not additive.
- Final restricted management container validation passed. TypeScript and Next build
  passed; production management, summary/action worker and web images built. Frozen
  worker imports passed with network disabled. Ruff checks/format cover 13 affected
  Python files; pinned Prettier 3.8.3 formatted six UI/type/test files.

Diagnostic failures were resolved and not counted as passes: a new output fixture
omitted its required description; a rejection-message expectation needed compatible
wording; two lifecycle fixtures used stale draft version 1 after editing to version 2.
The first web build met existing root-owned build artifacts and succeeded under the
existing Docker build ownership. Initial harness commands lacked test-only httpx or
contract PYTHONPATH; corrected commands are documented. None justified weakening a
production permission/schema guard. The real read acceptance passed on its first run.

## Candidate identities and deployment

| Application | Image |
| --- | --- |
| Management | `sha256:03047806993d5f549885e73cba4ad549835e6041df03b120da2d14de26f9ba43` |
| Summary/action worker | `sha256:489f9fc3a9bc3abe7fc6539a34f78cc8fde96203466593f4d09a609a6734894f` |
| Web | `sha256:7a03bf66c51232e507e343a91c94cbe6f41c0b6d9299f15a4cab8da100dde066` |

Install compatible readers before authorizing/publishing new v8 agents. No new DB
migration or role grant is introduced; preserve the prior additive chain and scoped
role setup. Older consumers cannot consume v8. Rollback uses a compatible prior release,
not manifest mutation. Do not replay historical events or auto-approve discoveries.
Sources synchronize to the authorized Linux checkout; maintained docs stage separately
under `.local/agent-platform-design-review/implementation`. Graph refreshed without
persistence: 6,952 nodes / 24,914 edges.
All 19 changed/new source hashes match Mac/Linux. Task added-line whitespace and full
Git diff whitespace checks passed; unrelated pre-existing changes were preserved.

## Limits and next work

The real test uses a disposable PostgreSQL workspace, synthetic prepared audio/model
qualification and a synthetic call record. No SIP/RTP, GPU inference, real caller data,
serving agent grant/profile/number change, remote memory write or Telegram send occurred.
The production Kübra/EMA release and disabled second mapping were not changed. No commit,
push, PR or merge. One none-auth read is accepted; all other tools/auth providers remain
unqualified. The schema intentionally rejects unsupported remote constructs.

The earlier Google GET returned 301 without a redirect; it remains connectivity-only,
not post-call POST/PUT/PATCH receiver acceptance. Real structured model extraction,
receiver/payload acceptance, coordinated activation and matched voice/load/rollback
checks remain open. Single-request latency is not P50/P95 or concurrent-call capacity.
No media callback work or per-turn discovery was added. This completes this compatibility
slice, not the live-readiness goal or the separate public-launch/carrier gates.
