# Summary fact boundaries and rejected controls — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
Previous goal turn was progress: it added managed acceptance and reproduced semantic
failures. This step strengthens that acceptance rather than relaxing failed assertions.
The live-readiness goal remains open.

## Retained test improvement

The shared legacy/managed assertion now rejects changing arrival into preparation,
reviving a superseded day, assigning the caller's own plan to the recipient, restoring
a withdrawn callback request, and shortening the unresolved quote in an actual-person
context. A product-problem report is not forced to have an empty requested action:
the requirements allow treating such reports as requests for assistance. All previous
assertions remain. No production implementation or serving configuration changed.

Re-evaluation of the previous 27 private synthetic managed outputs with the stronger
assertions yielded **19 passed, 8 failed**. This is a replay of stored outputs, not a
new provider run. Five failures additionally changed arrival into preparation; one
shortened an unresolved quote. The previous obsolete-product/invented-person failures
remain. The corpus is a bounded regression oracle, not proof of arbitrary semantics.

## Rejected private experiments

All inference used disposable records and synthetic caller statements; no external
action jobs, Telegram sends or MCP calls were configured. Production source/presets,
model catalog, credentials, account privacy policy and provider fallback rules were
not altered by these test-local overrides.

- Shortened English summary policy: **3 passed, 6 failed in 74.76s**, 18 deselected.
  This screen used the earlier assertions; ambiguity was still interpreted as people.
- Turkish summary policy: **7 passed, 2 failed in 71.97s**, 18 deselected. Stronger
  assertions caught invented people and changed verbs. Not adopted.
- One additional model review against original records: **7 passed, 2 failed in
  135.82s**, 18 deselected. It retained incorrect preparation claims. The extra call
  was rejected instead of adding permanent cost without passing quality acceptance.
- Same model on a diagnostic Groq route: all **3 cases failed before final output**
  with SDK ModelBehaviorError in 26.72s. This establishes no quality comparison.
- GPT-4.1 mini/OpenAI diagnostic: all **3 cases failed with HTTP 404** in 22.81s.
  A bounded follow-up classified the error as a data-policy failure; an explicit
  Azure Sweden endpoint also returned HTTP 404/data-policy failure. No fallback or
  account-policy change was attempted. No inference-quality claim is made for that
  model. Only safe error class/status/keyword markers entered diagnostic output.

The initial Groq/OpenAI probes selected provider display names; the routing docs
specify canonical slugs. They are not conclusive endpoint qualification. The explicit
Azure endpoint probe used its catalog slug. Recheck authenticated eligibility before
another provider/model comparison; never broaden fallback or privacy settings to
make a probe succeed.

Each pytest-in-Python diagnostic reported two import/rewrite warnings, which were
retained in its log. Tests pace provider requests by six seconds; the extra-review
probe also waits six seconds between its two requests. Wall times are not production
latency measurements and do not qualify a new provider/model/preset.

