# Coordinated platform rollout — 2026-10-27

AGP-07/08/09; M4–M5; ADR 0011; US-01/07/08; requirements §9–12/14–16.
The owner explicitly authorized Linux deployment and deferred further post-call summary
quality work. This report records deployment, not complete live-readiness qualification.

## Scope and preflight

Reviewed the running containers, private deployment manifests, additive migration ledger,
prepared assets and host voice-preparer. Compared 298 source/test/build files between
Mac and Linux. Application/build source matched; existing documentation, two dialogue
fixture files and the native-auth test differed and were preserved, not overwritten.
No unreviewed remote source change was replaced.

Built current management and action-worker images using their existing pinned locks,
web using its pinned Dockerfile, and an agent source derivative of the verified existing
agent image. The latter retains installed dependencies; its runtime reports Agents SDK
0.24.0, grpcio 1.78.0, cryptography 50.0.2, httpx2 2.16.0 and Pydantic 2.14.1.
All three existing release manifests compiled under control, candidate agent, candidate
worker and candidate management. Compared name, conversation instructions, engine,
speech/synthesis, note configuration, model connection and ASR replacements: identical.
This checks configuration, not measured voice latency. No release was republished.

Primary Linux source tests: **170 passed in 127.44s** across MCP schema/runtime,
lifecycle actions, HTTP actions, summary worker, agent runtime, release readiness and
declared outputs. Disposable database schemas and synthetic external/model fixtures;
no real-model summary quality corpus was run. Existing real-integration evidence retains
its original scope and limits.

## Deployment and preservation

Stopped the idle host preparer, acquired its advisory/file locks and verified no active
admission journal. Stopped management/web writes, requested persistent native admission
closure and required fresh drained acknowledgement. Waited for no active call or pending
summary/action work before stopping the agent and post-call workers. ASR/EMA stayed
resident. Existing paused/failed actions were not reset or retried.

Captured a consistent private PostgreSQL custom-format public-schema backup and checked
its archive inventory. Applied migrations 0020–0025 and reran the migration runner for
idempotency; the ledger now has 26 entries. Refreshed existing scoped management,
routing, records, summaries, readiness, provider-credential, action and voice-preparation
roles. Created separate restricted MCP discovery/execution roles and private credentials.
No owner/global credential was substituted for an executor role.

Configured the exact previously authorized Hindsight endpoint in the operator MCP
allowlist. No production MCP connection, tool review, grant or agent selection was
created automatically. Other endpoints/providers require their own configuration and
qualification. No OAuth provider was registered; empty OAuth availability is intentional.

Activated compatible readers before reopening management and admission. The independent
MCP-discovery service has no HTTP listener or GPU access and uses bounded CPU/memory.
Updated the host coordinator to a content-addressed source tree with its frozen existing
voice-preparer dependency lock. Existing resource limits, ports, provider key, model,
voice assets, private HTTPS origin and single-number routing remain.

The first cutover fingerprint included the new `agent_releases.mcp_grant_id` column and
therefore rejected the schema-only difference. Automatic recovery restored previous
services and reopened admission without database restoration. All other original
fingerprints matched; a separate comparison of every original release column matched,
and every added MCP reference was null. The corrected second attempt retained the first
attempt's evidence, reused verified scoped credentials, took another backup, and completed.
No user data was discarded or historical action replayed. Recovery against the migrated
schema is observed only for the unchanged old releases, not future v8 configurations.

## Active versions

| Component | Active image/source identity |
| --- | --- |
| Management | `sha256:c93081a112a07e1eb06206c92ec7b994959624169ffa168f72225f6befc1bf3c` |
| Summary, delivery, MCP discovery | `sha256:31906ec9ebb5256fe09d04c3b3ea3a6b4de679cc2ebdfd7af29a0b40d542737a` |
| Web | `sha256:7a03bf66c51232e507e343a91c94cbe6f41c0b6d9299f15a4cab8da100dde066` |
| Managed agent | `sha256:ed3ca51a938afd0c2722a80ee5157e0e2c1593cd17fa17805a39a36af06e04d7` |
| Host preparer source | `50e768a30947ebca736c22e3663a9fd7f31517aa2b33deabbe269c75d04d92e3` (63 source/lock files) |

Gateway, ASR, TTS, PostgreSQL and legacy health API container identity/start times were
preserved. No GPU model warm-up or new voice generation was initiated. Number bindings,
profiles, existing records and action intent/status were checked unchanged before
admission reopened. One enabled verified number has fresh release readiness. Berkcan's
second mapping remains disabled. No new external message or MCP tool call occurred.

## Postdeployment checks

- Native admission acknowledged open after fresh route readiness. Agent, gateway,
  ASR, TTS, management and PostgreSQL report healthy with zero restarts. The three
  background workers are running with zero restarts and no fixed unavailable/error
  markers; they do not have Docker health checks. The host preparer is active.
- Read-only HTTPS owner browser smoke passed login/logout, existing Kübra configuration,
  original prepared EMA audio decoding and account/number/connection/call navigation.
- A second read-only owner smoke passed MCP agent controls, HTTP action controls and
  both connection forms, with no authenticated API or browser errors. Login/logout
  are the only allowed mutations in these checks; no profile save, grant or send.
- The first second-smoke attempt incorrectly counted expected unauthenticated session
  401s as failures. The corrected check measures the authenticated interval; login
  and logout still have independent UI assertions. The failed attempt is retained.
- Final action counts remain nine sent, one paused and one failed; no added execution.
  Zero active calls and zero MCP executions at inspection. These are status snapshots,
  not end-to-end call quality or throughput evidence.

Build/preflight harness failures also remain recorded: Docker interpreted a bare image
ID in FROM as a registry name, resolved by tagging/verifying the exact local base;
a temporary release-manifest mount required explicitly matching the container test UID.
Neither failure changed the serving runtime.

## Rollback and remaining work

Private Linux evidence is under `.local/platform-rollout-20261027/`, including both
cutover attempts, backups, before manifests, image identities, compile checks, pinned
preparer release, health snapshots and browser logs. These contain private deployment
material and are not Git artifacts. Do not rerun one-shot cutover scripts blindly.

Restore compatible releases/readers under drained admission after checking outstanding
work. Do not revert to an old reader once newer manifests/jobs have been published
without proving compatibility. Never restore a predeployment database over newer calls,
mutate historical release manifests, or replay terminal/uncertain external writes.
The old binaries/configuration and unit are retained, but complete latest-release
rollback/load/soak coverage remains a separate acceptance package.

No new handset call, matched voice benchmark, GPU quality, simultaneous-call capacity,
public launch, additional OAuth/tool qualification or summary-quality pass is claimed.
Next: latest-release end-to-end functional checks, then performance/isolation/soak and
full operational recovery. No credential, personal transcript or full number is included
here; no commit, push or PR publication occurred.
