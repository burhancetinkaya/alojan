# ADR 0014: Shared response lifecycle and optional Jev observations

Date: 2026-10-27. Status: design and implementation authorized by the owner;
a temporary supervised Nazlı handset trial was authorized and performed on 2026-10-27.
The previous Kübra binding was restored; full acoustic/performance acceptance remains pending.
Scope: VXP-01–06, AGP-06/07/09, PERF-02/03, M2/M4/M5, US-04/05/06/08.
Extends ADR 0005/0011 and DEC-11 with an optional decision adviser; preserves
DEC-07/09/12, the primary conversational model and workspace authorization.

## Decision

Implement the owner's approved [response experience plan](../VOICE_RESPONSE_EXPERIENCE_PLAN.md)
as shared runtime capability, independent of agent identity and tool names.
The controller observes actual authorized MCP dispatch or durable note persistence.
At most one waiting utterance is eligible per turn, after 1.8 seconds from turn
processing start and at least 300 ms of active operation. Waiting music is not
speech and cannot reset this clock. Recovery turns do not emit waiting speech.

The initial implementation uses one prepared EMA clip selected by the release's
concise/natural preference or optional generic text. Publication binds text,
voice identity and audio digest. Waiting PCM is loaded during call setup and
rendered by the existing native callback, without a TTS request, remote dependency,
allocation or mutex in that callback. An available final response suppresses unsent
waiting speech or preempts it with a 5 ms crossfade inside the first response frame, without
inserting an extra 20 ms frame. Existing cancellation,
lease isolation and generation invalidation remain authoritative.

Waiting has a separate sent-audio receipt and transcript kind. It never satisfies
note acknowledgment, substantive answer metrics or end-of-turn/hangup conditions.
Partial waiting audio has duration but no fabricated transcript alignment.

Jev is an optional bounded OpenRouter Decisions client, not a replacement chat model.
Request `typesafe/jev-1.14`; accept only resolved `typesafe/jev-1.14-20261014`.
Use English platform instructions and unmodified caller-language input. Reuse only
the call's preloaded workspace-owned provider credential. Initially opt-in, the
operator switch now defaults on under the owner's 2026-10-27 deployment request.
Only runtimes with a validated published MCP tool grant dispatch observations;
adding a connection alone or configuring Telegram/post-call actions does not qualify.
An explicit `ALOJAN_JEV_SHADOW=0` disables the adviser.
Shadow observations run in parallel, with no authority over speech,
tools or permissions. No retry, two in-flight requests, a 750 ms deadline, bounded
response/identity state and a per-identity circuit breaker keep failures isolated.

Owner-approved context extension, 2026-10-27: snapshot up to three prior caller-led
turns from the same call's existing model history, capped at 12 messages and 4096
UTF-8 content bytes, separately from the current utterance's 4096-byte limit.
Do not duplicate the current utterance, truncate phrases or retain orphan answers
whose originating question was evicted. Only fully played substantive assistant
phrases enter that history; partial/unsent speech, waiting clips and raw tool
results are excluded. Known suspect ASR is marked unreliable in the copied data.
Treat all dialogue as untrusted state, never platform instructions. With context,
clear follow-ups/corrections may inherit the uniquely resolved request's intent;
unresolved references stay unknown. Empty history preserves the original request
shape and policy. The primary model already receives bounded call history and is
not reduced to this smaller adviser window. No additional database read, inference
request, permission, speech control or per-agent tuning setting is introduced.

## Gated capabilities

Synthetic decision and same-model metadata measurements are allowed by the owner's
request. They do not authorize claiming real audio or carrier performance acceptance.
Dynamic candidate metadata/TTS remains outside the active runtime until full-path
non-regression and GPU isolation are measured. The existing single EMA synthesis
slot cannot guarantee that speculative filler leaves final speech unaffected.
The initial prepared fallback therefore does not consume that slot.
Fast routing remains a separate research gate; no speculative tool-planner race.

## Migration and rollback

Waiting defaults remain off, and omitted draft/manifest fields preserve old release digests.
Jev's managed-runtime default is now on for published MCP-tool agents as described
above; it does not change release digests, tool authorization or number bindings.
Upgrade generated bindings, native gateway, agent service, management API/MCP,
asset preparation and frontend together before enabling a new release. Reapply the
management role's narrow utterance read grant for `source_generation_id`; the API
returns derived `kind`, not the internal identifier. RLS and write denial stay intact.
No database table or schema migration is introduced.

Prepare a new voice pack before publishing an enabled release. Do not mutate an
active call's pinned release. Roll back by binding the prior qualified release;
leave `ALOJAN_JEV_SHADOW=0`. Returning to older binaries requires disabling new
releases first. A mixed-version enabled rollout is unsupported.
