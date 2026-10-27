# Dependent-worker quiescence — 2026-10-26

Scope: ADR 0003/0011, AGP-09 / PERF-01/03 preparation, M2–M5, requirements
§12/12.1. Ponytail full. Primary Linux execution, no live inference or carrier traffic.

## Change and review

Reviewed shared generation cancellation, ASR non-preemptible decode, TTS producer/
EMA cleanup, agent setup/turn/end/summary flow, all four launchers, server factories,
health probes and callers/tests before editing. Graph discovery was used; its broad
`wait` references were checked against the actual service source. The installed
EMA scheduler/API source was read inside the existing TTS image because the external
package is not indexed. This was read-only and did not instantiate another model.

`WorkerMaintenance` adds opt-in gating on existing private gRPC servers. Only the
operator's exact regular-file `open\n` record permits new work; startup, missing,
invalid or non-regular state closes admission. File polling is outside media/turn
handlers. Enabled interceptors count entire RPC lifetimes, including stream cleanup;
disabled deployments install no interceptor. Cleanup endpoints retain normal lease,
identity, deadline and persistence validation. No HTTP service, protobuf migration,
profile setting, model selection or concurrency increase was introduced.

On-demand `voice.v1.Maintenance` Health Check is separate from ordinary health and
requires closed admission, zero tracked RPCs/leases/active calls/turns/initializations,
no current legacy summary, a successfully finished native future and confirmed
cleanup. Cancelled/failed futures cannot prove native idleness. EMA's adapter confirms
quiescence only after its existing engine-lock, CUDA synchronization and scheduler/
output cleanup finish. Failures remain unready. Health Watch is not this receipt.

Legacy summary processing pauses new claims while fenced, finishes existing work
and retains queued jobs. Normal service health stays SERVING during maintenance,
so existing supervisors do not restart healthy fenced workers. All three worker
images must support the gate; old images return no maintenance receipt.

## Reproduced failure and fix

The expanded failure suite initially reported **97 passed / 2 failed in 12.63s**:

- The ASR fixture re-raised its deliberately injected native exception during
  teardown. Cleanup now gathers that already-observed test exception; the test
  still requires an unready maintenance result.
- Agent cancellation discarded a producer-cleanup exception inside the shared
  `GenerationControl.wait` gather. Its later `aclose()` could succeed because the
  generator was already closed, incorrectly making maintenance appear ready.
  Track unexpected errors observed while cancelling or concurrently completing a
  cancelled operation. Agent/TTS stream cleanup failures also retain a failure flag.
  Added deterministic pending/already-completed race cases. The agent now propagates
  gRPC AbortError directly instead of attempting to abort the same RPC twice.

These failed attempts are not counted as acceptance. Failure flags are conservative;
there is no operator/API toggle that converts unconfirmed cleanup into success.
Inspect and repair/restart the affected process before accepting a fresh receipt.

## Exact validation

- Initial focused tests: 10 passed in 6.25s. EMA cleanup expansion plus existing TTS:
  37 passed in 7.54s. These were intermediate checks, not additional unique coverage.
- Initial existing service/call regression: 229 passed in 45.67s.
- After the cleanup fixes: 144 passed in 15.62s across maintenance/agent/ASR/TTS.
- **Final service/call regression: 248 passed in 51.57s**, including **19 new cases**,
  zero skips/failures. Includes native-backend blocks, lease retention/release,
  setup and inference rejection, end-call persistence still running, queued summary
  preservation, failed/cancelled futures, EMA cleanup failure, cancellation/completion
  races, safe file handling and the actual operator health CLI.
- Real local SIP/prepared/session/supervised-admission suites: **83 passed in 218.16s**,
  zero skips/failures. Following the final shared cancellation fix, the affected
  managed native-session suite reran: **11 passed in 86.36s**, zero skips/failures.
  Its existing Python 3.12 `audioop` deprecation warning remains.
- Ruff check/format, scoped source review, compose configuration and whitespace checks
  passed. Graph refreshed: 5685 nodes / 18968 edges; no persisted graph cache committed.
- No C++/protobuf changes or native rebuild; no redundant CTest result claimed.

Real loopback gRPC/SIP uses scripted speech and provider backends. EMA cleanup tests
exercise the adapter with simulated CUDA synchronization and scheduler operations.
They do not establish real GPU execution, actual model readiness or PERF acceptance.

## Validation images and live state

Source-only Linux derivatives preserve installed dependencies from exact retained
local runtime image IDs. `worker-maintenance.Dockerfile` requires an explicit base;
its no-default-FROM warning is expected, not a Dockerfile lint pass. Source staging
excludes secrets, host virtual environments, model weights and caches. No dependency
installation, registry publication or deployment was performed.

| Worker | Retained base image ID | Final validation image ID |
| --- | --- | --- |
| ASR | `sha256:d2bab4c59b45c16df88c1ceb5a1959790e4fb8fa6a96d8eee4132e8dd67f9db0` | `sha256:29ab22bc77478359a1118787da664d283e6df63efecd8991412ee0127b718954` |
| TTS | `sha256:5bcd2ccaa4e0fa4f3cc43fa8c20c76f5ef58d110c25b390070f991e8d238f7bc` | `sha256:b67a3792e8f1b635e9a9b516167b1dddb7f52daaef3879dee2f6d00178fb8405` |
| Agent | `sha256:b290dc7246cb9261864fc332a1c7b0265757afff116f0945269651d4d8473f25` | `sha256:dc7d2db695292efc5b6f569a67986d325fa335b7143366151c1ec175d54dd567` |

All three images passed service imports and launcher `--help`; the agent also passed
managed-launcher help. Checks used network-disabled, non-root, read-only, resource-
bounded temporary containers, without secrets, GPU or database access. Final source
hashes were checked against both the Linux checkout and all three staged images.
This is packaging evidence, not actual warm-worker startup or a full-source release
build. Temporary containers were removed; validation images were retained.

Read-only probes against all three resident workers returned ordinary health=0 and
maintenance=1, correctly refusing to treat unsupported old workers as quiescent.
At the last successful check, all seven live containers retained their original
2026-10-24 start times and healthy status. No live account/route/number/grant/publication changes or external sends.

Private `.local/worker-quiescence-20261026/` retains source backups, all test logs,
source hashes, packaging script/results, live probe results and sanitized container
state. Fourteen explicit source/config/test files were synchronized after comparing
and backing up remote versions. Remote root documents remain untouched. SSH timed out during the final documentation
copy, after code/image hashes and all tests were verified. The eight local maintained
documents are complete; their transfer to the existing design-review implementation
directory is pending connectivity. No current host-health claim is made while SSH
is unavailable.

## Next gate and limitations

Use the separate operator states in order: gateway closure and current local drain,
worker closure, then fresh receipts from all three current worker instances. Keep
states closed, exclude other inference producers and revalidate after any restart.
A restarting process can warm a model before its listener is ready, so old receipts
cannot reserve a GPU through restart. Reopening workers for a controlled benchmark
invalidates their idle receipt; retain gateway closure and exclusive producer control.

DB readiness/reconciliation housekeeping may continue. Independent action/summary
workers and an external provider's computation are outside this receipt. No claim
is made that cancellation has stopped remote provider execution. The documented
operator sequence must handle those producers for the selected measurement scenario.

Next: coordinated compatible maintenance deployment and real-worker receipt checks,
then fresh matched voice/PERF comparison. The resident images are unchanged. No real
model/GPU/carrier/PERF gate, frontend completion, production ownership transfer, push
or merge is claimed by this step.
