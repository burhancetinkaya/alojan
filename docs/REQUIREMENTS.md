# Technical requirements

This is the maintained implementation baseline extracted from the supplied product brief on 2026-10-09. The source document was removed from this repository at the owner's request; it is not needed to implement the project. Section numbers, DEC-01–15 and US-01–09 remain stable for task references. These are requirements, not claims of implemented or externally verified functionality.

## 1. Product

A personal, self-hosted Turkish phone assistant answers Netgsm 0850 calls, including calls forwarded from the owner's Turkcell line, identifies itself as AI, collects a message without readback confirmation (ADR 0006), and sends the owner a post-call summary. ADR 0011 extends scope to authenticated workspace users creating their own number-specific voice agents, instructions, model/runtime settings, configured catalog tools and post-call actions through a protected frontend/API. Kübra/Burhan and Berkcan/Serkan are initial examples using the same EMA voice. Telegram is the first action; MCP connections and typed HTTP webhooks are planned extensions. This is an accepted design, not implemented multi-user runtime support. The owner-selected architecture target remains 50 simultaneous calls across configurable servers (ADR 0009). The current Linux host target is `max_calls=5`; full capacity requires measured acceptance and is not current runtime readiness. iOS Focus-assisted forwarding is device/carrier dependent. Hosted voice orchestration (including Vapi, Retell, Bland or LiveKit Agents) is excluded; low-level libraries and standalone models are allowed.

## 2. Scope and fixed decisions

| ID | Baseline |
|---|---|
| DEC-01 | Primary development/build/test on the owner’s Ubuntu GPU server; macOS editing/optional checks; separate production and carrier acceptance (ADR 0003) |
| DEC-02 | Self-hosted ASR/TTS; current development host RTX 4080, 16 GB VRAM with configurable five-call target; horizontally provisioned 50-call architecture with per-server admission limits (ADR 0009); hardware capacity requires validation |
| DEC-03 | Docker Compose with NVIDIA Container Toolkit |
| DEC-04 | C++20 and PJSIP/PJSUA2 for SIP/RTP; license review required |
| DEC-05 | Netgsm 0850 IP-directed SIP trunk through office public IPv4/NAT |
| DEC-06 | Owner-controlled Turkcell forwarding and cancellation; no unattended USSD guarantee |
| DEC-07 | C++ conversation control, VAD/turn decisions, jitter/playout, interruption, state, cancellation and echo policy |
| DEC-08 | Configurable CUDA ASR: faster-whisper large-v3-turbo by default; optional Nemotron 3.5 under ADR 0008; application-managed partial transcription |
| DEC-09 | canberkkkkkk/ema-lightning, Turkish single voice, stream(), lightning() warm-up; no cloning |
| DEC-10 | Silero ONNX VAD and Smart Turn v3.2, CPU inference |
| DEC-11 | Python OpenAI Agents SDK, Responses streaming, native tools and MCP boundary; ADR 0011 selects per-agent model/provider/runtime settings from a validated catalog. Initial entry remains OpenRouter `openai/gpt-oss-120b` on Cerebras (ADR 0005); new entries require compatibility/quality/speed validation |
| DEC-12 | C++/Python gRPC streaming with binary audio, cancellation, deadlines and backpressure |
| DEC-13 | PostgreSQL for calls, dialogue, summaries, actions and telemetry |
| DEC-14 | Cloudflare Tunnel for protected HTTP(S) management only, never SIP/RTP |
| DEC-15 | Explicit AI identity, no unapproved commitments/writes, recording off by default |

P0 includes SIP answer/termination, bidirectional G.711, automatic operator-provided caller ID, partial/final Turkish ASR with errors/retry, workspace-scoped number-selected agents with instructions and configured tools (ADR 0011), take_note/finish_call, streaming TTS, dynamic turns and barge-in, PostgreSQL records, post-call summary and durable notification, health/secrets/logs/tests/setup, and a real Netgsm call through NAT. ADR 0011 selects configured deterministic post-call actions: Telegram first, typed HTTP requests later, separate from model-selected conversational tools. Scoped self-service configuration/API and isolation are required foundations; the frontend and MCP/HTTP delivery are staged in AGP-01–09.

P1 includes a protected dashboard (call list/detail, transcript, summary/actions, filters, latency distributions), contact matching/greeting, assisted iOS forwarding/status, notification and profile/configuration improvements, and offline quality evaluation with consented samples.

