# Post-call summary conditions candidate — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.4/11/12/14–16.
Ponytail full: extend existing typed actions, owner consent, release readers,
transactional finalization and Next/shadcn controls. No new service, dependency,
migration, model request, arbitrary expression engine or media-path work.

## Result and review

Each Telegram/HTTP action selects `answered` (unchanged default), `summary_ready`
or `summary_failed`. Conditions examine durable answered/end timestamps and terminal
summary status only. They do not interpret caller text, model instructions or hangup
reason substrings. A successful summary is not proof of model accuracy, caller
confirmation, complete extracted outputs or external delivery.

The existing finalization transaction creates jobs only for matching actions. With
no matching action it still commits the final event and terminal summary job, without
a delivery row or dispatch-scope entry. With matching siblings, immutable target,
selected fields, lease/retry fencing and live revocation are unchanged. There is no
fallback send, historical replay or re-evaluation from a later draft. Existing
mapping null/omit/fail policy still applies after a condition matches.

Conditional intent requires action-review v4/release v5. Default configurations keep
historical schemas and digests. A condition edit changes the exact consent digest;
old grants cannot authorize publication of the changed intent. Existing active-call
and queued-job releases retain their original condition. Both editors and the owner
review display the condition. SQL examples are read-only PostgreSQL and perform no
configuration write or send.

Reviewed affected contracts, publication/rollback, runtime validation, finalizer,
delivery grant/retry consumers, tests, fixtures and frontend callers plus the full
task delta. Predicates are bounded to four configured actions and use already loaded
metadata; no new query or additional privilege is introduced. Graph discovery was
used first; its incomplete call-edge result was supplemented with source review.

## Primary Linux evidence

- Initial condition suite: **6 passed in 6.32s**.
- Broad compatibility: **243 passed in 188.38s**, covering conditions, declared
  outputs, HTTP/grants/delivery/retry, scoped summaries/records, publication, runtime,
  prepared releases, MCP and call management. Real disposable PostgreSQL schemas,
  actual limited database roles and synthetic external transports.
- Expanded condition/SQL checks: **7 passed in 4.54s**. Includes terminal-status
  truth table, unsupported condition rejection, schema downgrade rejection, exact
  consent replacement, pinned draft independence, mixed Telegram/HTTP fan-out,
  all-unmatched finalization/no replay and the read-only SQL contract. Counts overlap.
- Final real HTTPS browser harness: **33 passed in 1.0m**, followed by all database
  invariants passing. HTTP condition save/reload, changed-consent/mobile review and
  Telegram conditional publication/revocation use actual scoped APIs. Other cases
  include intercepted UI contracts; no real external write. Linux evidence:
  `.local/web-validation-8588f5a8e5da4cbc8437b6623380b27a`.
  Harness reports zero production writes and zero external sends.
- Pinned Linux Node 22.23.1 TypeScript and Next production builds passed. Separate
  management, summary/action worker and production web images built. Restricted
  management container validation passed with disposable limited roles/schema.
  Frozen summary/delivery imports and condition evaluation passed with network disabled.
- Final Ruff check/format: ten affected Python files. Pinned Prettier 3.8.3 and
  TypeScript: six affected UI/test files. Review includes a mobile condition-consent
  screenshot. Source/diff checks include untracked files and preserve unrelated work.
- Code graph refreshed without persistence: 6,830 nodes / 24,619 edges. No credentials,
  caller transcripts, recordings, real full numbers or graph artifacts are included.

Diagnostic failures are not acceptance: the first browser run passed 32 and failed
an existing performance test during account switching. The trace showed logout
succeeded, then no second login request: the test filled a transient form before the
login navigation finished. It now waits for the expected login URL before filling;
the complete rerun passed. An initial frozen-import command used nonexistent module
`action_worker`; corrected to the existing `delivery_worker`. An initial management
validation command omitted the shared-contract PYTHONPATH; corrected invocation
passed. Neither command failure was a serving change or hidden as a pass.

## Candidate identities and activation

| Application | Candidate image |
| --- | --- |
| Management | `sha256:b65a142093035ce2459f9dcd444caafab74440831ba7c31c0793725dc3bcee63` |
| Summary/action worker | `sha256:2afb26dd74796a1bd7e1a4d5bf4265e397ad15f5d020e3b413052345515a9346` |
| Web | `sha256:8382e0f5b57593c09a5282ebf6d6791f816a6dae4be9a9bed8c87c45388b59d4` |

All 17 source-manifest hashes match Mac/Linux. Added-line whitespace and full Git
diff whitespace checks passed, including the new files. Source changes are synchronized to the authorized Linux checkout; maintained
technical documentation is separately staged under
`.local/agent-platform-design-review/implementation/`. Upgrade all release-v5 and
review-v4 consumers together before publishing conditional agents. The earlier
candidate migration/provisioning chain remains pending activation; this slice adds
no migration or database role privilege.

No serving restart/migration, ingress/environment replacement, model/provider/MCP
request, webhook/Telegram send, synthesis or SIP/RTP call occurred. Kübra/EMA and the
disabled second-number mapping remain unchanged. No commit, push, PR or merge.

## Remaining scope and limitations

This is the summary-condition slice, not complete AGP-08 acceptance. Current scoped
finalization requires answered ended calls. No-answer/interrupted outcomes need
separate lifecycle contracts and tests before exposure; they are rejected now.
Optional raw-transcript sharing remains disabled pending explicit disclosure/access
policy, bounded projection and reviewed recipient intent. Existing selected outputs
continue working, but raw transcript/audio/reasoning cannot be selected as action fields.

Real receiver/model/MCP acceptance, sustained load, P50/P95 non-regression,
concurrent-call capacity and public-launch/carrier gates remain untested here.
