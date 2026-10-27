# Self-service journey and lifecycle controls — 2026-10-26

AGP-06 / M2,M5, ADR 0011; requirements §1/12/14–16.
The owner authorized continuing independently through the approved plan.

## Delivered behavior

The existing HTTPS UI/API now has an end-to-end new-owner acceptance scenario:
register an isolated workspace; create an agent; create/select write-only model and
Telegram connections; prepare and listen to audio; review the exact Telegram target
and grant; publish; claim a number; verify ownership/routing separately; wait for
node readiness; bind an immutable release. Missing voice assets, missing grants,
unverified numbers and unready nodes each block the dependent operation. Readiness
failures now have specific user-facing explanations. Draft edits do not change a
bound release or an initialized call's manifest.

Added owner-only lifecycle controls through existing APIs:

- Stop new incoming routing after reviewing the masked number. Existing calls and
  history remain pinned; restarting requires an explicit ready-release binding.
- Close a model/Telegram connection after reviewing its identity and impact. Closed
  immutable connections cannot reopen; create/select a replacement. Already-started
  operations may finish.
- Cancel performs no write. Submission is guarded immediately and controls cannot
  dismiss while pending. Stale number versions and ambiguous responses require a
  fresh review; the UI refreshes authoritative state rather than retrying blindly.

No backend, migration, dependency, prompt, model or media-path change. Browser
fixtures do not add a public test endpoint. A private file bridge validates its
`test_web_` schema and synthetic owner before running the actual preparation worker
with a synthetic generator, number-verification command and node-readiness fixture.
Actual CallRouter initialization checks the pinned manifest, not real SIP traffic.
No synthetic credential is used for an external request.

## Validation and review

Primary Linux host, pinned Node/Playwright containers:

- Final real HTTPS suite: **18 passed in 42.6s**, no skips or retries. Covers the
  complete journey and existing registration, role/CSRF/isolation, edits, publication,
  rollback, call detail/transcript, permission, retry and performance scenarios.
- Lifecycle cases cover cancellation, concurrent binding/version conflict, and a
  server-committed deactivation/revocation whose response is lost. The number is
  disabled after one attempt; the old synthetic call still resolves its original
  release and new call initialization rejects it. Both connection types close.
- Related voice-job, number-routing, provider/Telegram connection and release tests:
  **62 passed in 32.39s**. Ruff format/check, Prettier, TypeScript, isolated frontend
  build and deployable production image build passed.
- Initial journey run had 17 passes and one assertion failure: grant validation
  occurs at publication confirmation, not preview preparation. Corrected the test;
  subsequent runs passed 18 in 42.1s and 41.5s. Final 42.6s run adds mobile modal
  overflow and visual checks. One service-test invocation failed collection because
  its optional `httpx` test dependency was absent; rerunning with pinned 0.28.1 gave
  the 62-pass result. No skipped/failed check is counted as a pass.
- An initial mobile screenshot caught the sidebar's responsive CSS transition.
  Animation-disabled screenshots show the settled layout correctly; no production
  layout change was needed. Stop/revoke dialogs and the connection page were
  visually reviewed at 390px with no overflow. Browser storage remained empty and
  no JavaScript page errors occurred.
- The full affected diff and new harness/test files were reviewed against the
  pre-task snapshot, preserving unrelated work. `git diff --check` passed.
  The code graph was refreshed without a shared cache artifact. No commit/push/PR.

Final isolated evidence:
`.local/web-validation-e9e1a5acc899449b9907b64ae13e9fe5/`.
Private rollout/smoke and local review screenshots: `.local/self-service-20261026/`.

## Private-preview deployment

Web image: `sha256:0028bb0530076977f1db8618852426fe11a988519293b5c4742a03592f806b2b`.
Only web was recreated. Nine application peers kept their container IDs and
configured healthy checks. Management was not restarted and no migration ran.

Read-only deployed owner smoke passed registration rendering, login, existing
Kübra instructions/model, release history, existing EMA decoding, all navigation,
call detail/transcript/delivery status, performance and logout. It opened/cancelled
number-stop and connection-close reviews. A request interceptor rejected every
configuration mutation. Zero browser errors; no new call, synthesis or message.
The existing number/agent configuration and disabled second mapping remain intact.

Rollback: restore `.local/self-service-20261026/web-compose.before.env` to the
private web environment and recreate only web. Previous image:
`sha256:96e9c98977118884069d0aeb3508a729220218a40ecdee35b29e98bf0399c23e`.

## Limits and next work

Functional self-service acceptance reaches the synthetic operator/voice/routing
boundary. It does not establish new-agent GPU quality, real carrier routing,
latency non-regression or simultaneous-call capacity. The latest handset evidence
is unchanged. Number ownership must still be verified by the trusted operator;
users cannot self-approve it. Connection revocation cannot undo an in-flight write.

AGP-07 MCP connection/discovery/selected-tool execution and AGP-08 typed HTTP actions
remain unimplemented. The existing MCP allowlist helper is unconnected and must not
be presented as a complete integration. Both stages require the approved egress,
manifest review, workspace/grant and readiness boundaries before exposure. Real
external integration acceptance needs an approved target and credentials; synthetic
implementation/testing can precede those. Public email recovery and public launch
remain separate from this private preview.