Outside v1: voice cloning, emotional voice control, live human transfer, outbound campaigns, IVR designer, call-center platform, automatic meeting confirmation, live Outlook/Teams/Jira/Contacts integrations, public agent marketplace, billing and scaling beyond the planned 50-call deployment, guaranteed no-touch DND forwarding, browser WebRTC phone, and hosted voice-agent platforms. Historical two-call tests prove isolation only. ADR 0009 adds a 50-call architecture target, per-server configurable hard limits and busy rejection when capacity is exhausted; five/50-call production capacity must be validated separately.

## 3. Success metrics

Targets are measured goals, not SLAs: turn-end to first RTP playout P50 <1000 ms and P95 <1800 ms across 50+ Turkish turns; valid barge-in stop <250 ms; premature turn cutoff <2%; false barge-in <3%. Also prove successful SIP transactions, intelligible two-way audio, ASR/TTS readiness without OOM in 16 GB, direct/forwarded caller identity comparison, and consistent call/transcript/summary/action correlation. Use labeled pause/noise sets, packet timestamps, DB correlation and resource/soak measurements. Sent audio only estimates what the caller heard. Do not claim platform parity without evidence.

## 4. Acceptance criteria

| ID | Required behavior |
|---|---|
| US-01 | Inbound INVITE, RINGING → CONNECTED, explicit AI greeting, correct 200/ACK/BYE, controlled failure |
| US-02 | Collect available name, subject, message and requested callback; clarify only unclear content; save without readback, acknowledge naturally, allow further requests and close three seconds after a contextual farewell when the caller is done (ADR 0007) |
| US-03 | Evaluate From, trusted P-Asserted-Identity, Diversion and History-Info; store E.164 and redacted source metadata; unknown number with withheld/anonymous reason preserved; verify forwarded CLI live |
| US-04 | Incomplete sentences with 500–1000 ms pauses must not end from VAD alone; combine acoustic/context evidence and log reasons |
| US-05 | Valid interruption flushes playback, cancels LLM/TTS and invalidates generation_id; old audio never resumes; context contains only aligned sent speech |
| US-06 | VAD plus echo/backchannel heuristics avoid noise/short acknowledgments causing false interrupts; clarify politely when uncertain |
| US-07 | Persist call, utterances, requested actions and finalized summary; notify name/number if available, reason and callback need; retry through durable outbox |
| US-08 | Start with function_tool; provide a Streamable HTTP MCP adapter boundary; caller identity never authorizes tools; external writes require owner approval |
| US-09 | Document and test assisted Shortcuts/forwarding enable, status and disable; do not assume automatic USSD (P1/external) |

Owner prioritization, 2026-10-27 (ADR 0011): further post-call summary semantic/wording
quality improvement is deferred and does not block the current private rollout.
Summary generation/persistence and action security remain required. Known semantic
failures stay recorded; deferral is not quality acceptance. Live conversation quality
and performance requirements are unchanged.

Owner-approved shared response experience, 2026-10-27 (ADR 0014): any agent may
enable one release-bound waiting statement while an authorized operation is slow.
The runtime owns timing and interruption; waiting never counts as a final answer
or note acknowledgment. Jev is an optional platform adviser with English instructions
and original-language input; it cannot authorize tools or replace the primary model.
Owner-approved activation on 2026-10-27 defaults this adviser on for published
conversational MCP-tool agents, with an operator-wide off switch. Agents without
selected published MCP tools do not dispatch adviser requests. Recent call context
is bounded and receipt-backed as specified in ADR 0014.
Existing useful-answer latency and audio-quality gates remain unchanged. Dynamic
text/TTS and fast routing require the plan's separate performance/quality gates.

## 5. Architecture and audio path

[ADR 0001](ADR/0001-architecture.md) records service boundaries. SIP/RTP → G.711 decode → mono PCM 8 kHz → resample to 16 kHz for VAD/ASR as needed → agent text → TTS PCM → negotiated G.711 → timed RTP. Never move audio through HTTP webhooks. Each call owns CallSession, conversation_id, generation_id, cancel tokens and bounded input/output queues. Keep inference models loaded across calls.

## 6. SIP/RTP

Use PJSUA2 callbacks and an inbound endpoint; REGISTER only if the actual carrier product requires it. Handle provisional responses, INVITE, 200/ACK, BYE, CANCEL, OPTIONS when needed and RTP inactivity timeout. The owner-selected carrier profile (2026-10-23) sends 180 Ringing and waits at least 3000 ms before answering; cancellation during ringing must prevent a later answer. Termination stops call workers and releases resources idempotently.

Negotiate PCMA/PCMU at 8 kHz mono with 20 ms frames using a codec registry. Preserve separate receive/transmit paths, RTP sequence/timestamps, pacing, adaptive jitter buffering, late drops and RTCP statistics where available. Reuse low-level PJMEDIA facilities.

