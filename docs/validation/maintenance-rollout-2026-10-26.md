# Controlled maintenance rollout — 2026-10-26

Historical maintenance-stage record. The owner's subsequent in-place testing
instruction superseded the isolated-candidate sequence: the existing DB has since
been migrated and the managed line opened for a phone trial. See the
[current state and evidence](in-place-platform-2026-10-26.md).

Ponytail full; ADR 0003/0011, AGP-09 / PERF-01/03 preparation, M1–M5,
requirements §12/12.1. This is a maintenance deployment and compatibility check,
not managed-agent publication or matched performance acceptance.

## Preparation and ingress

Restored SSH connectivity and verified all eight previously pending documentation
review copies against their exact after hashes. The seven original containers were
healthy. Preserved the four voice image identities, private inspect snapshots,
rendered Compose configurations and deployed agent/native source artifacts.
Compose comparison allows only image, admission environment and read-only state
mount changes to gateway/ASR/TTS/agent; PostgreSQL, API and Telegram are identical.
No broad project recreation, dependency installation or registry publication.

The old gateway has no admission fence. The owner explicitly authorized executing
the privileged bootstrap step. A dedicated nftables table, syntax-checked before
application, temporarily drops IPv4 UDP packets beginning with `INVITE ` to the
configured Alojan address and port 5060, excluding loopback. It does not flush or
replace other firewall tables. ACK/BYE/OPTIONS and RTP are outside this match;
re-INVITE also matches. This is a bounded maintenance control, not a new SIP security
boundary or carrier acceptance. Its rollback deletes only the dedicated table.
No credential is stored in the helper files or evidence.

After fencing, waited beyond the deployed 120-second maximum call lifetime before
replacement; all 29 recorded calls were ended and all 29 summary jobs were done.
The gateway alone was recreated with `--no-deps --no-build`. Its new instance
reported both `admission_state mode=draining` and `admission_drained local_calls=0`,
and passed normal health. All six other container identities stayed unchanged.

## Real worker startup

Recreated only ASR, TTS and agent using the exact tested maintenance derivatives,
with worker and gateway state files closed. The same model mounts, commands,
secrets and runtime libraries remain selected; no second EMA instance was started.
All three passed normal health and fresh on-demand maintenance health checks.
Each emitted its own current-instance quiescent event after startup. EMA readiness
includes its actual pinned CUDA warm-up. These are real startup/idle receipts,
not inference throughput, speech quality or latency results.

| Service | Image SHA-256 | Container start (UTC) |
|---|---|---|
| Gateway | `e0e21c73db2d49ad45287e2523834cb5900e94176d96704fc9a70961735fa852` | 06:38:57.956652159 |
| ASR | `29ab22bc77478359a1118787da664d283e6df63efecd8991412ee0127b718954` | 06:42:24.535723943 |
| EMA TTS | `b67a3792e8f1b635e9a9b516167b1dddb7f52daaef3879dee2f6d00178fb8405` | 06:42:24.543683907 |
| Agent | `dc7d2db695292efc5b6f569a67986d325fa335b7143366151c1ec175d54dd567` | 06:42:24.548186417 |

## Compatibility harness and remaining gates

The private harness preserves the actual deployed control agent and native binary,
with pinned dependency versions checked against the resident agent. It uses a
loopback SIP peer, isolated disposable DB schema, synthetic Turkish input and the
deployed greeting pack. Synthetic input PCM is cached privately for later paired
comparisons. There is no external telephone call or Telegram sender in this harness.
Worker admission opens only for the controlled attempt and closes in `finally`;
fresh receipts are required again after it finishes. Gateway admission stays closed.

Two initial attempts failed before synthesis: the historical input generator used
the now-reserved `managed-` call namespace without release configuration. The first
failure was reported only as AioRpcError; the second exposed FAILED_PRECONDITION,
`synthesis not configured`. A third attempt using a fixture prefix also failed because the lease API requires
the managed namespace. All three failures reclosed the workers and obtained fresh
receipts. No production guard was weakened. The old leased test protocol must use
its exact retained speech services, or the new harness must explicitly configure
its synthesis profile; renaming the identifier is not a compatibility fix.

An exact-control attempt then restored the retained ASR/TTS/agent images under the
still-closed gateway. The actual deployed agent source and native binary completed
one synthetic two-turn SIP/RTP call with real CUDA speech and OpenRouter: note
persisted unconfirmed, both responses completed, all three call resources released,
call ended and summary persisted. The disposable schema was removed by the harness.
No Telegram send occurred. The controller then restored the maintenance derivatives
and obtained fresh receipts; total switch/test/restore time was **89.86 seconds**.

The two output-port timing observations were 1340/2859 ms after endpoint, and
2264/3859 ms including estimated endpoint silence (not handset playback). This tiny
sample has no useful tail/confidence claim and is not PERF-01/03 acceptance. It
confirms that the retained real-model control still works. Matched sampling,
confidence analysis, load/soak, managed release qualification, owner migration and
carrier acceptance remain open. The second number is absent.

## Schema compatibility finding and current hold

The new agent initially passed RPC/maintenance health but repeatedly reported
`call_reconciliation_unavailable`. Read-only inspection confirmed production still
lacks `call_route_snapshots` and `summary_jobs.scope_id`. The new Store uses both
for scoped-job isolation; ordinary RPC health alone was insufficient to establish
compatibility with the unmigrated live database. No production migration occurred.

Stopped the resident agent while gateway/ASR/TTS admission stays closed. This
explicit stopped state supersedes its earlier startup receipt. Do not reopen this
combination or describe the whole voice deployment as ready. A matching isolated
schema/runtime is required for candidate validation; production migration remains
a later accepted step. API, Telegram and PostgreSQL were not recreated.

Strengthened the legacy launcher startup query to validate both required relations
before creating a listener. Regression tests run against actual disposable Linux
PostgreSQL schemas: old and partially upgraded schemas reject startup; a fully
migrated schema reaches the listener boundary. Combined migration, managed-startup
and maintenance regression: **43 passed in 20.94s**, no skips/failures. Ruff check,
format check and whitespace checks pass. The production guard remains staged;
the stopped resident agent is not restarted against the incompatible schema.

Built `alojan-agent:maintenance-schema-validation-20261026`, image
`sha256:484d70ab98029c428e97695989570631627a52e77acbee093a49827f4663cf7b`.
An isolated non-root, read-only container with dropped capabilities, 0.5 CPU,
512 MiB and 64 PIDs exercised startup against the unchanged live schema using
a synthetic provider credential. It exited 1 with `UndefinedTable` before readiness,
as required. No GPU, provider request, listener or resident-agent restart occurred.
This failure is the expected negative-test outcome, not an operationally ready agent.

Private Linux artifacts: `.local/maintenance-rollout-20261026/` contains before
snapshots, immutable image selections, explicit rollback configuration, gateway and
worker receipts, ingress apply/rollback helpers, synthetic harness and attempt logs.
Admission remains closed during this work; do not mistake healthy containers for
an open customer line. To reopen, first validate the selected runtime and workers,
open workers, verify normal/release readiness, open gateway and verify its current
acknowledgement, then remove only the temporary ingress table.
