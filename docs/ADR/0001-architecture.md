# ADR 0001: Architecture and staged delivery

Date: 2026-10-09
Status: Baseline; development platform and sequencing superseded by [ADR 0002](0002-macos-development.md). Local implementation has started under the owner-authorized Mac plan.

## Context

Alojan starts as one personal Turkish phone assistant. The broader README vision does not expand MVP scope. The maintained [technical requirements](../REQUIREMENTS.md) is the requirements source; this ADR does not amend DEC-01–15.

## Decision

Use Ubuntu, Docker Compose, C++20/PJSIP for SIP/RTP and conversation control, Python services for faster-whisper, EMA Lightning, and OpenAI Agents SDK, streaming gRPC internally, and PostgreSQL for durable records. Smart Turn and Silero run CPU inference. Cloudflare is for private HTTP management only. No hosted voice orchestration, multi-tenancy, voice cloning, or live transfer in v1.

Develop locally on Mac under ADR 0002; production builds and GPU/carrier acceptance run on Ubuntu. The initial target is one active call; two calls validate isolation, not promised capacity.

Reuse PJSIP/PJMEDIA's low-level SIP, RTP, codec, and jitter capabilities where appropriate. Application-owned orchestration does not require reimplementing protocol primitives. Media callbacks must not block on database, inference, or API operations.

Separate signaling/session termination from post-call processing: a hangup releases media resources promptly; summary and notification work continue durably outside the media callback. Transcript playback accounting describes audio sent, not guaranteed playback at the remote handset.

## Consequences

M0 establishes reproducibility and contracts. M1 proves local SIP/RTP before local AI implementation; real carrier acceptance follows on Ubuntu under ADR 0002. External gate failures are documented blockers, never reasons to claim simulated success. API/model access and performance remain unverified. Preserve DEC-11's requested model identifier until the owner's approved ADR changes it; no silent substitution.

Future architecture or scope changes need a new ADR with alternatives, evidence, migration impact, and owner approval. Licensing remains proposed separately in `../LICENSING.md`.
