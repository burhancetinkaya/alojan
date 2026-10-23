# ADR 0002: macOS development before Ubuntu acceptance

Date: 2026-10-09
Status: Accepted by the owner in chat (request to update the plan for initial macOS development). Primary development platform superseded by [ADR 0003](0003-linux-development.md) on 2026-10-23; separate carrier/model acceptance is retained.
Supersedes: ADR 0001's development-platform restriction and real-carrier prerequisite for M2–M5 implementation. Amends DEC-01; Ubuntu production and DEC-02–15 remain unchanged.

## Context and decision

The Ubuntu server is currently unavailable. Develop and test locally on macOS, then validate deployment, CUDA and carrier behavior on Ubuntu when access returns. This approval changes the plan; it does not start product implementation or approve publication/licensing.

Run the C++20/PJSIP gateway and local SIP test peer natively on macOS. Run Python/gRPC services natively in the pinned uv environment; run PostgreSQL and other support services in Docker Compose with loopback-published ports. Do not require Linux host networking or NVIDIA dependencies in the Mac profile. Use the same application code and contracts with platform-specific build/configuration only where necessary.

Inspect the Mac CPU architecture and installed toolchain during M0-01. Do not assume Apple Silicon or claim model compatibility before a smoke test. Try the selected ASR/TTS models on CPU where supported; use explicitly selected deterministic test services when a dependency is unavailable or impractically slow. Keep real inference and test-service results/readiness distinct. No silent production fallback or substitution of the required model. MPS optimization is not part of the initial scope.

## Order and evidence

M0 local foundation → M1 local real SIP/RTP (G1) → local M2–M5 development. G1 must use real SIP endpoints and packetized audio; mocked telephony cannot satisfy it. G2 no longer blocks local AI development. A tested contract with explicit inference stubs can unblock downstream implementation, but cannot complete a real-model acceptance criterion.

Track each task's local implementation and Ubuntu/live acceptance separately. G0-local and G1-local can pass on Mac. G0-Ubuntu and G1-Ubuntu must be run later before G2. G2 remains a real Netgsm gate. G3–G7 retain their hardware/carrier/device requirements; local analogues are supporting evidence only. M1 is not fully accepted until carrier tasks pass.

When the server returns, inspect OS/driver/GPU/container support, reproduce frozen builds and migrations on Ubuntu, exercise Linux network settings, rerun SIP integration, then verify real calls, model coexistence and live performance. CPU measurements never establish RTX 4080 latency or VRAM performance. CUDA warm-up is required for production inference but not for a WAV-only G2 test.

## Alternatives and limits

Waiting for Ubuntu would block independent work. Running the gateway natively keeps the Mac SIP/RTP test path simple; support containers still exercise database deployment. This adds a second development platform and later Linux revalidation, without changing the Ubuntu production target. No server, model, API or carrier check is claimed by this ADR.
