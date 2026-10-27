# ADR 0001: Architecture and staged delivery

Date: 2026-10-09
Status: Baseline; development platform and sequencing superseded by [ADR 0002](0002-macos-development.md). Local implementation has started under the owner-authorized Mac plan.

## Context

Alojan started as one personal Turkish phone assistant. [ADR 0010](0010-number-agent-profiles.md) extends the accepted design to centrally administered number-specific profiles and Telegram destinations; implementation remains pending. The broader README vision does not expand MVP scope. The maintained [technical requirements](../REQUIREMENTS.md) is the requirements source; this ADR does not amend DEC-01–15.

## Decision

Use Ubuntu, Docker Compose, C++20/PJSIP for SIP/RTP and conversation control, Python services for faster-whisper, EMA Lightning, and OpenAI Agents SDK, streaming gRPC internally, and PostgreSQL for durable records. Smart Turn and Silero run CPU inference. Cloudflare is for private HTTP management only. No hosted voice orchestration, voice cloning, or live transfer in v1. ADR 0011 now authorizes workspace-scoped self-service agent management; implementation is pending. ADR 0010 adds logical recipient isolation and a protected profile-management API within the existing services.

Develop locally on Mac under ADR 0002; production builds and GPU/carrier acceptance run on Ubuntu. The historical target was one active call; two-call tests validated isolation only. ADR 0009 supersedes the capacity target with configurable per-server limits and a 50-call deployment architecture; runtime acceptance remains separate.

Reuse PJSIP/PJMEDIA's low-level SIP, RTP, codec, and jitter capabilities where appropriate. Application-owned orchestration does not require reimplementing protocol primitives. Media callbacks must not block on database, inference, or API operations.

Separate signaling/session termination from post-call processing: a hangup releases media resources promptly; summary and notification work continue durably outside the media callback. Transcript playback accounting describes audio sent, not guaranteed playback at the remote handset.

## Consequences

M0 establishes reproducibility and contracts. M1 proves local SIP/RTP before local AI implementation; real carrier acceptance follows on Ubuntu under ADR 0002. External gate failures are documented blockers, never reasons to claim simulated success. API/model access and performance remain unverified. Preserve DEC-11's requested model identifier until the owner's approved ADR changes it; no silent substitution.

Future architecture or scope changes need a new ADR with alternatives, evidence, migration impact, and owner approval. Licensing remains proposed separately in `../LICENSING.md`.


## 2026-10-25 extension

[ADR 0011](0011-self-service-voice-agents.md) supersedes the earlier administrator-only
profile architecture. The target now includes authenticated workspaces, user-created
agents, per-agent models/runtime settings, configured catalog tools, future MCP,
and deterministic Telegram/HTTP post-call actions. Existing service/media boundaries
and capacity acceptance gates remain. See the authoritative
[platform design](../VOICE_AGENT_PLATFORM.md).