[Network preparation](NETWORK_NETGSM.md) defines public address/Contact/Via/SDP, DNAT, configurable media ports and provider allowlists. Record provider prefix configuration (source brief examples: caller prefix 0, called prefix +90), not universal defaults. Make header precedence and operator trust configurable; canonicalize Turkish numbers to +90 and never trust From alone.

Log redacted signaling, correlation IDs, endpoint, transitions, codec, packet count, jitter/loss. On unavailable agent dependencies play a short versioned fallback such as “Şu anda mesaj alamıyorum” and close, rather than keeping a silent connection.

## 7. Conversation engine

### 7.1 State and threading

```text
NEW → RINGING → CONNECTED → GREETING_PLAYING → LISTENING
LISTENING → POSSIBLE_END_OF_TURN → TRANSCRIBING_FINAL → THINKING
THINKING → SPEAKING → LISTENING
SPEAKING + valid_interrupt → INTERRUPTING → LISTENING
conversation completion → SUMMARIZING → FINISHED
any active state → FAILING → DISCONNECTED
```

Serialize state changes in a per-call event loop; media IO uses a separate real-time thread. DB/logging/network/inference must not block media callbacks. Post-call summarization must not keep the caller connected; signaling cleanup and analysis lifecycle are separate as recorded in ADR 0001.

### 7.2 Initial configurable thresholds

| Setting | Initial profile; requires calibration |
|---|---|
| RTP frame | 20 ms |
| VAD speech threshold | 0.50 |
| Pre-roll/pad | 200 ms |
| Silence candidate | 250 ms |
| Fast response window | 350–500 ms |
| Incomplete-turn maximum wait | 1200–2000 ms |
| Barge-in speech candidate | 150–250 ms |
| Silent caller reminder | Once at 7 seconds, then timeout policy |

Combine VAD silence, Smart Turn completion probability, partial transcript and last agent question. Use risk-based adaptive waiting, with more patience for open-ended answers than yes/no turns; do not implement silence duration as the sole hard cutoff.

### 7.3 Interruption and playback

Always monitor inbound speech while speaking. Use outbound reference correlation, VAD, duration and lexical/semantic backchannel classification; do not assume perfect AEC. Valid interruption stops new output, flushes queues, cancels generators and drops stale generations. Track sent_audio_ms and aligned text; never insert unsent generated text into conversation history. A brief “evet/hı hı” may be recorded without interruption. Log why, VAD/detector confidence, canceled_generation, played_ms and false_interrupt_candidate with privacy-safe metadata.

### 7.4 Streaming

Partial ASR may run speculatively, but no response audio precedes a final turn decision. Buffer LLM deltas at natural Turkish phrase/sentence boundaries for TTS; do not synthesize isolated tokens. Convert and pace GPU chunks to 20 ms RTP in real time.

Owner-selected waiting feedback (2026-10-23): use quiet instrumental music instead
of the spoken waiting phrase while the first response is pending. Start only after
the final turn decision and a short delay; stop for response audio, valid interruption,
failure or hangup. Keep music out of transcript, confirmation and substantive
response-latency metrics. Music must not delay a ready response.

## 8. Speech services

### 8.1 ASR

Default to faster-whisper large-v3-turbo on CUDA with compute_type=float16. ADR 0008 authorizes an optional pinned Nemotron 3.5 backend selected by configuration; change the live default only after comparative quality and service validation. Smaller models require a recorded decision supported by VRAM/WER evidence. Decode mono 16 kHz input using rolling/chunk partial hypotheses and finalization; this is not native incremental token streaming. Evaluate names, Turkish mobile numbers, dates and times; optional lexicon/prompts may help proper names. Keep VAD, transcription and completion detection distinct. Owner-configured exact multiword spelling aliases may normalize known terms without modifying numeric tokens or single-word acknowledgments. Keep vocabulary private; do not enable decoder/denoising changes that regress entity accuracy or latency in the available evaluation.

### 8.2 TTS

Pin code and model revisions for canberkkkkkk/ema-lightning. Construct one EMA instance per worker, call lightning() once for warm-up/compilation, and stream mono float32 chunks. The source baseline lists sample rates 8000/16000/24000/48000; verify against the pinned version and compare direct 8 kHz with 24/48 kHz resampling. Turkish only, single voice, no cloning/emotion controls. Test text normalization and foreign-word pronunciation. Version AI-generated greeting/fallback WAVs with provenance; bound inference queues and concurrent contexts.

## 9. Agent and tools

### 9.1 Runtime

