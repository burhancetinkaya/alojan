# Summary rate-limit recovery and expanded quality evidence — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
Ponytail full: reuse the existing scoped worker, bounded input and fenced database lease.
Previous turn made concrete progress (TLS receiver acceptance and identification of
real semantic failures). This turn does not complete the live-readiness goal.

## Implemented recovery

An actual provider diagnostic identified HTTP 429 errors. Scoped summaries now defer
only the SDK's explicit `RateLimitError`, never an arbitrary exception with a claimed
status. The existing processing lease becomes a cooldown, without holding a thread,
connection or model client open. A claim remains fenced by workspace/release/token;
another eligible job can run immediately. The next attempt reloads the immutable
release/input and rechecks the original connection's current authorization.

Default/minimum cooldown is 60 seconds. Retry-After seconds and timezone-aware HTTP
dates are honored up to 300 seconds; malformed, nonfinite, negative numeric or longer
delays are terminal rather than retried prematurely. The third total claim cannot
defer again. Claims consumed by earlier cancellation/infrastructure recovery also
count toward that limit. Credentials/authentication/schema/model errors otherwise
retain their previous behavior. Cancellation and failed DB transactions preserve
recoverable fencing. No response body or credentials enter diagnostics.

No summary finalization or action is queued while deferred. A successful later attempt
or terminal failure finalizes once through the existing atomic path. This is post-call
work with no external tools. Live-turn retries and the legacy rollback worker are not
changed. There is no new dependency, migration, service, user setting or DB permission.
This is a per-job bound, not a provider-wide quota scheduler or capacity certification.

## Linux verification

- Initial focused retry/scoped persistence tests: **38 passed in 24.65s**.
- Broader compatibility: **105 passed, 1 failed in 80.42s**. The failure was a new test
  fixture calling its synchronous routing helper inside an event loop. Moving fixture
  initialization outside that loop fixed the harness; no production guard was relaxed.
- Final focused retry/fencing/other-job progress: **39 passed in 25.12s** (overlap).
- Final affected consumer boundaries: **90 passed in 48.13s**, no skips. Includes
  summary worker, scoped records, declared outputs, runtime/database and lifecycle.
- Tests cover eventual recovery, three-attempt exhaustion, cooldown duration and no
  early claim, no premature event/action, original credential identity, revocation,
  stale token rejection, authentication failure, HTTP-date/seconds bounds and another
  call finishing while the first job cools down.
- Frozen production worker dependencies imported the current source successfully in
  a network-disabled, read-only container with source mounts. An initial attempt using
  an unpopulated local project virtual environment failed on missing cryptography;
  that was not treated as a pass. No package/lock changes were needed.
- Final Ruff lint/format passed for five affected Python files. Task delta and full
  Git whitespace checks passed; five source hashes match Mac/Linux. The graph was
  refreshed without persisted artifacts: 7,011 nodes / 25,315 edges.

## Real model investigation and remaining gate

Chronological database ordering and correct delivery of model instructions were checked.
The provider returned reasoning-token usage for a diagnostic request. Official Cerebras
documentation describes [reasoning settings](https://inference-docs.cerebras.ai/capabilities/reasoning)
and [structured output support](https://inference-docs.cerebras.ai/capabilities/structured-outputs);
those capabilities do not establish semantic accuracy for this application.

Private experiments were not adopted: high reasoning passed 4/6 focused tests (one
429 and one semantic failure); reordered output fields still generated unsupported
references; plain dialogue formatting passed 3/6; a pure output-tool experiment failed
SDK validation, including an empty value for the fixed `promised_action='none'` literal.
The model, preset, transport and public Summary schema remain unchanged.

The only summary-policy change asks for a non-sensitive ambiguous phrase to be kept
in unresolved questions rather than inventing a new referent. Its initial focused
real screen passed **6 cases in 26.35s**. The expanded corpus adds document ambiguity,
an actual person/hiring context, and two independent products with only one corrected.
It retains all earlier assertions and strengthens source-fidelity checks.

**Expanded acceptance: 37 passed, 2 failed in 289.44s. Do not promote the candidate.**
There are 27 legacy/shared-policy cases and 12 real scoped typed-output cases. All 12
typed cases and new counterexamples passed. Two unresolved phrases changed `hangisi`
to `hangileri`, failing exact-source preservation. No invented-person or stale-product
failure was observed in this run, but that is not a general correctness guarantee.
Manual review confirmed legitimate people and independent product quantities were
preserved. The remaining failed assertions were not removed or counted as passes.

The opt-in fixture now spaces requests by six seconds. Scoped worker measurements
6.775–7.770 seconds include that test delay and are not production latency evidence.
No 429 occurred in the expanded run, so real provider recovery was not exercised there;
the durable retry evidence is the real DB/scoped worker with synthetic provider errors.
The scoped test now explicitly fails when a deferred job has no finalization, instead
of accidentally unpacking a missing row. Deferral is never reported as success.

## State and next work

Private synthetic artifacts are under Linux `.local/summary-quality-20261026/`:
`high-screen.log`, `order-screen.json`, `dialogue-screen.log`, `tool-screen.log`,
`ambiguity-quote.log`, `expanded.log`, `expanded-legacy`, `expanded-outputs`,
`final-retry.log`, `compatibility.log` and `final-boundaries.log`.

No raw real caller data, external webhook POST, Telegram send, Hindsight write,
serving restart, number/grant/profile change, historical replay, commit, push or PR.
No candidate images were rebuilt/promoted and no UI changes required browser reruns.
Current source is synchronized to the authorized development checkout; maintained docs
stage separately rather than overwriting remote maintained documents.

Next resolve the source-fidelity requirement and verify complex scenarios through the
managed runtime, then proceed to coordinated activation and matched voice/load/rollback
acceptance. Prompt-only safeguards do not guarantee complete semantic accuracy or
arbitrary-secret redaction. Functional tests do not prove five/50-call throughput.


## Follow-up: managed correction corpus

The source-quote schema experiment was rejected after real semantic regressions.
The retained baseline now has full managed-worker correction coverage: 25/27 passed,
with obsolete-product and invented-person failures. The overall quality gate remains
open. See [managed acceptance evidence](source-fidelity-2026-10-26.md).
