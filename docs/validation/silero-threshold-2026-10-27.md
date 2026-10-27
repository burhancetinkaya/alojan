# Silero interruption threshold sweep — 2026-10-27

M3-02/M5-03/VXP-06; US-05/06; ADR 0003/0014. Owner accepted an isolated
0.50/0.60/0.70 interruption-threshold comparison. No live settings changed.

## Decision

Keep the existing threshold. Increasing it did not prevent any tested
background-speaker sustained crossings; some target decisions became later.
This does not establish that threshold tuning never helps other noises. Silero
detects speech, including competing speech; these thresholds do not identify
the intended caller. The noisy-room handset issue remains unresolved.

## Method and provenance

Reused the 34 public/synthetic PCMA/PCMU streams from the
[Hush evaluation](hush-2026-10-27.md): 727.68 seconds, two main voice roles,
quiet and overlapping speech, short normal/quiet interruptions and silence.
No Hush filter was applied. No private audio or external inference was used.
Linux CPU, Python 3.12.3, NumPy 2.5.4, ONNX Runtime 1.31.0, one inference thread;
existing isolated environment and `hush-requirements.lock`, no new dependencies.

- Silero v6.2 ONNX SHA-256:
  `1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3`.
- Fixture manifest SHA-256:
  `dad31c9e7753ae3b0fae450ca872b99852464f02594809ba7bb5b019ef3e7955`.
- Result JSON SHA-256:
  `e5dbf6a4817cfa733037fe5944981c8c5998f5c62cb02495b208fb4384ef6f58`.
- Linux results and probabilities: ignored
  `.local/silero-threshold-eval/results/{results.json,probabilities.npz}`.

Infer once per stream with fresh state, then compare the same probabilities at
all three thresholds. Preserve the gateway's float32 threshold boundary and
512-sample/32 ms cadence. Listening sensitivity is untouched. The offline scorer
keeps 640 ms sustained evidence and resets after at least 160 ms quiet, starting
with empty evidence per scoring window. Every 0.50 score field exactly reproduced
the preceding Hush bypass evaluation across all 34 streams.

## Results

| Outcome | 0.50 | 0.60 | 0.70 |
|---|---:|---:|---:|
| Later background-only false sustained crossings | 20/20 | 20/20 | 20/20 |
| Initial background-only false sustained crossings | 4/4 | 4/4 | 4/4 |
| Quiet clean long target repeats detected | 4/4 | 4/4 | 4/4 |
| Clean short target repeats detected, normal + quiet | 4/4 | 4/4 | 4/4 |
| False crossings in clean gaps + silence controls | 0/14 | 0/14 | 0/14 |
| Maximum added target-window crossing delay vs 0.50 | 0 ms | 32 ms | 64 ms |

All 32 target-repeat windows crossed at all thresholds, but overlapping windows
cannot attribute detection to the caller. Isolated short normal phrases crossed
at 688/688 ms (PCMA/PCMU) for 0.50 and 0.60, and 720/688 ms for 0.70.
Quiet short clean phrases crossed at 720/688 ms at all thresholds. Times are
relative to clip/window start, not annotated speech onset or caller-to-stop latency.
The 500 ms tail did not rescue additional detections in this comparison.

## Verification and limits

Linux sweep completed successfully: 34 streams, all previous baseline fields
matched exactly. Self-checks passed for codec fixtures, inclusive float32
boundaries, just-below-boundary rejection, 640 ms evidence, 128 versus 160 ms quiet
gaps, and invalid thresholds. Linux Ruff check and formatting check passed for all
three changed Python files; Mac Ruff and diff whitespace checks passed. Shared
scoring retains its 0.50 default; Hush's native import is now local to its entry
point so this evaluation does not initialize that library.

This is CPU offline evidence only. ASR-assisted interruption (including the
192 ms minimum evidence), echo rejection, RTP scheduling, cancellation and
sent-audio timing were not replayed. No new GPU, SIP/carrier or handset test;
no live deployment. Counts describe a small controlled set, not production rates.