ADR 0011 changes the target to per-agent catalog model/provider/runtime selection;
the paragraph below records the current implemented default and its acceptance
limits. Agent releases must pin their own validated settings before activation.

Use KubraPhoneAgent (renamed under ADR 0006) with OpenRouter `openai/gpt-oss-120b` on Cerebras, Responses API and Runner.run_streamed under [ADR 0005](ADR/0005-openrouter-agent.md). Verify account access and SDK/model settings before activation. The owner-authorized reasoning follow-up selects medium reasoning, temperature 0.2 and a bounded 4096-token model-step budget, including reasoning. Omit verbosity and retain concise speech bounds. The owner's below-three-second response-preparation target does not replace §3's endpoint-to-RTP goals. No silent model or provider substitution. SDK handles text/tools/context, never audio transport. Require actual tool selection; only validated respond/finish_call speech reaches TTS, never raw model text or reasoning. Isolate context per call with token limits and truncation. Activate only after comparative response-speed and dialogue-quality validation.

### 9.2 Behavior

Introduce the selected profile explicitly as its represented person’s AI assistant in the opening (ADR 0010): Kübra for Burhan Bey, Berkcan for Serkan Bey; never impersonate the owner. Ask name and purpose concisely. Do not ask for an already available phone number; optionally request a callback number if unknown. Under ADR 0006, save a usable message without reading it back or asking for confirmation; retain confirmed=false. Under ADR 0007, storage returns a result to the conversational agent instead of forcing a fixed acknowledgement and hangup. The selected assistant chooses a natural acknowledgement and any relevant follow-up, then a contextual farewell when the caller is done. Under the owner natural-closing refinement, do not repeat an already delivered acknowledgement of an unchanged note in that farewell. Track completed speech against the emitted note version; interrupted acknowledgements and later corrections remain distinct. Follow the researched conduct rules in AGENT_CONDUCT.md: concrete empathy, plain language, targeted clarification, contextual corrections and truthful next steps. Identify the product before offering further help for a product problem. These are adapted service practices, not a certification claim. Answer AI-identity questions directly; redirect harmless off-topic conversation warmly. Preserve independent requests in the complete current note, and omit volunteered credentials from generated notes and replies (this does not imply raw-transcript redaction). A new request after goodbye keeps the call open; a later final goodbye still closes it. Known content-free status/closing turns cannot rewrite durable notes. Malformed model/tool output triggers clarification without requesting hangup. Close three seconds after final farewell playback, with a short media-drain allowance. Never disclose private calendar/documents or make unapproved meetings, messages or commercial/legal/financial commitments. Treat caller/tool content as untrusted. For immediate danger give general guidance to contact appropriate emergency services or nearby help, without making critical decisions or unreliable promises. Under the owner follow-ups to ADR 0007, the selected assistant uses a senior executive-assistant manner: take ownership of concrete product problems/questions as requests for the represented person, save before acknowledgement, and ask only for essential missing details. Do not redirect to an unspecified support team. After handling the request and essential details, ask “Başka yardımcı olabileceğim bir konu var mı?” once per call, including after an informational answer. Track completed playback; corrections and additional requests must not reset this state. Explicit goodbye/refusal/hangup requests bypass the invitation. Thanks after a handled request and delivered invitation can complete the call; thanks while an essential question remains unanswered require targeted clarification and continued listening. Unclear speech also requires clarification; do not close merely because clarification failed. Preserve existing call resource/deadline bounds. Run analysis after the call.

The existing Kübra profile’s owner-approved greeting is “Merhaba, ben Kübra. Burhan Bey’in yapay zekâ asistanıyım. Size nasıl yardımcı olabilirim?” When asked about availability or speaking to the owner, explain that he is unavailable and may be in a meeting. If the reason for calling is unknown, follow with a polite open question, for example “Burhan Bey şu anda müsait değil, bir toplantıda olabilir. Hangi konuda görüşmek istemiştiniz?” Do not ask the reason again when it was already supplied. This is an owner-configured response, not calendar knowledge. An already supplied message or callback request takes priority over the availability response. Automated notification implementation remains pending under ADR 0010; the closing phrase is not evidence of delivery. The Berkcan profile requires its own approved Serkan-specific greeting and availability wording before activation; do not inherit Burhan’s personal availability claims.

### 9.3 Tools

