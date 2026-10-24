# M4-01/02 dialogue quality and acknowledgement repair

## Scope and release decision

Owner-approved implementation of the independently reviewed M4-01/02 plan,
including narrowly scoped M4-03 summary consistency; US-02/05/06/08 and
requirements sections 7/9/11, ADR 0007. Skill Creator was used for every prompt
revision. No scenario-specific date, name, product or correction recognizer was
added. The model remains `openai/gpt-oss-120b`, Cerebras-only, medium reasoning,
temperature 0.2 and 4096 output tokens. No additional normal-path model call,
public protocol, database schema, ASR, TTS or media implementation was introduced.

**Candidate is not approved for rollout.** Deterministic receipt/storage checks
pass, but real-model correction and conversation-quality gates fail. The running
agent was not replaced or restarted. M4 dialogue-quality acceptance remains open.
Do not infer production readiness from a passing unit test or a low response time.

## Implementation

- Prompt and tool descriptions distinguish a complete edited note from a raw
  transcript: preserve independent requests, replace explicitly corrected facts,
  clarify ambiguous references, and maintain natural professional Turkish.
- Private speech-tool intent metadata describes whether accepted speech
  acknowledges a stored note. Actual storage and complete response playback,
  bound to that note's version, establish the acknowledgement. Partial/unsealed
  cancelled groups cannot do so; old receipts cannot acknowledge a newer update.
  The existing phrase recognizer remains defensive/compatible, without new synonyms.
- A whole-response receipt is intentionally conservative: interrupting a question
  after an acknowledgement can leave that acknowledgement unmarked. Model intent
  labels are still fallible; they are not proof of semantic correctness.
- Summary input labels chronological utterances and decodes the durable note.
  Instructions distinguish final caller intent, saved state and uncertainty.
  Existing worker enforcement of confirmation status remains authoritative.
- Failed/cancelled saves retain the prior durable note and version and cannot
  reach a success response. The new regression checks the SDK's wrapped storage
  exception as well as cancellation.
- Evaluation records timing for failed accepted turns as well as successful
  ones, without attaching a preceding generation's timing to a rejected attempt.

## Method

Linux execution used isolated baseline/candidate source snapshots and the existing
locked environment. Live source was not overwritten. Fifty regression/targeted
conversations contain 100 steps; a separate subagent-authored eight-conversation,
25-step set was reserved until candidate freeze. The final comparison alternates
baseline/candidate order across three pairs, using independent conversation state
and identical settings. All inputs are synthetic. The evaluator uses in-memory
notes and simulated completed playback, not a carrier call or durable business write.

Three exploratory candidates were retained privately. A review found an overly
broad quote/negation instruction; this was corrected before final candidate freeze.
The interrupted pre-review candidate run is exploratory, not an acceptance pass.
The completed first baseline run remains comparable because its source, evaluator,
fixtures and settings were unchanged. The unseen set was not used for subsequent
prompt tuning. Once examined, it is no longer unseen for future revisions.

The independent code reviewer found no further runtime defect in the scoped diff.
Independent language review received conversations/results and product constraints,
without the prompt or which A/B variant was the candidate. Keyword checks are only
automated checks, not an estimate of overall conversational accuracy.

## Deterministic and independent review evidence

### Repeated model comparison

Each row contains 125 planned turn checks. Unexpected hangup invalidates later
turns and counts them as failures; those turns do not have a response latency.
First-phrase metrics include emitted responses even when their content fails.
P50 is the median; P95 is the nearest-rank percentile.

| Version / repetition | Passed checks | Emitted first phrases | P50 | P95 | Maximum |
|---|---:|---:|---:|---:|---:|
| Baseline 1 | 117/125 | 125 | 1045 ms | 1708 ms | 3082 ms |
| Candidate 1 | 113/125 | 124 | 1009 ms | 1824 ms | 2415 ms |
| Candidate 2 | 111/125 | 124 | 988 ms | 1662 ms | 2424 ms |
| Baseline 2 | 118/125 | 124 | 1040.5 ms | 1630 ms | 6052 ms |
| Baseline 3 | 112/125 | 123 | 1012 ms | 1915 ms | 3957 ms |
| Candidate 3 | 117/125 | 125 | 1013 ms | 1919 ms | 2680 ms |
| **Baseline pooled** | **347/375** | **372** | **1033.5 ms** | **1724 ms** | **6052 ms** |
| **Candidate pooled** | **341/375** | **373** | **1002 ms** | **1839 ms** | **2680 ms** |

Candidate emitted-response P50 improved by about 3%; P95 increased by 6.7%,
within the planned allowance. None of its emitted first phrases exceeded three
seconds. These conditional timing thresholds do not override two unexecuted
post-hangup turns or the failed meaning gates. No production SLA is established.
This excludes ASR, TTS, real database latency and carrier transport.

All five baseline responses above three seconds are retained: repetition 1,
`quality-independent-days` turn 3 (3082 ms); repetition 2, `weather` turn 1
(3902 ms) and `quality-name` turn 2 (6052 ms); repetition 3, `weather` turn 1
(3957 ms) and `quality-independent-days` turn 3 (3320 ms). Baseline also had two
`quality-repeat` turn-2 RPC failures after five `respond` attempts (2983 and
3065 ms elapsed), plus one unexecuted post-hangup turn. No candidate RPC failure
occurred. Failures were not silently dropped from the check denominator.

