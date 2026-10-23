# Agent service (M4)

A private loopback gRPC service uses OpenAI Agents SDK 0.24.0 against OpenRouter's
Responses endpoint, with owner-selected `openai/gpt-6-luna-pro`, reasoning `none`,
low verbosity, no SDK tracing, no stored Responses state and no automatic retries.
The pinned client versions and hashes are in `uv.lock`. See ADR 0005.

Each call owns bounded conversational context (12,000 UTF-8 bytes of recent
complete utterances), at most 16 turns and 16 phrases per turn. SDK runs permit
five tool/model steps, 800 output tokens per step and 4096 output text bytes per
turn. Responses are emitted as short phrase-sized `text_delta` events. Only
completed output-port phrases become assistant context; interrupted phrases keep
an empty text with the measured sent duration. This is sent audio, not proof of
handset playback. The callback never performs RPC/DB/API work.

`take_note` writes only local PostgreSQL notes, idempotently on call/version.
Under owner-approved ADR 0007, Kübra acts as a professional conversational
telephone agent. A successful `take_note` returns the durable result to the model,
which chooses an acknowledgement and an appropriate follow-up. Storage alone
never closes the call. A usable message is saved before optional contact-detail
questions. Further additions update the note, and no readback confirmation is
requested. `confirmed=true` remains rejected.

When the caller is done, `finish_call(reason="caller_finished", closing_text=...)`
emits the model-selected brief farewell and requests closing. Empty/oversized
closings and questions are refused. The gateway drains closing audio and waits
three seconds plus its existing 150 ms media allowance before BYE. Storage failure
cannot announce success. Owner-selected availability wording is not calendar
knowledge and must not preempt an already supplied message. If the purpose is
unknown, follow unavailability with one polite open question about the reason for
calling; never ask the generic reason again when it is already known.
No notification, scheduling or arbitrary external tool is exposed. The separate
MCP adapter is an owner-allowlisted, approval-required Streamable HTTP boundary;
it is not attached to the phone agent or connected to live systems.

The agent emits only response speech. At the owner's request, the native gateway
now provides quiet instrumental waiting music after 800 ms until the first speech
frame is available. Music never enters this service's receipts, context or note
confirmation. It cannot extend the turn deadline.  See [waiting music provenance and behavior](../../assets/waiting/README.md).
Sanitized text-readiness logs remain distinct from handset audio measurements.

`EndCall` creates a durable summary job after gateway teardown starts. A separate
worker validates the summary schema and never upgrades the stored confirmation
status based on model opinion. Failures remain in `summary_jobs` with a sanitized
code; an owner can reset a failed job to `pending` for retry. The caller does not
wait for summary inference. The summary object cannot promise an action.

## Linux run

Install with `uv sync --frozen --project services/agent`. Keep the key in
`.local/agent.env` with permissions 0600; keep the database URL in `.local/dev.env`.
Apply migrations with the existing app API migration command first.

```sh
PYTHONPATH=services/app-api uv run --frozen --env-file .local/dev.env python -m alojan.migrate
PYTHONPATH=services/agent:services/voice-contracts:generated/python \
  uv run --frozen --project services/agent --env-file .local/dev.env \
  --env-file .local/agent.env python -m alojan_agent --port 15073
```

Select `--agent-port 15073` with adaptive turn models and barge-in on the gateway.
A fixed-capture profile is accepted solely for deterministic native integration
checks. Without `--agent-port`, existing speech tests and the live M3 profile
remain unchanged. Health means service/DB configuration, not verified provider
permissions; API and carrier acceptance are separate gates.

## Limits still requiring validation

Linux regression and synthetic actual ASR/EMA/API dialogue checks passed; see
[the evidence](../../docs/validation/linux-agent-2026-10-23.md). The agent profile is
active on the development line. The owner confirmed correct readback but reported
excessive waiting, so carrier latency acceptance remains open. M3's
incomplete-turn fallback and silent-caller reminder remain deferred by the owner;
the agent prompt alone cannot implement ASR retry timing. Call state and cancellation tombstones
are bounded at 128 calls / 4096 generations per process and fail closed at
capacity; restart supervision and lifecycle reclamation remain hardening work.
EndCall delivery is bounded/best effort at the gateway; a gateway crash before
the end RPC leaves an active DB call for later reconciliation. No M5 completion
or production readiness is implied.

## Performance review follow-up

Streaming now accepts sufficiently long comma/semicolon clauses while preserving
common title and numeric boundaries. Ordinary sentence endings remain immediate.
The previous confirmation flow is superseded by ADR 0006. Exact explicit goodbyes
still close locally without saving or confirming a note or calling the model.
Summary input retains recent complete utterances under 12,000 UTF-8 bytes.

See [measurements and remaining review findings](../../docs/validation/performance-review-2026-10-23.md).
`tools/validate-agent-call.py --adaptive --asr-port 15172 --goodbye --output DIR`
checks a synthetic early goodbye without a note. Omit
`--goodbye` for message storage, a chance to add more, and a second-turn natural farewell without confirmation; use the private env
files and a fresh output directory as described above.

A caller who declines a message or says they will call later can exit through
`finish_call(reason="caller_finished", confirmed_message=null)` without a note.
The server returns the selected farewell (or a short compatibility default) and finish decision. Successful standalone
farewell text also triggers finish when it matches the explicit closing set;
partial/error streams, draft commentary and farewell plus follow-up questions
do not use this fallback. Native audio completion and the closing pause still
precede disconnection. This does not authorize or fabricate a message delivery.