- take_note(caller_name?, caller_number?, subject, message, confirmed: bool) → note_id; idempotent on call_id + note_version. Current policy accepts only false; successful storage returns to the model for contextual conversation and does not request closing.
- finish_call(reason, confirmed_message?, closing_text?) → decision; request controlled orchestration, not immediate hangup before the closing audio. The caller_finished reason covers declining a message or saying they will call later, without requiring or fabricating a note; the same closing pause applies. closing_text is an optional bounded farewell selected by the agent; questions are rejected. A saved note alone is not a reason to close.
- respond(text) → validated local speech, without requesting hangup or external writes. Require nonempty text, at most 400 characters and one question. A completed tool result is emitted through the existing phrase/playback boundary; partial arguments and free-form model text are not speech. Repeated identical notes with a durable note ID reuse that result rather than repeat database IO.
- Optional P1 get_contact_by_number(number): trusted allowlisted read-only data with minimal model disclosure.
- Future calendar/MCP tools separate reads/writes, owner approval, audit, timeouts and idempotency. A brief natural waiting phrase is optional for pending tools; initial timeout profile 3–5 seconds.

### 9.4 Post-call summary

Validate and persist structured JSON: caller_name, caller_number, subject, summary, requested_action, urgency (low/medium/high), promised_action (none by default), confirmation_status, unresolved_questions, confidence, privacy_flags. Notify summary content only from this finalized object; do not delay caller disconnection for analysis. If finalization fails or exceeds two minutes, label the summary as unavailable without inventing it. Under owner-approved ADR 0010, Telegram also includes the persisted calling number, stored call start/end in Türkiye time and all available final dialogue, with sent-audio accounting for assistant text. Long dialogue uses numbered, resumable messages; no silent transcript truncation.

## 10. Contracts

Preserve these initial field numbers/types when implementing versioned protobuf services:

```proto
syntax = "proto3";
package voice.v1;

message AudioFrame {
  string call_id = 1;
  uint64 sequence = 2;
  int64 captured_at_unix_ms = 3;
  uint32 sample_rate_hz = 4;
  uint32 channels = 5;
  string format = 6;          // pcm_s16le | pcm_f32le
  bytes audio = 7;
  string generation_id = 8;   // used for TTS responses
}
message TurnEvent {
  string call_id = 1;
  string generation_id = 2;
  string type = 3;            // vad_start/turn_end/interrupted/...
  int64 at_unix_ms = 4;
  float confidence = 5;
  string detail_json = 6;
}
message AgentRequest {
  string call_id = 1;
  string generation_id = 2;
  string final_user_text = 3;
  string context_json = 4;
}
message AgentEvent {
  string call_id = 1;
  string generation_id = 2;
  string type = 3;            // text_delta/tool_started/tool_finished/end/error
  string text = 4;
  string detail_json = 5;
}
```

Add StreamRecognize, StreamSynthesize, RunTurn and CancelGeneration plus bounded backpressure/deadline propagation. Every service checks generation_id for stale output. Commit generated bindings with reproducible generation.

Events: call_invited, call_answered, rtp_started, vad_speech_started, vad_candidate_silence, turn_detector_decision, asr_partial, asr_final, agent_started, llm_first_token, tool_started, tool_finished, tts_first_chunk, rtp_playback_started, barge_in, agent_cancelled, call_disconnected, postcall_summary_completed, notification_sent, error.

Protected REST: GET /health/live, GET /health/ready, GET /v1/calls, GET /v1/calls/{id}, GET /v1/calls/{id}/events, GET /v1/metrics, POST /v1/internal/notification/retry (authenticated owner only). External HTTP access is Cloudflare Access restricted. REST/CLI/logs suffice for MVP; dashboard is P1.

## 11. Persistence

| Table | Fields |
|---|---|
| `calls` | `id UUID`, `sip_call_id`, `direction`, `status`, `from_number_e164 nullable`, `from_number_source`, `to_number_e164`, `redirecting_number nullable`, `started_at`, `answered_at`, `ended_at`, `duration_ms`, `codec`, `hangup_reason`, `failure_code` |
| `utterances` | `id`, `call_id`, `speaker caller/assistant`, `text`, `is_final`, `confirmed`, `audio_sent_start_ms`, `audio_sent_end_ms`, `source_generation_id`, `created_at` |
| `call_events` | `id`, `call_id`, `event_type`, `timestamp`, `generation_id`, `duration_ms`, `value`, `metadata_jsonb` (PII scrubbed) |
| `call_summaries` | `call_id`, `caller_name`, `subject`, `summary`, `urgency`, `requested_action`, `confirmation_status`, `json_schema_version`, `created_at` |
| `action_items` | `id`, `call_id`, `type`, `description`, `status pending/approved/done`, `owner_approved_at nullable` |
| `notes` | `id`, `call_id`, `note_version`, `text`, `confirmed`, `created_at`; idempotency unique key |
| `notification_outbox` | `id`, `call_id`, `target`, `payload_jsonb`, `retry_count`, `next_attempt_at`, `delivered_at`, `last_error`, `failed_at`, `provider_message_id` |

