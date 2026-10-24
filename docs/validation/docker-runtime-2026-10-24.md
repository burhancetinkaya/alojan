# Docker runtime and service recovery validation

Tasks M0-03/06/08 and M5-03; US-01/07; requirements sections 12 and 15;
[ADR 0011](../ADR/0011-docker-runtime.md). The owner explicitly selected Docker
for every assistant runtime component. Source baseline: published `21f0cca` plus
this focused change. No new model, prompt text, carrier routing or recording policy.

## Implemented and deployed

- Seven Compose services: PostgreSQL, gateway, ASR, TTS, agent, API and Telegram.
- `unless-stopped` restart policies, bounded logs and unprivileged voice/application
  containers. Explicit NVIDIA runtime with device 0; no Docker socket mounts.
- In-container watchdogs use bounded local probes, restart after repeated process
  unresponsiveness, and forward shutdown to the worker process group.
- Opt-in, bounded/transactional stale-call reconciliation in the supplied profile:
  120-second gateway hard limit, 300-second recovery age and 30-second scan interval.
  Notes/dialogue survive; summary jobs and recovery events commit atomically.
- Recovered notifications distinguish recovery time from unknown hangup time and
  do not newly notify historical calls from before channel activation.

The existing database volume and paired Telegram channel were retained. An idle
cutover stopped the native gateway and five speech/agent workers (including two
old ASR rollback listeners), then disabled the old Telegram user unit. All seven
containers became healthy. Private process/environment snapshots and a database
dump were saved before cutover. The live database retained 28 calls and seven
delivered notifications, with no pending notifications at the post-cutover check.
Those are aggregate preservation checks, not committed caller records.

The native agent source on the host lagged published main. Images use main's
previously committed agent behavior, not that older source; the old source remains
available for rollback. This task edits no prompt. The owner subsequently reported
a live handset test; Docker gateway events and the ended/completed database record
confirmed that the container deployment handled that call. No personal transcript
or caller identifier is included in this evidence.

## Completed evidence

| Check | Result and scope |
|---|---|
| Gateway image build | Pinned PJSIP/gRPC/ONNX artifacts built inside Docker; all nine native CTests passed in 2.47 seconds |
| Docker Python/SIP suite | 130 passed, zero failures/skips, 422.88 seconds; one existing Python 3.12 `audioop` deprecation warning |
| Focused Linux recovery tests | 35 passed in 3.82 seconds; superseded by the broader container run above |
| Recovery boundaries | Current calls preserved, concurrent reconciliation idempotent, audit failure rolls back call/job updates, late end does not duplicate jobs, historical notification exclusion |
| CUDA ASR container | Seven synthetic gRPC cases passed; entity check passed; standard large-v3 revision unchanged |
| CUDA in TTS image | A 256-element GPU computation matched its CPU reference |
| Process crash injection | An isolated ASR worker killed with SIGKILL recovered to Docker healthy in approximately 22.4 seconds, one restart |
| Process hang injection | The isolated worker stopped with SIGSTOP recovered in approximately 62.4 seconds, one restart; no manual recovery signal |
| Real-model local conversation | Synthetic PCMA call inside a validation container used the resident Docker CUDA ASR/EMA and real OpenRouter; two turns, durable unconfirmed note, closing and post-call summary passed in an isolated DB schema |
| Initial runtime health | All seven services healthy; real EMA CUDA warm-up completed; GPU allocated approximately 4090 MiB at idle after retiring old ASR workers |
| Source and library checks | Changed runtime file hashes in all four images matched the release source; gateway shared libraries resolved |
| Host isolation | All 34 unrelated application containers retained their IDs and start times; no Docker-daemon or host restart |

The native dependency build emits upstream warnings; they were not promoted to
clean compiler diagnostics. A final gateway layer updates only the reviewed
watchdog/probe files over the successfully built image; the native executable is
the tested one. Base image IDs and package inventory are retained privately.

Initial setup exposed two issues before cutover: the already-running Docker daemon
does not discover bare `--gpus`, so the existing explicit NVIDIA runtime was used;
and uv's build-owned cache was not writable by the runtime UID, so runtime uv uses
a separate private `/tmp` cache. Both were corrected before the successful checks.

## Soak

The seven-container soak passed in **1,803 seconds** with **56 successful samples**.
All seven container IDs remained unchanged, with zero restarts and no OOM events.
Every sample synthesized the same short Turkish system-check sentence with resident
EMA and received a non-empty final Whisper recognition. This verifies continued
inference availability, not transcript accuracy across a representative corpus.

Synthetic TTS-to-ASR probe time was 344–392 ms (median 366.5 ms). This excludes
telephone turn detection, LLM response and caller playback, and is not a live-call
response-latency claim. Sampled global GPU memory remained 4,050 MiB. Container
memory at the first/last sample was approximately 78.31/78.33 MiB for gateway,
107.3/107.7 MiB for agent, 498.8/486.2 MiB for ASR and 1.702/1.699 GiB for TTS.
These short-run observations do not establish unbounded lifetime memory behavior.

The soak made no carrier calls and wrote no production dialogue/notes or Telegram
test messages. After completion, all seven services remained healthy and all 34
unrelated application containers retained their original IDs/start times. Ruff
lint/format and diff whitespace checks passed; 256 local documentation links
resolved. Changed-file checks found no known credential/private-host patterns.

## Limits

- No host reboot was performed on the shared server. Docker is enabled on boot;
  restart policies and process failure recovery were verified separately.
- One owner-reported live handset call was corroborated in Docker and the database.
  This does not establish full carrier acceptance, five/50-call capacity, latency
  percentiles or broad noisy-speech quality.
- A responsive gRPC loop with a stuck GPU kernel is outside this process watchdog's
  coverage. Restart cannot resume an interrupted conversation's in-memory state.
- Existing call/generation lifetime bounds still require a call-release protocol;
  cancellation tombstones were not silently evicted by this operational change.
- Full M5-03 includes additional failure, retention/restore and quality gates. This
  report covers the owner-selected Docker/service-recovery slice.

Private evidence lives under the Linux workspace's ignored Docker release,
rollback and runtime-evidence directories. No token, phone number, personal
transcript, recording or private endpoint is included in this report.
