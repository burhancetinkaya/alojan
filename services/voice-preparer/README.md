# Resident voice preparation

AGP-06 / M2,M5, ADR 0011, requirements §11.2/12/12.1/14–16. This private Linux
host process consumes `voice_preparation_jobs`; management HTTP remains a separate
Docker service without Docker, admission-file or GPU access. The coordinator uses
Docker CLI only to inspect fixed operator-selected containers and execute their
existing health probes. It never accepts commands, endpoints or paths from users.

`POST /v1/workspaces/{scope}/agents/{profile}/voice-preparation` takes an empty JSON
object, session/Origin/CSRF and draft `If-Match`. It creates an immutable preparation
and deduplicated request. GET with the same version returns missing/queued/preparing/
ready/failed. Owner/editor request; viewers can read. Limits: four pending requests
and ten requests/hour/workspace, three attempts/preparation. Obsolete queued drafts
fail without inference. Ready speech identities are reused. An atomic pack left
behind by a failed metadata commit is verified and imported without another GPU
run; corrupt/conflicting files remain rejected. Requests never publish,
change routing, notify, or start model work inside HTTP.

The runner holds a PostgreSQL session advisory lock and an OS file lock. It persists
an admission journal, closes gateway admission, requires a fresh native drained
acknowledgement, closes all worker gates and obtains current quiescence receipts.
Only TTS reopens. Container identity/start/PID/restart count and gate ownership are
checked throughout synthesis. The existing resident EMA is used with a bounded
call lease/configuration, 512-character chunks, a 90-second progress deadline, validated
20-ms PCM frames, duration bounds, hashes and atomic immutable WAV installation.
There is no second model, torch import, recording, or new media callback work.
Synthesis RPCs additionally have 40-second deadlines: a blocked read can defer the
next progress check by up to that bound. Cleanup has its own 150-second receipt
wait and fails closed if native work cannot be proved finished.

Before normal admission resumes, TTS closes, all workers attest cleanup, all gates
reopen with fresh acknowledgements, and existing managed routes must have current
consumer readiness. A process change, lost fence, failed cleanup or failed readiness
leaves a persistent closed gate/journal. Interrupted work is never reclaimed merely
because a lease timer expired. Jobs are spaced by 60 seconds; idle polling is 10 seconds.

## Installation

1. Apply migrations using private migration credentials. Reapply `grant_management`
   for the HTTP role; it can insert only request columns, never job status/assets.
2. Create a dedicated nonowner/noninheriting database login; provision it using
   `python -m alojan.voice_worker --grant-role <role>` with migration credentials.
   It cannot authenticate users, read provider/Telegram ciphertext, publish or bind.
   Cross-workspace reads are limited to the queue and routing readiness metadata;
   phone digits are not granted. Store its DSN in a private `worker.env`.
3. Configure private JSON with `control_directory`, `asset_store`, `tts_endpoint`
   (`127.0.0.1:15072`), `node_id`, and maps `containers`/`state_files` for gateway,
   TTS, ASR and agent. Paths/names come from deployment, never HTTP. TTS must use a
   distinct file, e.g. `/run/alojan-worker-admission/tts-state`; ASR/agent may share
   `state`. Mount directories read-only in voice containers. Initialize files only
   in a controlled, acknowledged maintenance window. Existing shared-gate deployments
   require a drained TTS reconfiguration before enabling this worker.
4. `uv sync --frozen --project services/voice-preparer` installs the independently
   locked CPU-only runtime. PYTHONPATH includes app-api, voice-contracts, generated/python.
   For deployment, copy those source packages and this runtime manifest/lock into a
   private content-addressed release directory and use its paths in the unit.
5. Install the example `infra/systemd/alojan-voice-preparer.service` as a user unit,
   substituting pinned release paths and private configuration paths. It caps CPU
   at 0.5 core, memory at 256 MiB and tasks at 64, and intentionally does not restart
   automatically after an error. The host account needs existing Docker access;
   never grant this to the management container. No listening port is added.
6. Validate `--once` with the restricted role, then start/enable the service. Check
   its health through systemd and the private journal; queued requests can persist
   while it is stopped. Keep systemd alerts/operator recovery in operational checks.

## Recovery and rollback

Stop the coordinator before other operator voice maintenance; all operators must
honor its lock/journal. Do not delete a journal, mark a job ready or reopen admission
to bypass missing evidence. After interruption, fence gateway and all workers,
inspect current process identities and require fresh native drain and all-worker
quiescence. Restart the gateway in persistently drained mode if a fresh native
receipt cannot be obtained; restart a worker only when cleanup cannot be proved.
Recheck all identities/receipts after any restart. Verify ordinary health, current
managed release readiness and gate-open acknowledgements before reopening gateway.
Only after recording recovery evidence may the operator archive the journal and
mark the affected `preparing` job `failed/interrupted`; user retry remains bounded.

Rollback by stopping the idle coordinator and restoring the previous management/
web images. The additive job table may remain. Retain the TTS state-file mapping
and open-state evidence; reverting it without coordinating the gates is unsafe.
Do not restore an old database backup over new calls or account changes.

## Acceptance limits

The private preview is enabled; this is single-host preparation with brief admission
pauses, not concurrent background synthesis or zero-downtime preparation. A failed
worker is visible in systemd and may require operator recovery. Public signup abuse
budgets, generalized multi-node coordination, full matched call-latency/load/soak
acceptance and new handset audio-quality acceptance are separate work. The existing
carrier acceptance and capacity-one limit remain unchanged.