Unique (call_id, note_version) enforces note idempotency. Raw audio is off by default; opt-in recording needs separate disclosure, encrypted storage and retention policy. Transcript 30 days and metadata 90 days are configurable initial defaults requiring owner/privacy review. Restrict/encrypt backups and exclude secrets/full numbers/transcripts from logs; DB access is separately authorized.

### 11.1 Number-scoped profile and delivery configuration (ADR 0010, extended by ADR 0011)

The global model/budget ownership below describes migration 0003's delivered
foundation. Section 11.2 supersedes it for the target architecture: agent-specific
runtime revisions and zero or multiple configured post-call actions.

The [profile routing design](PROFILE_ROUTING_PLAN.md) defines the accepted extension;
implementation is tracked as PROF-01–07. PROF-02 now provides
profile-revision configuration storage and typed `system_settings` for shared
technical settings; runtime consumption and routing remain pending. All previously
identified identity/wording/response-style options belong to profiles; model,
budgets, timeouts and mandatory safety policies belong to system settings.
Safety policies are constrained, not optional per-profile permissions. Number-owner display name and assistant name
must be independently editable through the profile API and future UI, with no
code change or per-profile deployment. Initial names are configuration values.
Publishing a rename updates all identity-bearing speech and greeting assets for
new calls; existing calls/history retain their snapshots. Renaming never changes
scope identity or Telegram destination. Persist recipient scopes, immutable profile
and notification-target revisions, canonical carrier numbers and atomic bindings.
Resolve the trusted called DID before greeting and snapshot the binding/profile/target
on the call. Caller identity, caller speech and model output cannot choose a scope.
Unknown or ambiguous numbers fail closed. Shared EMA/ASR does not imply qualified
concurrent-call capacity.

Management uses authenticated versioned API endpoints with scope checks, optimistic
concurrency, audit and write-only secrets. A later frontend uses that same API.
All identity-bearing prompts, corrective speech, tools and summaries use the frozen
profile. Edits affect new calls; historical ownership and delivery remain unchanged.
Database constraints prevent cross-scope associations. Referenced revisions persist.

Finalize summary and enqueue notification atomically. Dispatch through the call's
pinned bot/chat target using a bounded leased worker. No automatic historical sends.
Revoked targets pause pending delivery. Local idempotency does not guarantee
exactly-once Telegram delivery: uncertain sends enter an explicit unknown state and
require an informed retry. Profile credentials never enter prompts, call snapshots,
logs or ordinary API responses. Record carrier and Telegram acceptance separately.

### 11.2 User-managed agent platform (ADR 0011)

The [platform design](VOICE_AGENT_PLATFORM.md) supersedes administrator-only
configuration and global agent-model settings. Users create agents in authorized
workspaces, verify their DID ownership, write instructions, select fixed catalog
tools and configure per-agent parameters/secrets. Model-visible arguments exclude
fixed configuration and trusted execution context. Instructions guide selection;
only executable policy and grants authorize execution. Caller identity is never
authorization. User-authored executable code is excluded.

Agent releases atomically pin profile/instructions, model/provider/runtime settings,
tool/MCP manifests and configurations, output schemas, action configurations and
prepared speech assets. Changes affect new calls; live revocation still blocks
future tool/action execution. A globally unique verified DID binding prevents
cross-workspace number takeover. API/repository/DB boundaries isolate users,
credentials, calls, tools and background jobs.

Users select an approved model and business behavior per agent. Generation,
context, timing, speech calibration and technical budgets are supplied automatically
by a system-owned immutable engine preset. Users do not tune these parameters.
Platform settings retain infrastructure, capability catalogs and hard safety/resource
ceilings; compatible agents share qualified presets. Resolve effective settings at
publication; reject unsupported combinations without silent fallback. Preserve
migration 0003; copy technical defaults into engine presets and attach preset references to agent
runtime revisions in an additive migration. No live model or behavior changes follow from this design.

MCP connection/authentication/discovery is workspace-scoped, with reviewed tool
subsets and pinned schemas. Catalog tools and MCP writes require explicit standing
or per-invocation owner grants. Credentials never enter prompts; SSRF protections
cover connection/discovery/auth destinations. Required unavailable tools prevent
release readiness; manifest drift cannot silently expand permissions.