Public provider metadata lists capabilities, not availability for this account.
[OpenRouter provider selection](https://openrouter.ai/docs/guides/routing/provider-selection)
and [user-filtered model discovery](https://openrouter.ai/docs/client-sdks/typescript/api-reference/models/models)
describe the routing boundary. Actual authenticated requests determine eligibility.
No new model/provider has been added to the approved platform catalog.

## Evidence and remaining work

Private Linux evidence lives in `.local/final-facts-20261026/`, including screen logs,
synthetic outputs, `review-candidates/` and `strengthened-baseline.json`. The test-local
scripts are not production runtime options. No private outputs/credentials were added
to Git. No production restart, migration, image promotion, carrier call, commit or push.

Finish semantic quality qualification before rollout. A provider error is not a
passing semantic test, and syntax/quote fidelity is not sufficient evidence of
correct final facts. Matched voice/load/rollback acceptance still remains afterwards.


## Connectivity interruption and handoff

The authenticated user-model listing command never connected to Linux: its SSH handle
terminated with exit 255/connection timeout. Two separate 10-second SSH checks also
failed. No model-listing HTTP request from that command is claimed. All earlier
provider/test commands had already completed; no inference run is awaiting a result.
The owner was asked whether Linux access is restored. This is the first occurrence
of this connection blocker in the current goal sequence, not a completed or blocked
goal. The preceding work produced stronger assertions and new rejection evidence.

The final test source had already been synchronized and Ruff lint/format passed on
Linux. Five relevant source hashes matched before the interruption; the production
summary policy matches the starting snapshot. New documentation is local and still
needs staging under the remote private design-review folder after reconnection.
Mac syntax compilation and the full Git whitespace check passed; they are not Linux
integration evidence. Graph refresh: 7,032 nodes / 25,586 edges, no persisted artifact.

Next: reconnect to the same authorized host, read the account-filtered model catalog
using the existing credential without changing policy, diagnose eligible canonical
endpoints, and qualify final-fact accuracy. A different model/provider remains an
isolated diagnostic until its compatibility, quality, performance and rollout
requirements are satisfied. Do not bypass publication or silently change the live
voice model to unblock summary testing.


## Follow-up: account discovery and exhausted local test key

The next goal continuation again failed two bounded SSH checks to the configured
Linux host. The SSH handles terminated with exit 255; no remote command or test
remains in flight. This is the second consecutive goal turn with the same Linux
connectivity blocker. Independent read-only investigation still made progress.

The existing Mac project credential successfully called OpenRouter `GET /models/user`
(HTTP 200), which returned 21 eligible model identifiers. GPT-4.1 mini was absent.
Public endpoint metadata for the listed `openai/gpt-6-luna-pro` advertises structured
output and reasoning parameters but not temperature. This catalog result is not
proof of successful inference, compatibility or availability on the Linux credential;
credential equality has not been verified while Linux is unreachable. No private
preset identifiers or raw key/account metadata were added to maintained documentation.

A supplementary macOS diagnostic used the existing Python 3.12.13 environment with
Agents SDK 0.24.0, OpenAI 3.37.0 and Pydantic 2.14.1, matching the root lock entries.
It reused the production summary method, configured style, schema and strengthened
assertions for three synthetic cases, with a test-local model override, no tools,
4096 output tokens and existing 15/20-second limits. It omitted temperature and
selected canonical `openai` with flex/fast variants excluded and fallbacks disabled.
All three requests failed with HTTP 403 before output. This is not Linux, database,
managed-credential, voice, carrier or model-quality acceptance.

One bounded diagnostic on that model and one on the existing Cerebras model both
returned HTTP 403 with key-limit markers. Read-only `GET /key` then confirmed a
configured, exhausted limit with no configured reset period. Only safe status flags
were recorded; no credential, key label, balance or spending amount was printed.
No spending limit, account/privacy setting or provider grant was changed. Stop
further paid inference attempts on this exhausted local key. Listing success does
not establish usable inference quota, and a rejected request is not a semantic fail.

Evidence is private on Mac under `.local/final-facts-20261026/`: `eligible-models-local.json`,
`local-key-status.json`, `local-model-screen.log`, `local-control-diagnostic.log` and
`local-model-diagnostic.log`. Every diagnostic has finished. Production source and
serving configuration remain unchanged; all new documentation still awaits remote
staging. Once Linux is reachable, compare connection identity without displaying
keys, inspect that connection's current eligibility/quota, then resume quality
qualification with authorized usable access. Broader rollout gates remain open.


## Third-turn blocked audit

A new SSH attempt to the configured primary host ended with exit 255 and connection
timeout. A new read-only local key status request returned HTTP 200 and confirmed
that its configured limit remains exhausted. No paid inference was attempted. The
same Linux blocker has now persisted across three consecutive goal turns. Previous
turns made progress through stronger acceptance and account discovery; that does not
prove readiness. No test process remains live.

All independent work at this stage is complete. Required model-quality validation,
Linux scoped integration, remote documentation staging and later voice/load/rollback
gates cannot progress with current access. The blocked audit threshold is met.
Resume after Linux is reachable; first compare the server connection with the local
one and verify usable inference quota. The server may have a different connection,
so increasing the local key limit is not assumed to be necessary. Preserve the full
objective and all failed quality evidence. No production or financial setting changed.