Model-step distributions for 0/1/2/3/4/5 calls were respectively
3/173/189/6/0/3 for baseline and 3/177/185/7/1/0 for candidate. The zero-call
entries are the existing local ASR-artifact clarification path. Baseline made
282 `respond`, 194 `take_note` and 107 `finish_call` attempts; candidate made
273/192/106. Repeated speech-tool attempts within a turn were 13 versus 7.
These reveal repair activity, but exact rejection reasons were not instrumented;
do not equate every extra model/tool step with a specific semantic repair.

The `m4-heldout-03` first-turn note-presence assertion is stricter than the
permitted behavior of clarifying the product before saving. It can report a
nonblocking mismatch. Frozen checks were not relaxed after seeing outputs;
independent review distinguishes this from genuine failures. The new fixture
files are `dialogue-quality.json` and `dialogue-quality-heldout.json`, alongside
the two existing dialogue-review files under `tests/fixtures/agent/`.

### Runtime regression and speech integration

The focused Linux suite passed **134 tests in 8.04 seconds**, including storage,
model/tool contracts, isolation, cancellation, timing, phrases and existing
latency reporting. After adding the early-receipt race case, the complete
acknowledgement-specific file passed **7 tests in 0.88 seconds**. Together these
cover 135 distinct deterministic cases; the seven are not additional to all 134.
No skip or simulated inference result is labeled real-model acceptance.

One final **two-turn synthetic PCMA loopback** passed with the candidate agent,
resident CUDA Whisper/EMA workers, real OpenRouter, the existing Linux gateway
binary and an isolated PostgreSQL schema. It saved an unconfirmed note, retained
the second turn, completed farewell audio, closed and persisted a structured
summary. Endpoint-to-first-audio was 1618 ms and 819 ms; ASR finalization was
146 ms and 115 ms. Waiting music total was 660 ms. The first response's second
phrase started later because the first phrase was playing; it is not another
LLM first-response measurement. This is a transport/integration smoke check,
not validation of all semantic cases, carrier listening, a new native build or
a fresh measurement of the three-second post-playback hangup requirement.

Mac Ruff checks, formatting and diff-whitespace checks passed. No Mac inference
or GPU performance result is claimed. The Linux source snapshot was frozen for
final comparisons; real speech tests followed them rather than adding concurrent
API load to the latency measurements.

Final live-source hashes matched the pre-task baseline for `backend.py`,
`models.py` and `service.py`. Resident ASR, TTS and agent health checks all returned
`SERVING`; none was restarted. A scoped credential-pattern scan matched only the
explicit synthetic test API-key literal, and private evidence remained Git-ignored.

The independent language reviewer examined all 58 first-pair conversations with
variant identity hidden and preferred the baseline overall. The candidate was
sometimes clearer when asking about incoherent input, but it did not achieve the
requested experienced-assistant tone consistently. Confirmed issues include:

- Wrong corrected times/dates and lost independent requests, including during
  content-free farewells after a previously correct intermediate note.
- Ambiguous references applied to both items without asking, and actor/action
  reversals in notes. These are meaning failures, not merely awkward wording.
- An added request followed by premature closing, and a separate ignored explicit
  farewell. The once-per-call invitation alone does not establish correct ending.
- A synthetic one-time-code marker persisted in a candidate note. The baseline
  excluded it in that pair. This is a regression even though no real secret was used.
- Repetitive storage announcements and bureaucratic paraphrases. The baseline
  also has unresolved errors, so rejecting the candidate does not certify it.

The reviewer distinguished legitimate implied product-help requests from invented
technical remedies, and historical correction narration from a wrong current fact.
Keyword failures and semantic failures are not interchangeable. The final stored
note must be inspected, including farewell-only turns.

## Summary acceptance

Real OpenRouter summaries were generated three times for each of six synthetic
correction/withdrawal scenarios, through isolated PostgreSQL schemas and the real
summary worker: **13/18 automatic checks passed; five failed**. Independent semantic
review found **four material meaning failures**: a withdrawn date became the date
of an event, and all three ambiguous scheduling examples invented recruitment or
a person instead of retaining an unresolved report/contract reference.

The two counts measure different things. Some automatic failures merely detect
unwanted correction narration, while semantic review identifies meaning errors
that keyword checks miss. Other outputs mixed English into Turkish summaries,
added unnecessary questions, or used ambiguous action fields. All 18 persisted
results remained unconfirmed and promised no external action. Storage consistency
and schema validity therefore passed checks that language quality did not.

## Remaining work

Do not add fixture-specific correction phrases or claim that a longer prompt
solved this class of errors. Further work must establish a more reliable general
way to preserve independent facts and resolve correction targets, with a fresh
unseen evaluation set. The receipt change can be evaluated separately from the
rejected language candidate; it is not automatically authorized for live rollout
by this failed combined evaluation. Carrier listening is still separate.

Private synthetic outputs, frozen hashes, exploratory failures and reviewer
artifacts are under `.local/m4-quality-20261024/` on the development machines.
They are not Git artifacts. No credentials, private transcripts or recordings are
included in this report. No commit, push, PR, notification or carrier call occurred.