Qualified remote schemas must retain the original tool digest and separately pin any
bounded local narrowing in the owner grant/release. Defaults cannot be silently
injected; omission and explicit null retain distinct semantics. Fixed parameters,
combined requests and structured results must validate against the same qualified
bounds. Unsupported constraints fail closed rather than disappearing during normalization.
For supported negotiated MCP versions, an omitted output schema is allowed under an
explicit versioned grant: only bounded JSON-object results are accepted, with no
inferred typed post-call output fields. UUID and explicit-timezone date-time input
constraints must be enforced. Existing grant/release semantics must not change.

A finalized call event deterministically triggers configured post-call adapters,
independently of model tool choice. Telegram is first; HTTP requests use typed
call/summary/declared-output field mapping with explicit missing-value policy,
fixed approved destinations and no executable templates. Unknown delivery states,
idempotency limits, per-action retries, revocation and scoped audit are mandatory.
No automatic historical replay. Separate provider/carrier/Telegram/MCP/webhook
acceptance from local mocks and database checks. AGP-01–09 defines implementation.

## 12. Operations

Owner follow-up (2026-10-25): any management HTTP server is an independent
application in its own Docker service (`management-api`); post-call/background
work runs separately (`action-worker`). Neither shares the voice process or blocks
media callbacks. Netgsm inbound alone is supported; carrier IP/NAT/port/prefix
settings remain private deployment config. No generic operator setup UI is required.
The [performance plan](AGENT_PLATFORM_PERFORMANCE_PLAN.md) is a release gate:
fresh matched baseline, no per-turn HTTP/config lookup, prebuilt release/audio,
bounded background resources, API outage/overload isolation and regression/soak
checks. Per-agent model/workflow changes are measured separately from overhead.


Use Ubuntu LTS, supported NVIDIA driver, Docker Engine/Compose and NVIDIA Container Toolkit. Host driver stays on host; pin compatible CUDA/cuDNN/PyTorch containers. Prefer gateway Linux host networking, private/loopback service access, persistent warm workers and independent ASR/TTS/agent/API/DB/listener readiness.

[ADR 0003](ADR/0003-linux-development.md) makes the owner’s Ubuntu GPU server the primary development/build/test environment. The owner-selected [ADR 0011](ADR/0011-docker-runtime.md) supersedes the native runtime profile: gateway, ASR, TTS, agent, API, PostgreSQL and Telegram run in Compose. Native source builds inside the gateway image; the host provides Docker and NVIDIA drivers. [ADR 0002](ADR/0002-macos-development.md) remains the historical macOS fallback decision. Local SIP/WAV tests do not require CUDA or inference models. Real local SIP/RTP must pass before downstream local development; Ubuntu/GPU/carrier acceptance remains separate. CUDA and real model readiness are required for G3, not the WAV-only G2 test. Explicit inference test services support contract tests but never count as model acceptance.

Restrict initial UDP 5060 and 10000–10100 to confirmed carrier sources; validate public IPv4, NAT/SDP, rate limits and TLS/SRTP availability. Document unencrypted WAN audio risk if unavailable. Prefer Access plus MFA for management. On overload use bounded queues and busy/fallback; on shutdown stop new admission, allow controlled active-call completion and preserve outbox. Benchmark precision/worker adjustments if GPU memory exceeds 16 GB.

### 12.1 Configurable capacity (ADR 0009)

Count ringing and active calls against each server limit. Reserve admission atomically, release it idempotently and return SIP 486 when no eligible server has capacity. The intended current-host configuration is `max_calls=5`; zero drains new admission. Partition deployment quotas to at most 50, preserve call affinity and bounded inference queues, and validate the complete speech/agent/database path at each provisioned capacity. Configuration does not certify GPU or carrier capacity. See [the capacity plan](CALL_CAPACITY_PLAN.md) for infrastructure, overload, recovery and measurement gates.

## 13. Carrier/device feasibility

Validate direct, Turkcell-forwarded and withheld caller identity separately. Assisted Shortcuts for DND on/off must not claim background USSD success. The source supplied unverified activation variants **21*NUMBER# and *21*NUMBER*#, cancellation ##21#, and status *#21#; verify current official operator guidance and the actual line before use. Conditional 61/62/67 forwarding is not equivalent to DND. Never commit a real number inside a command.

## 14. Security and licensing

[Runtime security](SECURITY.md) covers AI disclosure, data protection, approval/audit, trusted trunk identity, injection resistance, private storage and access controls. [License review](LICENSING.md) retains PJSIP dual-license and third-party/model review obligations. No license is adopted by this requirements migration.

## 15. Validation

