# ADR 0015: Selectable Pocket Turkish speech

Date: 2026-10-27. Status: accepted by the owner's explicit request to add Pocket
as a selectable agent TTS and hear a Nazli preview. Amends DEC-09 and ADR 0011's
EMA-only boundary. TTS-01 / M2-02 / AGP-03/06, US-01/02/05, requirements §8.2/11.2.

Keep EMA and historical release identities unchanged. Add six bundled Pocket Turkish
voices, selected through the existing draft `voice` field in UI/API/MCP. Resolve each
voice to an operator-pinned model revision, bind assets and runtime to the same
identity and use release v11 for Pocket. Unknown/unloaded voices fail closed without
falling back to another speaker. Existing releases keep their versions and digests.

Load one optional Pocket model and cache six reference states before service readiness.
Keep the current single admitted synthesis, bounded queues, cancellation/cleanup,
lease and generation checks. Default Pocket to CPU to avoid a second CUDA workload;
measure its actual latency and resource impact before changing this deployment choice.
Convert 24 kHz output to 8 kHz using a fresh stateful anti-aliasing filter per generation.
Management remains a separate HTTP application; no inference runs in its request path.

This slice exposes bundled synthetic voices, not arbitrary voice uploads, cloning
permissions or emotion tuning. Such user interfaces require separate scope. Preparing
Nazli audio does not bind a phone number or change the existing live assistant.

Acceptance: frozen-model integrity, real Linux synthesis/preview, call-local backend
selection, bounded cancellation and slot retention, voice-asset mismatch rejection,
release v11 round trip and EMA rollback, UI persistence, same-worker EMA regression.
Carrier listening and multi-call capacity remain separate from these checks.

2026-10-28 deployment amendment: the owner approved promoting the measured CUDA
correction after regression tests and review. The optional deployment overlay now
selects CUDA on the qualified Linux GPU host; the command-line default remains CPU
for explicit standalone use. Scope cuDNN autotuning suppression to Pocket decoder
calls and preserve EMA calibration. Failed producer cleanup blocks subsequent
synthesis and reports unhealthy status for existing supervisor recovery. No change
to the single-synthesis capacity. See the GPU release validation record.
