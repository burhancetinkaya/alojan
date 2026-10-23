# ADR 0004: Generate EMA prompts to resolve the G1 listening failure

Date: 2026-10-23 (Europe/Istanbul).
Status: Accepted by the owner's explicit request to install EMA on the GPU server,
regenerate both announcements and present them for listening.

## Decision

The owner found the eSpeak development announcements unintelligible. Record this
as failed human listening acceptance, not a completed G1 gate. Use the already
selected EMA Lightning model (DEC-09) on the authorized Linux host to generate
replacement greeting and unavailable-service prompts. Keep code, weights and
dependencies pinned, with model provenance and separate GPU execution evidence.

This narrowly advances the offline generation portion of M2-02 to fix M1-03,
before G1 closes. It does not authorize marking the gate complete without a new
listening review or starting the full M2–M5 live pipeline. DEC-01–15 and product
scope are unchanged. ADR 0003 still governs the development host and source sync.

## Consequences

Use an isolated project-local Python environment, retaining the existing driver,
host services and CPU development environment. Keep the rejected v1 files for
historical evidence and generate a versioned EMA set. Real CUDA synthesis of two
prompts proves that limited scenario only: full TTS streaming integration, ASR/TTS
coexistence, cancellation, carrier calls and performance acceptance remain open.
