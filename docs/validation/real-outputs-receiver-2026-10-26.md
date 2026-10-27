# Real post-call extraction and receiver validation — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
Ponytail full: existing worker, provider connection and HTTP transport; no new service,
dependency, migration, public schema version or model selection.

## Acceptance decision

**Summary qualification remains open. Do not activate this candidate.**
The final paced run produced **27 passed, 3 failed in 135.96s**: all 12 managed typed
extraction cases passed, while 3 of 18 expanded summary cases failed. Two ambiguous
schedule references invented a person; one product correction narrated the obsolete
product. Manual inspection confirmed real semantic errors, not assertion artifacts.
No rate-limit error occurred in this final run. A passing small extraction corpus does
not establish general final-meaning correctness, redaction safety or provider reliability.

The opt-in managed test uses a disposable PostgreSQL workspace, restricted management/
records/summaries/credential roles, an encrypted real provider credential, a pinned
published release and synthetic call/audio preparation. It changes the draft after
publication, then invokes the real summary worker. Eight fields cover scalar and array
types, late correction, null unknowns and malicious instructions. It checks durable
output statuses, confirmation/prohibition of invented commitments, no second job and
zero action jobs, notification outbox rows and MCP executions. Free-text product names
accept either the exact name or the caller's noun phrase; this is not canonical entity
ID extraction. Credentials and real caller data are never test fixtures.

## Changes and investigation

Both summary paths now share the same platform policy. It removes the contradictory
instruction to narrate/update a stale note while also omitting corrections, requires
final facts, preserves actor/action ownership and explicitly treats unclear references
as uncertainty. It prohibits credential copying and requires Turkish handover text.
No model request, tool or semantic postprocessor was added. Experimental changes to
the shared Summary field descriptions and backend JSON field ordering were reverted;
those two files are byte-identical to their pre-task snapshots.

Earlier attempts are not acceptance evidence: the initial eight typed checks passed
but manual inspection found stale correction narration. A policy-only revision failed
one of twelve assertions. An interim shared-policy run passed 27/30 but manual review
also found an invented person not caught by the old assertion; that regression check
now rejects person/hiring variants. A Turkish-only prompt experiment failed 10/30.
The final mixed-language policy still fails the expanded gate described above.

Provider request failures were separately diagnosed as `RateLimitError`, HTTP 429 in
a three-case diagnostic run (**2 passed, 1 failed**). Private diagnostics record only
exception class/status. A test-only three-second delay now spaces requests. It neither
adds production retries nor proves concurrent provider capacity. The final scoped
worker timings of 3.772–4.720s include that deliberate three-second wait and cannot be
reported as production latency. A controlled two-request probe obeyed the exact test
instruction with both SDK `instructions` and an inline system message; missing system
instructions were not reproduced. No transport change was justified. The official
[OpenRouter Responses contract](https://openrouter.ai/docs/api/api-reference/responses/create-responses)
documents the instructions field; the probe is evidence only for the tested requests.

## Real TLS receiver and authorized Google GET

**8 passed in 13.66s** on primary Linux. The new receiver tests use real sockets,
TLS and the production HTTP client/worker. Test-only DNS/routing maps the synthetic
public destination to loopback and trusts an ephemeral test certificate. Production
public-address guards remain intact. The disposable database and existing fixtures
exercise encrypted bearer configuration, owner grant, immutable release, finalization
and job completion. No real customer data or external POST/PUT/PATCH is sent.

- POST, PUT and PATCH preserve typed JSON (string, number, false, null), mapped call
  identity, Host/SNI, bearer authorization, business header and stable idempotency key.
  A completed action is not dispatched twice.
- 302 is rejected without following Location; 401 is rejected; 503 and a socket closed
  after reading the payload become `delivery_unknown`. None is automatically replayed.
- Wrong TLS hostname fails before credentials/body reach the receiver and remains
  a retryable connection failure.

The authorized empty Google GET also ran through `Webhook.resolve/send` with no
authentication, call data or query. It returned `failed/rejected` in **0.625s**, without
following a redirect. The earlier independent GET observed 301. This run confirms a
conclusive TLS/HTTP rejection, not successful webhook delivery. The public action
contract remains POST/PUT/PATCH; no GET action feature was added for this diagnostic.
An actual customer's receiver authentication, business deduplication and side effects
remain outside this controlled receiver acceptance.

## Verification and rollout state

- Broad Linux compatibility before the final policy text: **146 passed, 1 skipped in
  90.01s**, covering HTTP receiver/action, outputs, summary, runtime, publication,
  lifecycle, transcript and legacy rollback contracts.
- Final policy consumer checks: **98 passed, 1 skipped in 59.50s** (overlap). The skip
  requires an explicitly selected preserved Linux legacy consumer artifact. It is not
  a rollback pass. No SIP/RTP, GPU, concurrent-call or carrier test ran in this slice.
- Final Ruff lint/format passed for five affected Python files. Full Git whitespace
  and task-delta review passed. Seven relevant source hashes match Mac/Linux,
  including byte-for-byte restoration of the experimental backend/model edits.
  Graph refreshed without persisted artifacts: 6,979 nodes / 25,198 edges.

Synthetic evidence and logs remain under Linux `.local/real-outputs-20261026/`, notably
`paced`, `paced-legacy`, `paced.log`, `http-receiver.log`, `compatibility.log` and
`final-boundaries.log`. No secret files are synchronized. Maintained documents stage
separately under `.local/agent-platform-design-review/implementation`.

No serving restart, number/grant/profile change, historical replay, Telegram send,
Hindsight write or external webhook write occurred. No candidate image was rebuilt
or promoted after this failed quality gate. The prior candidate image IDs remain
historical evidence, not a claim to contain this policy. No UI behavior changed, so
the browser suite was not repeated. No commit, push, PR or merge.

Next resolve the semantic failures and qualify provider-limit behavior before advancing
to coordinated activation and matched voice/load/rollback checks. The live-readiness
goal remains active; this is a recorded failed acceptance gate, not a completed goal.