[Call test plan](CALL_TEST_PLAN.md) owns G0–G7 and EXT-01–08, evidence rules, 30+ synthetic/labeled Turkish scenarios, 50+ timed turns and a 30-minute soak. Unit/contract coverage includes codec vectors/roundtrips, resampling, RTP reorder/loss/jitter/pacing, all session transitions/cleanup, VAD/turn fallback/long silence, stale-generation drops, streamed SDK cancellation, duplicate tools, protobuf compatibility, deadlines/slow consumers, caller identity and summary/outbox behavior. Real recordings require consent and anonymization. Never label missing integrations as passed.

## 16. Delivery

[Implementation plan](PLAN.md) defines M0–M6 and dependencies. M0/local M1 come first; local agent/ASR implementation follows real local SIP/RTP proof without waiting for Netgsm. Ubuntu and carrier gates remain required for production acceptance. Update README, runnable commands, test results and changed assumptions at milestone completion. The owner has authorized Linux server development and testing under ADR 0003; progress is tracked in PLAN.md.

## 17. Layout

README documents the intended service/proto/infra/test layout. Development setup, ADRs, network, security and acceptance records live in docs. Optional turn-inference separation is only justified by measured integration needs. No source implementation is created by this document.

### 17.1 Agent configuration completeness

[CFG-01–18](AGENT_CONFIGURATION_AUDIT.md) defines required coverage for all supported
agent behavior. Each setting must have explicit user/system ownership, a versioned schema, validated defaults,
DB/API/native consumer agreement, effective-runtime visibility and observable
acceptance tests. Production identity/business/timing literals cannot bypass a
published agent release. Preserve protocol constants and mandatory security/resource
ceilings. Reject unsupported options rather than presenting nonfunctional controls.
Performance, quality, correct actions and cost must be measured jointly; no claim
of world-leading performance is established by a configuration redesign.

## 18. Change control

DEC-01–15 and P0/P1 changes need an ADR and owner approval. Performance-driven model/codec/adapter changes need the same fixtures, comparative measurements and rationale. The EXT register in CALL_TEST_PLAN is an external verification backlog, not permission to assume success. The original brief's embedded implementation prompt is intentionally not retained as an executable instruction.


### 11.3 Personal management MCP (ADR 0012)

The owner selected Codex and Claude Code as the required clients. Claude web/Desktop
remote connectors and inbound OAuth are outside this release.

Authenticated users can create expiring, narrowly scoped personal tokens, copy each
secret once, and revoke them. A separate HTTP MCP application exposes the operational
agent workflow, configured connections/tools/grants, preparation/publication/explicit
number activation and scoped call/summary/transcript/delivery queries. Each request
must enforce current account, workspace, role and token permissions. Account login,
password/token issuance, operator-only verification and tool qualification remain
outside the MCP authority. Credential entry and provider consent use a secure
same-user browser handoff; secrets are not returned to the model.

Write retries use durable operation keys committed with their mutations. Preserve
optimistic versions, grant review digests, prepared audio/node readiness and one
active agent per number. Search is bounded and literal; transcript access requires
separate permission and excludes partial/unsent speech. Maintain independent
transport/API/resource limits and existing voice performance gates. The owner
approved `<DEPLOYMENT_HOST>` through Cloudflare Tunnel; public HTTPS and basic real-client discovery now pass. Conversational activation
and matched voice performance remain pending. See MCP-01–06 and the implementation
evidence for status.

### Native password policy — owner clarification, 2026-10-27

AGP-02 / M0,M5, ADR 0011, US-08: registration, password changes and private operator
recovery require 8–128 Unicode characters. Retain adaptive salted hashing, bounded
login work, revocable sessions and password-version invalidation of personal tokens.

### Self-service MCP endpoint registration — owner clarification, 2026-10-27

ADR 0013 / AGP-07/09: workspace owners can add canonical public HTTPS MCP server
addresses without an operator allowlist or prior address approval. Discovery and
execution retain exact-destination credential binding, public-IP DNS pinning, TLS,
redirect rejection, tenant/grant authorization and bounded work. Protocol/schema
compatibility and OAuth issuer registration are distinct from address approval.

### Agent instruction variables — owner clarification, 2026-10-27

AGP-06/09, M4–M5, US-08 and ADR 0011: users can define per-agent literal variables
and reference them as `{{name}}` in agent instructions through UI or management MCP.
Reserved identity/time variables refresh from trusted application state in the
configured IANA timezone. Definitions are versioned, scoped and release-pinned;
old agents retain their instructions. Reject undefined/duplicate/reserved names,
invalid syntax/timezones and expansion over the existing prompt budget. No template
expressions, recursive expansion, external lookup or secret injection is supported.
The media path must not acquire new IO or mutable configuration dependencies.
