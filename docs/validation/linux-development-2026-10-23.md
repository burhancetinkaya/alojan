# Linux development environment validation

Date: 2026-10-23 (Europe/Istanbul). Tasks: U0-01 / M0-08, with M0/M1 foundation
revalidation. Requirements: DEC-01–03, sections 12 and 15–16; US-01/05/07/08 at
the existing transport/database boundary. Authorization: ADR 0003.

Branch: `codex/linux-development`; baseline commit
`a59675e9806e6fbe09cb4b8c3725ec89a7a27716` plus the owner's existing uncommitted
foundation and this setup change. No commit, push, merge or PR was created.

## Environment and isolation

- Ubuntu 24.04.2 LTS x86_64, kernel 6.11.0-19-generic; 20 logical CPUs, 31 GiB RAM.
- Workspace: `~/ai/alojan`, as selected by the owner. The initially created
  `~/Development/alojan` was moved; path-dependent build/virtual-environment outputs
  were recreated in the final location. Source and download cache were preserved.
- GCC 13.3.0; Python 3.12.3; uv 0.11.9; CMake 3.31.6; Ninja 1.11.1.3.
- PJSIP 2.16; gRPC 1.78.0 and exact submodules from the existing build scripts.
- RTX 4080, 16376 MiB VRAM, driver 550.120, existing CUDA compiler 12.4.131.
- Docker 28.1.1; Compose 2.35.1; NVIDIA Container Toolkit packages 1.20.1-1.
- PostgreSQL 17.4 at the existing pinned digest, isolated `alojan-local` Compose
  project/volume and `127.0.0.1:15432`. Server-only random DB credentials are in
  ignored `.local/dev.env`, mode 0600. No Mac secrets were transferred.

NVIDIA installation added exactly four packages; no existing package was upgraded
or removed. Runtime registration used `nvidia-ctk runtime configure --runtime=docker`,
`dockerd --validate` and `systemctl reload docker`. Existing container IDs and start
times matched before/after reload. The driver, daemon process and host were not
restarted. No carrier-facing port, NAT configuration or firewall exception was added.

Build parallelism began at four and was increased to eight after inspecting spare
CPU/RAM on the shared host. The dependency build resumed from completed objects;
the intermediate interruption is not a test failure.

## Executed evidence

| Check | Observed result |
|---|---|
| Existing SSH authentication | Passed without storing the supplied password |
| uv release checksum and `uv sync --frozen` | Passed; Linux virtual environment created from uv.lock |
| PJSIP configure/build/install | Passed in the final workspace |
| gRPC/application configure/build/install | Passed with C++20 and the existing exact dependency pins |
| C++/Python binding regeneration | All 6 source files byte-identical by SHA-256 |
| CTest | 1/1 passed; 0 failed |
| Full pytest suite on Linux | 42 passed in 27.31 seconds; no skips (9 SIP, 4 DB, 5 protobuf, 24 gRPC/PCM) |
| PostgreSQL Compose health and migrations | Passed; `Migrations applied` |
| Database and protobuf tests | 9 passed in 0.80 seconds; no skips |
| Ruff lint/format | Passed; 11 Python files already formatted |
| clang-format (gateway, contract probe and CUDA smoke) | Passed after formatting the new smoke source |
| Compose configuration, shell syntax, pre-commit config, whitespace | Passed |
| Relative documentation links and source graph refresh | Passed |
| GPU enumeration in NVIDIA runtime container | RTX 4080, 16376 MiB, driver 550.120 |
| Native CUDA arithmetic and device-to-host copy | 256/256 exact integer results passed |
| Same executable inside pinned CUDA container | 256/256 exact integer results passed |
| GPU hidden with `CUDA_VISIBLE_DEVICES=` | Correctly failed with no CUDA-capable device; no CPU fallback |

The CUDA smoke source is `tests/gpu/cuda_smoke.cu`. Exact build/run commands are in
DEV_SETUP.md. It launches a real kernel, synchronizes, copies output back and checks
every result. It does not load a speech model or measure production performance.
The diagnostic container has no network and receives only a read-only executable
mount. Its image digest and license-review limitations are in DEPENDENCIES.md.

Bare `docker run --gpus all` initially failed with device-driver capability
discovery after runtime reload. The explicit `--runtime=nvidia` plus
`NVIDIA_VISIBLE_DEVICES=all`/`NVIDIA_DRIVER_CAPABILITIES=compute,utility` path passed
GPU enumeration and actual computation. Use that tested path until a future planned
daemon restart; do not report the failed invocation as a pass.

## Limits and evidence locations

All implemented foundation tests passed. Real UDP loopback coverage includes PCMA
and PCMU bidirectional RTP, playback completion, CANCEL/reuse, remote BYE/busy,
RTP inactivity, silent RTP activity, max-duration and bounded shutdown. Synthetic
tones establish media transport, not the required spoken AI introduction.

G0-Ubuntu and G1-Ubuntu remain partial while the remaining service/deployment and
G1 scenario requirements are unimplemented. Native Linux loopback checks do not
prove container host-network integration or carrier/NAT behavior. Inference test
peers are synthetic and cannot establish ASR, EMA, PyTorch, model coexistence,
latency or VRAM acceptance. G2–G7, real model/API access, Netgsm and iOS acceptance
remain pending. No private audio was recorded.

Private operational logs stay under the server's ignored `.local/logs`, including
PJSIP/gRPC build logs, package-install output and container before/after snapshots.
Connection details are only in the Mac checkout's ignored `.local/remote.env`.
The repository keeps sanitized evidence and an executable hardware smoke, not
credentials, raw captures or unrelated application inventory.
