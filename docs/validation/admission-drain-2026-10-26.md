# Native gateway admission drain

Date: 2026-10-26. Ponytail full; ADR 0003/0011, AGP-09 / PERF-01/03 preparation,
M1/M5, requirements §12/12.1. This implements local maintenance admission control,
not the five/50-call capacity plan or live carrier rollout.

## Behavior and review

The native gateway now accepts `--start-drained 0|1`, defaulting to its existing
open behavior. SIGUSR1 closes new-call admission; SIGUSR2 explicitly reopens it
at the same capacity. Signal handlers only assign a `volatile sig_atomic_t` flag.
The existing SIP callback checks that flag before admitting a new call. Rejection
uses the existing 486 path; source-policy rejection retains 403 precedence.

Ringing/setup calls already admitted before the close acknowledgement continue.
Answered calls retain their RTP streams, budgets, cancellation and BYE handling.
No media callback IO, model reload, database query or HTTP service is introduced.
The main loop logs state changes and reports local drain only after the normal
session reaper has waited for local speech quiescence and setup-worker completion.
Repeated identical signals do not repeatedly log the same state. SIGINT/SIGTERM
keep their existing bounded shutdown behavior, including termination of active calls.

Control is local operator authority, not a caller/tool/API capability. Commands must
be serialized and observed against the current executable/PID and its own logs;
standard Unix signals can coalesce and do not provide request IDs. Closing by signal
is volatile. A maintenance launch must retain `--start-drained 1` across supervisor
restarts, then resume explicitly. A health check or `event=ready` does not prove
admission is open or dependent workers are idle.

`event=admission_drained local_calls=0` deliberately claims only local drain. Remote
cleanup can time out and native GPU work may continue after cancellation. The managed
cleanup regression explicitly exercises `confirmed=0`; it does not turn that into
worker/GPU readiness. Resolve worker leases, cleanup and other inference producers
before real GPU reservation. No second EMA worker is permitted by this feature.

## Linux validation

Source hashes matched before editing; the old remote source was preserved privately.
Built all native targets with the pinned local CMake preset and four build jobs.
No SIP test ran concurrently with a native rebuild.
The tested binary is preserved at
`.local/admission-drain-20261026/voice-gateway-tested` on Linux; SHA-256:
`28f6bbfc252eb39e94a4038307a7807866d892fb51ac8028b4e40f59fb3ef5b4`.

- New real loopback SIP/RTP suite: **8 passed in 16.29 seconds**, zero skips/failures.
  Both PCMA/PCMU preserve audible synthetic RTP for more than two seconds while a
  spare admission slot rejects new/retransmitted INVITEs. Resume admits another call
  while the first remains active. Ringing calls finish setup; pending managed setup
  and timed-out cleanup finish locally before the drained event. Closed startup and
  three invalid startup values are covered.
- Native CTest: **10/10 passed in 3.84 seconds**.
- Expanded existing SIP/prepared-setup/managed-session regression: **120 passed in
  318.19 seconds**, zero skips/failures. Together with the focused suite this is
  128 SIP tests, separate from the ten native CTests.
- Clang-format and Ruff check/format checks passed. The graph was refreshed without
  persisted artifacts. Python 3.12 emitted the already-documented audioop deprecation
  warning; it is not a test failure.

These are native signaling/media and scripted local dependency results, not CUDA,
real provider, carrier, listening, load/soak or PERF latency acceptance. No live
number, account, grant, route, database schema or external message changed.
All seven resident containers remain healthy with their original 2026-10-24 start
times. Final source checksums match Mac/Linux; maintained documentation was mirrored
to the remote review directory while preserving remote root documentation. No push
or merge occurred; hosted CI and clang-tidy were not run.

## Deployment boundary and next step

The resident `lifecycle-20261024` gateway image and Python supervisor remain unchanged.
They must not receive these signals: unsupported USR signals may terminate them.
Do not send `docker kill --signal USR1` to that container's supervisor PID 1. Verify
the compatible gateway child PID after supervised-image integration. Keep the
preserved image/configuration for rollback and avoid replacing a long active call
with bounded SIGTERM shutdown.

Next: validate supervised deployment and remote-worker quiescence for a controlled
maintenance window, then run the matched real voice/PERF comparison. The offline
candidate EMA pack remains available and unchanged. Production ownership transfer,
standing grants, binding activation and carrier canary still require their remaining
acceptance gates. No concurrency increase or general max_calls=0 reload is delivered.
