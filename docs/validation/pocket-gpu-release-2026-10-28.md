# Pocket CUDA release — 2026-10-28

TTS-01 / M2-02 / US-01/05, ADR 0015, requirements §8.2. The owner authorized
fixing Pocket, testing, reviewing and resolving findings, then deploying to Linux.

## Review and correction

The previously measured fix disables cuDNN autotuning only within each Pocket CUDA
decode and restores the prior value in `finally`. EMA calibration, model revisions,
precision, sampling and the single-synthesis admission limit remain unchanged.
Review covered backend selection, callers, asset identity, cancellation, bounded
queues, worker maintenance, configuration and tests.

One additional failure-path finding was closed: a generator that raises from its
own cleanup can already be closed, so a later `close()` does not prove producer
quiescence. The TTS service now checks the backend's quiescence evidence, rejects
subsequent synthesis after failed cleanup, and reports NOT_SERVING to the existing
supervisor. Regression coverage distinguishes failed cleanup from a recoverable
inference error. Normal Pocket cancellation already drains/joins the pinned upstream
producer; no new cancellation mechanism was necessary.

## Linux validation

- 123 focused tests passed in 25.72 seconds: Pocket audio/voices, TTS,
  configuration, releases, voice jobs, worker maintenance and service resilience.
- Ruff check passed; formatting required no changes. Final diff whitespace check passed.
- Actual final-image GPU RPC acceptance passed for EMA plus all six Pocket voices,
  PCM framing, cancellation/reuse and return to EMA.
- Thirty timed syntheses: three authored synthetic texts, two voices, five repeats.
  First means the first telephone PCM frame received over loopback RPC; total means
  all audio produced, not playback duration or end-to-end telephone response time.

| Voice/text | Median first frame (ms) | Median total generation (ms) |
| --- | ---: | ---: |
| EMA / short | 8.41 | 46.13 |
| EMA / greeting | 8.25 | 32.73 |
| EMA / answer | 9.45 | 42.51 |
| Pocket female 2 / short | 27.15 | 171.80 |
| Pocket female 2 / greeting | 37.79 | 430.44 |
| Pocket female 2 / answer | 31.14 | 434.28 |

The greeting's Pocket first-frame range was 33.93–48.86 ms; its generated audio was
6.38 seconds long. This is a small warm-service sample, not a percentile or load SLA.
Candidate startup took 35.54 seconds. The isolated test watched for live calls and
removed its candidate container afterward. Private evidence is under
`.local/pocket-gpu-release/`; no recordings, credentials or customer transcripts
are included in this record.

## Deployment

At 2026-10-28 00:13:34 +03:00, the coordinated rollout replaced only the serving TTS
image with `sha256:178d03d00b217de63c777d8714c0c9002ae9d92158a3d23f24beb2f8951d22c6`
and selected `--pocket-device cuda`. It held the existing preparation/coordinator
locks, drained the gateway and confirmed worker quiescence before replacement.
Prior configuration and image are retained privately for rollback.

After rollout: TTS/ASR/agent healthy, routes ready, admission open, pinned voice
preparer active, public HTTPS health 200. Phone binding snapshots were unchanged.
The optional operator overlay now selects CUDA; the CLI default remains CPU.
No agent draft, release, number binding, EMA calibration or other serving image was
changed by this rollout. The existing public synthetic preview page remains available.

No new handset/carrier listening test, noisy-room assessment or concurrent-load
qualification was performed. Subjective Pocket voice quality remains separate from
these synthesis correctness and performance checks. Source remains on the feature
branch; no Git push or merge was performed for this rollout.
