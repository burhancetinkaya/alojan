# macOS foundation validation

Date: 2026-10-09 (Europe/Istanbul). Branch: codex/agentic-bootstrap.
Owner authorized starting macOS development; Ubuntu checks are deferred.

## Environment

macOS 26.6.2 arm64, Apple Clang 21.0.0, uv 0.11.9, managed Python 3.12.13,
CMake 3.31.6, PJSIP 2.16, Docker Desktop 4.91.0 / Engine 29.8.0 / Compose 5.5.1.
PJSIP archive hash and dependency pins are in DEPENDENCIES.md and uv.lock.

## Executed checks

- Pinned PJSIP native configure/build/install: passed; sources/install remain ignored in .local.
- CMake configure/build: passed with C++20 and compiler warnings enabled.
- Real UDP loopback SIP/RTP: PCMA and PCMU calls each received paced WAV audio and sent non-silent input to the gateway meter; CANCEL before answer, session reuse, remote BYE and busy admission passed.
- PostgreSQL Compose start/health and migration: passed on a dedicated project container.
- Database integration: repeat migration, checksum rejection, failed-DDL rollback, duplicate note/outbox transaction rollback, orphan rejection and HTTP live/ready semantics passed. Tests isolate schemas without truncating application data.
- Python contract tests: binary PCM serialization, core field numbers and streaming descriptors passed.
- CTest: invalid-port rejection passed.
- Ruff lint/format and clang-format checks: passed.

A failing health test exposed lost connection options; corrected it to preserve the test schema while setting a transaction-local query timeout. Reran database checks after the fix.

## Limits and remaining tasks

This is a local transport/foundation slice, not completion of M0/M1. No ASR/TTS/agent inference, AI spoken greeting, caller identity parser, production readiness, packet impairment or two-call concurrent isolation has been validated. Native contracts and RTP inactivity are covered by the follow-ups below. No microphone or private audio was captured. Tests generate synthetic tones, which do not satisfy AI identity/fallback speech acceptance.

Linux CI is configured but not run remotely. Ubuntu/CUDA/Netgsm/iOS tests remain not run. The gateway is loopback-only and its dependency build omits TLS/device capture/video. Do not expose it as a trunk endpoint. DB readiness explicitly does not claim voice readiness. Deployment roles/container hardening and license approval are still pending.

Local random DB credentials are stored only in ignored .local/dev.env with mode 0600. No real credentials are in source. The dedicated PostgreSQL volume contains only local development/test data. No push, PR publication or merge occurred.

## M1 lifecycle follow-up

Continued on codex/agentic-bootstrap because transport timeout/cleanup belongs to
its existing M1 scope. No merge or new branch was needed.

Added a configurable inbound RTP timeout (default 10 seconds), using PJSIP receive
packet statistics rather than PCM callbacks, which may deliver generated silence.
The check runs in the call event loop, outside the media callback; non-active media
and unconfirmed dialogs do not trigger this timeout. Maximum call duration remains
a separate bound. Ending events record a non-sensitive reason.

Executed: native rebuild, Ruff, clang-format, and the full local SIP suite:
**9 passed in 26.43 seconds**. New scenarios cover no inbound RTP, release/reuse
after timeout, silent RTP activity followed by packet loss, maximum duration before
WAV completion, and shutdown both with and without a BYE response.

The earlier missing-inactivity limitation is superseded by these results. Packet
impairment, concurrent two-call isolation, caller identity, gateway-to-inference integration and the
full G1-local gate remain open. No Ubuntu/GPU/carrier tests or publication ran.


## M0-04 native transport follow-up

Completed the local contract task on the same branch. Native gRPC 1.78.0 and its
pinned dependency revisions build locally using C++20. Generated C++ and Python
bindings are present; regeneration reproduced all six source files byte-for-byte.
The build script installs into `.local/grpc` and does not modify system packages.
The initial application compilation caught a namespace alias collision with a
protobuf header; the probe now uses a distinct contract namespace alias.

Added shared PCM validation and an explicitly test-only Python gRPC peer. A native
C++ probe verifies synthetic binary PCM in both directions, three-frame streaming,
half-close finalization, a 100 ms deadline against a delayed response, cancellation
while the server is waiting for input, idempotent cancellation and stale generation
rejection. Python tests cover invalid PCM, fixed stream identity/format/sequence,
call isolation, bounded synthesis queues, producer cleanup, mandatory deadlines
and generation reuse. A slow-consumer failure during development showed that the
producer must be stopped before waiting for gRPC to deliver terminal status; the
peer now does so. Buffered transport frames still require receiver-side generation
filtering in the future gateway integration.

Executed checks:

- Native gRPC source build/install and application configure/build: passed.
- Transport suite: **24 passed in 2.86 seconds**.
- Full suite after rerun: **42 passed in 237.25 seconds**, no skipped tests
  (9 SIP, 4 database, 5 protobuf compatibility, 24 gRPC/PCM tests).
- CTest: **1/1 passed**.
- Six-file binding regeneration, Ruff lint/format, clang-format, shell syntax,
  Compose validation and whitespace checks: passed.
- Codebase graph refreshed after source changes.

The first full run had **41 passed, 1 failed in 969.08 seconds**: the PCMU SIP test
received 79 packets against its 100-packet minimum. Host load was unusually high
when inspected (load average above 200); this is context, not a proven root cause.
Both codec cases then passed independently (**2 passed in 10.68 seconds**), followed
by the full passing run above. No packet threshold or SIP implementation was changed
to obtain a pass. Host scheduling sensitivity remains a limitation of local timing
tests; these elapsed times are not voice latency benchmarks.

M0-04 is locally complete at the transport-contract boundary. The test peer echoes
synthetic audio, performs no inference and is not connected to SIP media. Production
ASR/TTS/agent entry points, cancellation fan-out, model readiness, separate database
roles, deployment containers, clang-tidy, remaining G1-local scenarios and remote CI
remain open. Ubuntu/GPU/Netgsm/iOS checks remain unexecuted. No push, PR publication,
merge, project-license adoption or public port exposure occurred.
