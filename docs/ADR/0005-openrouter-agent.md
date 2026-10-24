# ADR 0005: OpenRouter-hosted phone agent

Date: 2026-10-23
Status: Accepted by explicit owner instructions in the M4 continuation.
Amends: DEC-11 provider/model selection only.

## Decision and authorization

The owner requested OpenRouter's OpenAI-compatible API, then explicitly selected
`openai/gpt-6-luna-pro` after the original Luna model was denied by an account
model guardrail. Preserve the OpenAI Agents SDK, `Runner.run_streamed`, Responses
API, `reasoning.effort=none`, low verbosity and the existing native audio boundary.
Use `https://openrouter.ai/api/v1` with `OPENROUTER_API_KEY` in the ignored server
`.local/agent.env`. No fallback to another model/provider endpoint is configured
in Alojan. OpenRouter may perform its own provider routing under account policy.

The owner also chose to start M4 before remaining M3 calibration improvements.
M3's incomplete-turn behavior, silent reminder and latency targets stay open;
this scheduling decision does not mark those acceptance criteria passed.

## Evidence and alternatives

A real Linux Responses streaming request to the selected Pro model completed,
returned text, and accepted the requested settings (one synthetic observation:
3460 ms total). The original `openai/gpt-6-luna` returned HTTP 404 with the explicit
reason `Model blocked by guardrail`; no account guardrail was changed by the agent.
This smoke check is not full tool/dialogue quality or latency acceptance.

Direct OpenAI would violate the owner's provider preference. Silently changing
models would violate DEC-11; the explicit Pro choice authorizes this amendment.

## Consequences

Caller text and minimal call context pass through OpenRouter and its upstream
provider. OpenAI SDK tracing and response storage are disabled in application
requests; this is not a claim about provider-side retention. Keep API keys out
of commands/logs/Git. Terms, provider data policies and redistribution notices
remain review items. No external message/calendar tool is enabled by this change.
The durable notification milestone remains M5.

## 2026-10-24 amendment: owner-selected DeepSeek Flash

Status: Superseded before activation by the GPT-OSS selection below. This records
the earlier accepted owner instruction and its incomplete validation.

For M4-01 / M5-03 and requirements §9.1, the owner requested DeepSeek V4.1 Flash
to reduce response latency. The exact selected OpenRouter ID is
`deepseek/deepseek-v4.1-flash`, replacing the earlier Pro selection above.
Do not substitute the rolling `deepseek-flash` alias or another revision.
Preserve Responses streaming, `reasoning.effort=none`, serial tool execution,
800-token output bounds, per-call isolation, cancellation and disabled storage
and tracing. Omit `verbosity`: it is not advertised in this model's supported
parameters. The existing prompt still requires concise Turkish speech.

The [OpenRouter endpoint catalog](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints)
advertises tools, structured outputs and reasoning controls for this exact ID.
[DeepSeek's thinking-mode documentation](https://api-docs.deepseek.com/guides/thinking_mode/)
documents that Responses `reasoning.effort=none` disables thinking. These are
capability references, not evidence of account access or measured speed.

The first implementation attempt passed 74 local Mac simulated-agent tests and
Ruff checks. SSH to the primary Linux host timed out repeatedly. No source was
deployed, no live process was restarted and no real API benchmark was completed.
The last verified deployed model remains `openai/gpt-6-luna-pro`; its current
health cannot be established while the host is unreachable.

Before activation, run the Linux regression suite, synthetic real-API dialogue
checks (inquiry, note creation/correction, clarification and natural closure),
structured post-call summary validation and the CUDA loopback call. Compare
first-phrase latency with the prior model using the same scenarios and preserve
the last working backend for rollback. Carrier/handset timing remains separate.

## 2026-10-24 amendment: conditional GPT-OSS 120B activation

Status: Accepted for implementation and testing; activation authorized only after
comparative speed and dialogue validation. Owner-authorized Mac real API tests
show faster first text but failed dialogue checks, so activation is held.
Primary-host connectivity also blocks Linux validation; the live model is unchanged.

The owner selected `openai/gpt-oss-120b` through OpenRouter, requested prompt
optimization using internet research, and authorized deployment if faster.
Select Cerebras explicitly (`only=["cerebras"]`, `allow_fallbacks=false`) for both
conversation and summary. Unlike the previous models, GPT-OSS cannot disable
reasoning; use its supported `low` setting. Omit verbosity. Preserve Responses
streaming, SDK handling of tool-step context, strict tools, output bounds,
cancellation, isolation, disabled tracing/storage and existing speech services.

The prompt is reorganized into concise decision rules and aligned Turkish intent
examples without changing ADR 0007 policy. Saving does not close the conversation;
unclear answers get clarification, corrections preserve valid details, and only
caller completion permits a natural farewell. Internal reasoning must stay out of
spoken output; real evaluation found that event filtering alone does not guarantee
this when reasoning arrives as ordinary text. Provider failure remains a failure rather than triggering an
unapproved model/host switch; this trades provider redundancy for a reproducible
Cerebras trial and is a limitation to reassess after real measurements.

See [research, verification and activation gates](../validation/gpt-oss-120b-2026-10-24.md).
77 Mac regression tests passed; real Mac API evidence is now recorded, including
critical behavior failures. Linux/DB/summary/GPU/carrier evidence is still pending.
The last verified live Pro model remains the baseline. No new owner approval is
required once the documented speed/behavior gates pass and an idle window exists.

## 2026-10-24 follow-up: 120B reasoning and a validated speech channel

The owner reaffirmed GPT-OSS 120B and explicitly authorized more reasoning while
keeping response preparation below three seconds. Linux connectivity returned.
The selected implementation retains the exact model, Cerebras-only routing,
Responses streaming and Agents SDK. It uses medium reasoning, temperature 0.2
and a bounded 4096-token budget per model step (including reasoning), with the
existing five-step and turn-deadline limits. This is a measured development
target, not a guarantee of provider latency or a replacement for G3's tighter
endpoint-to-RTP P50/P95 targets.

Increasing reasoning alone did not reliably fix missing closing tools. Add a
local `respond(text)` speech tool and require a tool selection on every model
step, including steps after note storage. `respond` returns validated speech
without ending the call; `finish_call` still owns model-selected closing. This
changes the internal model output channel, not the protobuf/audio contract or
external tool permissions. The model still chooses wording and conversational
intent under ADR 0007. No fixed save-and-hangup rule is introduced.

Only a completed speech tool result is eligible for TTS. Raw text, commentary,
reasoning and tool-shaped JSON outside an actual tool call are never spoken or
executed, even if the provider labels them final text. Missing/invalid speech
fails through existing bounded error handling. Speech arguments are limited to
400 characters and one question; a closing question remains invalid. This bounds
format, not semantic correctness or language quality. Summarization keeps its
tool-free structured output contract.

Make existing-note state explicit in the system instructions and reuse the
durable result for an identical repeated note, avoiding unnecessary DB IO.
Optional contact details, unconfirmed storage, cancellation, isolation, no
external notification and three-second post-playback closing remain unchanged.
See [Linux evaluation and rollout evidence](../validation/gpt-oss-reasoning-2026-10-24.md).
The selected development-line worker is now active after an idle restart, with
the previous live model retained for rollback. This does not mark the recorded
adversarial closing failure, full dialogue acceptance or G3 latency gate passed.
