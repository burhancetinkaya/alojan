# Linux Docker runtime

M0-03/06/08 and M5-03, [ADR 0011](ADR/0011-docker-runtime.md). This profile runs
gateway, standard large-v3 ASR, EMA TTS, agent, API, Telegram and PostgreSQL in Docker.
It retains the current single-call limits; containerization does not add concurrency.

## Prerequisites and private state

- Linux x86-64, Docker Engine/Compose, NVIDIA driver and Container Toolkit.
  Register the `nvidia` runtime; this profile uses `runtime: nvidia` with
  `NVIDIA_VISIBLE_DEVICES` (default GPU 0). The existing daemon can use this path
  without a disruptive restart to enable bare `--gpus` device discovery.
- Prepare the pinned ASR/EMA weights using the existing worker model-download
  commands. Keep `asr/models/` and `ema/` in a private state directory. ASR mounts
  its cache read-only; EMA needs write access for compiled kernels/caches.
- In the same directory, provide `dev.env`, `agent.env`, `asr.env`, `netgsm.env`,
  `telegram.env` and `telegram-owner.env`, all mode 0600. Use the existing setup
  guides for values and bot pairing. No credentials belong in image layers.
- `dev.env` supplies `POSTGRES_PASSWORD`, `POSTGRES_PORT` (15432 by default) and
  `ALOJAN_DATABASE_URL`, using the host loopback database address.
- Copy [the Docker environment example](../.env.docker.example) to a private
  Compose environment file and set `ALOJAN_STATE_DIR` to the absolute
  state directory, `ALOJAN_RELEASE` to a unique image tag and `ALOJAN_UID` /
  `ALOJAN_GID` to the owner of the mounted files. Include the database variables
  required by `infra/compose.yaml`; the default UID/GID is 1000.

Do not use `docker compose config` without `--quiet` in shared output: rendered
configuration can contain private carrier/database settings. Do not publish images
until the repository and bundled dependency/model licenses have been reviewed.

## Build and start

Run from a clean source release on Linux:

```sh
docker compose --env-file /absolute/private/compose.env \
  -f infra/compose.yaml -f infra/compose.voice.yaml config --quiet
docker compose --env-file /absolute/private/compose.env \
  -f infra/compose.yaml -f infra/compose.voice.yaml build
```

The build verifies existing PJSIP/gRPC/model pins and runs native CTests in the
gateway build stage. Python environments use frozen service lockfiles. No models
download during service startup. Base images are digest-pinned; direct apt packages
are version-pinned, while their transitive Ubuntu packages are resolved by apt.
Preserve image IDs and package inventory for a release; the build is not a claim of
bit-for-bit reproducibility across future Ubuntu repository changes.

On a fresh database, first start PostgreSQL and run the migration module:

```sh
docker compose --env-file /absolute/private/compose.env \
  -f infra/compose.yaml -f infra/compose.voice.yaml up -d --wait postgres
docker compose --env-file /absolute/private/compose.env \
  -f infra/compose.yaml -f infra/compose.voice.yaml run --rm --no-deps \
  --entrypoint uv agent run --frozen --no-sync --project services/agent \
  --env-file /run/secrets/database_env python -m alojan.migrate
```

Pair/activate Telegram
explicitly using its setup guide; ordinary restarts must never reactivate/backfill it.
For an existing installation, retain the Compose project name and volume. Back up
the database, check for active/ringing calls and stop the previous listener before
stopping its workers. Disable the old Telegram user service before starting its
container. Never run two EMA instances or two delivery workers during cutover.

```sh
docker compose --env-file /absolute/private/compose.env \
  -f infra/compose.yaml -f infra/compose.voice.yaml up -d --wait --wait-timeout 300
docker compose --env-file /absolute/private/compose.env \
  -f infra/compose.yaml -f infra/compose.voice.yaml ps
```

Gateway startup waits for all three voice workers on initial Compose startup.
After a host restart, Docker restart policies do not reproduce Compose dependency
ordering: workers retry initialization, and the gateway retains its bounded
dependency-failure behavior until they warm up. API health is database health, not
an end-to-end voice guarantee. SIP OPTIONS health checks do not place phone calls.

## Recovery and operations

Workers get 180 seconds to warm up. Every 10 seconds, the watchdog runs a local
probe with a five-second outer deadline. After three consecutive failures it
terminates the child process group, waits up to 15 seconds, then forces cleanup
and exits. Docker restarts the container. A crash is also detected by child exit.
These are process/event-loop health probes, not a continuous inference benchmark;
a GPU kernel stall with a still-responsive gRPC loop is not covered by this watchdog.
Telegram advances a private heartbeat only after a successful queue/delivery loop;
its probe tolerates 90 seconds for bounded outbound network requests.

`restart: unless-stopped` applies to all seven services. Ensure the host Docker
service starts on boot. `docker compose stop` deliberately leaves services stopped
across reboot; use `up -d` to re-enable them. No watchdog mounts the Docker socket.
Restarting a worker during a call cannot preserve in-memory conversation context;
the failed call follows existing fallback/disconnection behavior. Recovery is for
subsequent calls and saved records, not seamless call migration.

The agent reconciles open records older than 300 seconds every 30 seconds, only
in this profile. The gateway must retain its 120-second hard call limit. Recovered
rows retain notes/transcripts and queue post-call work once. Their `ended_at` is
recovery time, `duration_ms` remains unknown, and `failure_code=missing_end_event`.
Telegram labels that distinction. Never enable this policy for a database shared
with longer-call deployments without adding ownership/lease-aware reconciliation.

The existing 128-call agent / 4096-generation worker lifetime bounds still need
call-release protocol work; this profile does not silently discard cancellation
tombstones. A 30-minute soak is not acceptance beyond those limits or at five/50 calls.

### Maintenance-window soak

After an idle-line cutover, use the Linux validation environment to run:

```sh
uv run --frozen python tools/validate-docker-soak.py --minutes 30 \
  --output .local/docker-soak-new.json
```

This checks all seven containers and repeatedly exercises the resident EMA/Whisper
workers with synthetic speech. It occupies their single-stream admission slots:
keep real callers off the line during the run. It is a validation tool, not a
background production monitor. A process restart, failed probe or missing service
fails the run; full details stay in the ignored output file. No carrier call,
production note or Telegram test message is created by this tool.

## Rollback

Keep the previous native command arguments/environment snapshots private. While
idle, stop the new gateway first, then voice and Telegram containers. Leave
PostgreSQL and its volume intact. Restore the previous ASR, EMA and agent processes,
verify readiness, then restart the previous gateway and Telegram worker. Alternatively
deploy the prior tested image tags. Never use `down --volumes` for rollback.

The database recovery is additive and idempotent. Recovered records stay marked
failed; do not reopen them or replay their already-delivered Telegram parts.

## Sources

- [Docker restart policies and service configuration](https://docs.docker.com/reference/compose-file/services/)
- [NVIDIA runtime/device selection](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)
- [Startup ordering](https://docs.docker.com/compose/how-tos/startup-order/)
- [Host networking tradeoffs](https://docs.docker.com/compose/how-tos/networking/)
