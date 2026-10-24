# ADR 0011: Run the complete assistant in Docker Compose

Date: 2026-10-24.
Status: Accepted by the owner's explicit request that all services run in Docker.
Tasks: M0-03/06/08, M5-03; US-01/07; requirements sections 12 and 15.

## Decision

Supersede ADR 0003's native **runtime** profile with a Linux Docker Compose profile
for gateway, ASR, TTS, agent, API, PostgreSQL and Telegram. Linux remains the primary
build/test host. Build native gateway dependencies inside its image; never import
host executables or virtual environments into an image. Preserve pinned model and
library selections. This does not authorize publishing images or increasing capacity.

Use the existing PostgreSQL Compose project and data volume. Store credentials as
read-only file mounts, outside the build context. Keep model caches outside images
and retain native processes/configuration as a rollback option during migration.
ASR and TTS receive explicit NVIDIA runtime/device selection. Runtime containers use an
unprivileged UID, no added capabilities and bounded logs. The Linux host driver,
Docker daemon and NVIDIA Container Toolkit remain host prerequisites.

The current gRPC services bind loopback, and SIP relies on the existing host/NAT
mapping. Use host networking for these containers, preserving loopback gRPC and
the carrier-restricted SIP listener. This exposes the host network namespace to
the containers; it is not network isolation. A future bridge-network transition
requires configurable bind/target addresses and new SIP/media acceptance.

## Recovery

`unless-stopped` restarts exited containers and restores running containers after
Docker/host startup. Explicitly stopped services remain stopped. A small in-container
watchdog probes the local worker and exits after repeated unresponsiveness; Compose
health status alone does not restart a stuck process. It forwards shutdown signals,
allows a bounded grace period and kills remaining child processes before exiting.
No Docker socket is mounted inside a container.

Enable stale-call reconciliation only in the supplied single-installation profile:
the gateway hard limit is 120 seconds; an active database row older than 300 seconds
is recovered every 30 seconds. Save a failure marker and recovery event, preserve
dialogue/notes, and atomically enqueue summary work. Recovery time is not actual
hangup time. Historical calls preceding notification activation are not newly sent.
Longer-call or shared-database deployments must change this policy before enabling it.

## Acceptance

Verify image builds, native tests, database recovery, process exit and hang recovery,
CUDA readiness and synthesized speech, retained records/outbox, and a 30-minute
container soak. Keep isolated synthetic checks separate from handset acceptance.
Host reboot testing is separate: this host runs unrelated applications and must
not be rebooted merely to exercise this change.
