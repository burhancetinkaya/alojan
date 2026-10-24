# GPT-OSS 120B reasoning and speech-tool follow-up

Tasks: M4-01 / M5-03. Requirements: DEC-11, §7.4/9.1–3, US-02/05/06/08.

The owner reaffirmed use of 120B, authorized more reasoning with response
preparation below three seconds, and restored Linux access. This follow-up uses
the primary Ubuntu host. It is a development-line change, not full G3 or security
acceptance. A remaining adversarial early-close failure is explicitly open.

## Implementation

- Keep `openai/gpt-oss-120b`, OpenRouter Responses streaming and Cerebras-only
  routing, without model/provider fallback. Select medium reasoning, temperature
  0.2 and 4096 output tokens per model step, including reasoning. Retain the
  existing five-step, cancellation and turn-deadline bounds.
- Require an actual tool choice at every step. Add local `respond(text)` for
  validated speech that keeps listening; `finish_call` owns closing and
  `take_note` owns persistence. The model still chooses intent and wording.
- Never send free-form model text, commentary or reasoning to TTS, including
  tool-shaped JSON mislabeled as final text. Wait for complete speech arguments;
  validate nonempty text, at most 400 characters and one question. Missing speech
  fails closed through the existing error path. This is format validation, not
  proof of language quality or correct intent.
- Supply existing-note state explicitly, clarify indirect callback requests,
  and reuse the durable result for an identical note. Unsaved identical state
  still performs IO. No readback confirmation or automatic save-and-close.
- Keep the tool-free structured summary, audio/protobuf boundary, external-write
  policy, disabled recording/tracing/storage and three-second closing pause.

[Cerebras reasoning documentation](https://inference-docs.cerebras.ai/capabilities/reasoning)
confirms low/medium/high effort and that reasoning consumes the output budget.
[Tool-calling documentation](https://inference-docs.cerebras.ai/capabilities/tool-use)
supports required selection and strict schemas. These are capability references;
the measurements below are from our actual provider path.

## Exploration and rejected variants

The prior prompt-only candidate was faster but unreliable. Medium/2048 initially
passed 18/18 checks, then 16/18 on repetition and 13/16 additional cases. High/2048
passed 16/18 and 17/18, including output-budget exhaustion. High/4096 without the
speech-tool change passed 17/18 and 14/16; some first phrases exceeded 3.5 seconds.
Changing to Chat Completions did not remove missing closing calls, so it was not
adopted. Temperature zero and application-state instructions alone did not solve
the problem either.

Required speech tools substantially improved normal dialogue. Later runs exposed
an unnecessary identical-note write (fixed with durable-result reuse), a polite
callback interpreted as availability (prompt clarified), and occasional budget
exhaustion on a rule-override request. Explicit refusal guidance reduced but did
not eliminate boundary failures. High reasoning with the final tool arrangement
passed 18/18 ordinary checks but still exhausted its budget on an adversarial
case; its maximum first phrase was 2.983 seconds. More reasoning is not a general
fix for that remaining issue. Retain the faster medium configuration.

These are exploratory tuning runs, not a randomized model-quality study.
Repeated cases were reused during development. Private scripts, synthetic
outputs, rejected results and prompt snapshots remain under ignored `.local/`.
No private caller transcript or credential was added to source control.

## Final Linux evidence

With the selected settings and current prompt: **37/38 automatic checks passed**
(18/18 primary cases, 15/16 additional cases, 4/4 separate boundary probes).
The one failure was a rule-override/false-delivery request that unnecessarily
ended the call. It was not counted as a success. The same input was correctly
refused in another run, so consistency remains unresolved. No new external action
or false delivery was performed. Speech inspection found no raw reasoning in the
validated replies. This does not establish general prompt-injection immunity.

Across these 38 cases, 36 used the real API; two used existing local clarification
guards. Mean first usable phrase was approximately 0.96 seconds and maximum was
2.304 seconds, including the incorrect early-close response in the timing sample.
Synthetic in-memory note storage was used for this comparison; it is not handset
latency, and a fast failed dialogue does not satisfy quality acceptance.

Before the final refusal wording, 59/60 checks passed at the selected settings;
the failed adversarial request exhausted its output budget after 2.316 seconds.
Earlier improvements are not silently relabeled as final-version passes.

Linux regression: **87 passed in 6.57 seconds** in the isolated candidate and
**87 passed in 7.68 seconds** after targeted synchronization into the primary
checkout, including isolated PostgreSQL,
SDK wire settings, required selection after rejected tools, cancellation while
speech arguments are pending, suppression of mislabeled reasoning/tool JSON,
closing validation and durable-note deduplication. The first isolated test launch
accidentally imported the live Luna package; another lacked the test-helper path.
Both were corrected with an explicit candidate package/test path. Their failed
runs remain recorded and are not candidate passes.

Real API plus isolated PostgreSQL and structured summary passed. A two-turn
synthetic PCMA loopback with resident CUDA Whisper/EMA also passed: first audio
after endpointing was **1459 ms** and **639 ms**, with ASR finalization 138/116 ms
and first TTS chunks 8/8 ms. The second phrase of turn one started at 2679 ms
because the preceding 1200 ms phrase was playing. Do not count that as first
response latency. The note remained unconfirmed; closing and post-call summary
completed. No carrier call, human recording or claimed 50-turn G3 acceptance.

## Rollout and remaining work

The owner's selected 120B development configuration was activated on loopback
agent port 15073 after confirming the gateway had only its startup event and no
call activity. Only the agent worker was gracefully restarted. ASR, EMA and the
gateway retained their existing processes and arguments; all three gRPC services
reported SERVING afterward. The exact prior live Luna backend/timing files and
agent log are retained under ignored `.local/rollbacks/gptoss-reasoning-20261024`.
No native source or binary was changed by this task. Linux byte-compilation,
Ruff check/format and diff-whitespace checks passed. No push.

Open: adversarial premature closing/budget exhaustion, human carrier validation,
representative 50+ turn latency/quality sampling and soak testing. The earlier
zero-critical-failure adoption gate is **not marked passed**. Choosing the owner's
requested development model is not a claim that these acceptance gates are met.
