# ASR spelling and CPU optimization — 2026-10-23

Scope: M2-01 / M5-03, requirements §8.1 and US-02/04/06. The owner requested
better recognition without extra load or latency, and confirmed a product name.
This is a spelling/CPU improvement, not a new acoustic model or full G3 acceptance.

## Selected implementation

- Keep the pinned faster-whisper 1.2.1 large-v3-turbo model, CUDA float16, beam 5,
  timestamp-token decoding, temperature 0 and 440-token bound unchanged.
- Set process-local `OPENBLAS_NUM_THREADS=1` in the ASR launcher, before NumPy
  imports. No global driver, EMA or agent setting changes.
- Load optional exact multiword spelling aliases from ignored `.local/asr.env`.
  Compile one bounded pattern at startup and apply one non-cascading substitution
  after each decode. Three owner-specific aliases are enabled privately. No fuzzy
  matching, number rewriting, single-word substitution or extra inference.
- Preserve native VAD/turn detection, cancellation, generation isolation and
  exact-zero silence handling. Quiet speech is not suppressed by a guessed gate.

The selected aliases were derived from exploratory failures. The evaluation is
not an independent accuracy estimate: 16 EMA-generated utterances, including four
initially held-out utterances subsequently inspected during diagnosis, all use
the same synthetic voice. No real caller recordings or transcripts were added.

## Paired synthetic CUDA evaluation

`tools/benchmark-asr-quality.py` consumes a private hashed synthetic manifest.
Each utterance has five conditions: clean, white noise at 15/5 dB SNR, 50 Hz hum
and approximately -24 dB quiet speech. Speech is passed through G.711 A-law and
resampled to 16 kHz. Three additional controls are digital silence, noise and hum.
Three repetitions, randomized paired order, full generator consumption and
warm-up produce 240 speech decodes / 249 total decodes per profile.

| Metric | Previous launcher/decoder | Baseline with one BLAS thread | Final exact spelling + one BLAS thread |
|---|---:|---:|---:|
| Speech decode P50, ms | 113.69 | 112.18 | 112.33 |
| Speech decode P95, ms | 132.25 | 130.93 | 127.96 |
| Process CPU time, all 249 decodes, s | 333.90 | 27.17 | 27.18 |
| Literal word edits / reference words | 438 / 1950 | 438 / 1950 | 426 / 1950 |
| Required name misses | 24 | 24 | 12 |
| Missing speech outputs | 0 | 0 | 0 |
| Unexpected vocabulary insertions | 0 | 0 | 0 |
| Nonempty outputs on nonspeech controls | 6 / 9 | 6 / 9 | 6 / 9 |

The last two columns are paired in the same run; the previous launcher baseline
is an earlier run of the same fixture workload on the same RTX 4080. The measured
CPU-time reduction is approximately 92%; this is process CPU time in this test,
not a claim of 92% lower whole-server utilization. Wall latency remains comparable.
A separate check of all 249 pairs found zero numeric changes and zero changes
outside the configured exact replacements. Literal edit counts include normal
spoken-number-to-digit formatting, so they are not semantic error rates.

The spelling pass cannot recover a completely misheard product name. Noise/hum
controls still hallucinate stock phrases if forced directly through Whisper;
existing gateway VAD remains necessary. This does not establish noisy-handset
accuracy, broad Turkish WER, concurrent load capacity or 50-turn P95 acceptance.

## Rejected experiments and regression caught

The pinned upstream [transcription implementation](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
was inspected for hotwords, timestamp decoding and context limits. Text-only
beam-5 decoding with contextual vocabulary reduced synthetic median latency by
about 15% and improved names, but a separate real-service phone fixture acquired
extra zeroes. Isolating the flags showed both text-only decoding and model
hotwords could change that number. Neither change is shipped. Short noisy
acknowledgments also echoed contextual hints before a temporary two-second guard;
that experimental hint mechanism and guard were removed entirely.

Greedy decoding inserted hints into nonspeech. A 100 Hz high-pass experiment added
work without a quality gain; stricter confidence/no-speech thresholds did not
remove the noise hallucinations. These changes were also rejected. No denoising
model, spectral filter or second ASR pass was installed.

## Linux service and native media validation

The final real CUDA gRPC validation passed all seven fixtures, all name/date/phone
entity checks, PCM16/float silence checks, pre-start cancellation, active
cancellation and recovery. Active cancellation was 0.60 ms with zero stale buffered
events and recovery on the first attempt. Unpaced total times are diagnostics,
not caller response latency:

| Fixture | Previous service, ms | Final service, ms |
|---|---:|---:|
| Greeting | 524.07 | 465.53 |
| Closing | 464.76 | 459.45 |
| Date/time | 594.19 | 577.00 |
| Phone | 1327.30 | 1304.25 |
| PCM16 silence | 3.12 | 4.68 |
| Float greeting | 450.75 | 452.47 |
| Float silence | 3.58 | 3.52 |

Real loopback SIP/RTP → turn detection → CUDA ASR → EMA → RTP passed both PCMA
and PCMU. Each supplied 356 ASR frames and seven partials, received all 200 TTS
frames, and preserved approximately 20 ms RTP pacing. ASR half-close to first
playout was 140/139 ms, with 1104 ms turn silence. This validator uses a fixed
reply: no OpenRouter agent, carrier or human-listening claim follows from it.

Focused regression checks include invalid/oversized dictionaries, number exclusion,
whole-word boundaries, apostrophe suffixes, no cascading, longest-phrase precedence,
unchanged decoder options and cancellation/admission behavior. One earlier unit
run exposed a client/server cancellation-cleanup race in the test assertion;
bounded polling now waits for the server's existing finally block, while still
asserting native inference remains unfinished. No production cancellation contract
was relaxed. Final validation: 44 Linux pytest cases passed in 3.11 s, Ruff lint/format checks
passed for six Python files, and launcher syntax/diff whitespace checks passed.
The full 255-test baseline suite was not repeated for this focused ASR change.

## Development activation and privacy

The idle development gateway switched to ASR port 15173 after all three worker
health checks. The replaced live ASR on 15172 was stopped after successful startup;
no extra resident worker remains from this change. Existing older rollback workers
were left untouched. ASR GPU allocation remains 1984 MiB; aggregate host allocation
returned to 6626 MiB. The 8965 MiB validation peak included the temporary candidate
alongside the preserved live worker. The final worker has BLAS limit 1 verified in
its environment and 29 process threads (other libraries also use threads).

The gateway executable hash is unchanged:
`bb9d5823635885d38e7df3e96de6cfa0f8d1239278f321d3b6a74c969f7a433e`.
The natural-v2 agent, approved greeting, three-second ring delay and closing pause
remain active. Private rollback artifacts, dictionary, configuration and detailed
synthetic outputs stay under ignored `.local/`; no caller recording was enabled.

Human carrier retest with the product name, a number and short yes/no responses
remains pending. General agent/API latency and production supervision are outside
this change. No Git push or PR publication was performed for this task.
