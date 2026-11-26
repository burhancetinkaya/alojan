# EMA cuDNN calibration and runtime flags — 2026-10-28

TTS-01 / M2-02, US-01; follow-up to the Pocket decoder autotuner correction.

## Question and mechanism

The owner asked whether disabling autotuning for EMA would also improve latency.
EMA 1.1.2's `lightning()` explicitly enables cuDNN benchmarking before constructing
its CUDA graphs, compares the graph and plain paths, then serves through the captured
graphs. Selecting kernels at initialization differs from Pocket's repeated variable
decoder work. Disabling the flag after capture does not rebuild already selected
graph operations. This is a speed/calibration setting, not a voice-quality control.

## Method

Actual Linux RTX 4080, isolated container using the unchanged serving TTS image
`f70f53561c65d0be3e01f53a0e0e07944ca2bbe0b3b42997335186ec6f22f9fd`.
Two fresh processes built EMA graphs: calibration enabled versus disabled. The
private harness intercepts the upstream Graphs constructor to set the flag before
warm-up/capture, because `lightning()` otherwise always enables it. Both retained
the upstream graph/plain validation and successfully constructed all ten graphs.

Each process synthesized the same three authored Turkish texts from the Pocket
comparison ten times per runtime flag. Runtime True/False order alternated each
repeat. Total: **120 syntheses**. Timing is direct `EmaBackend.stream`, including
its native cleanup; it excludes gRPC framing/transport and is therefore not directly
comparable to the preceding RPC table's absolute numbers. This is a warm microbenchmark,
not caller-perceived latency or a statistical capacity claim.

## Results

Median first-audio / full-generation milliseconds:

| Graph calibration | Runtime flag | Short | Nazli greeting | Answer |
| --- | --- | ---: | ---: | ---: |
| On | On | 4.92 / 5.69 | 5.33 / 7.20 | 5.86 / 10.35 |
| On | Off | 4.94 / 5.63 | 6.05 / 7.28 | 7.54 / 9.57 |
| Off | On | 4.88 / 6.46 | 5.29 / 9.02 | 8.52 / 10.51 |
| Off | Off | 4.91 / 6.61 | 5.28 / 9.00 | 8.44 / 10.65 |

Turning off the runtime flag after calibration showed no consistent improvement.
Calibrating with tuning enabled retained a small total-generation benefit on these
fixtures; disabling it did not reproduce Pocket's large onset improvement. Ten
repeats are insufficient to establish small first-frame differences as stable effects.
Each paired runtime True/False result had an identical PCM SHA-256 within its capture
configuration. Cross-calibration PCM equality and perceptual equivalence were not asserted.

## Decision and limits

Keep EMA's initialization calibration and the separately tested Pocket-only override.
There is no evidence here that globally disabling tuning will improve the current
EMA serving path. No product code, live image/device or routing was changed.
The candidate was removed; live TTS stayed healthy and GPU memory returned to
4090 MiB. Active-call monitoring would abort testing if a call began.

No handset call, subjective quality evaluation, multi-call load, fallback-path sweep
or long soak was performed. Application suites were not repeated because no product
source changed. Private harness and raw results: `.local/ema-autotune`.

Reference: [PyTorch performance tuning guide](https://docs.pytorch.org/tutorials/recipes/recipes/tuning_guide)
describes algorithm-selection benefits for recurring convolution sizes and overhead
for variable shapes. The EMA-specific mechanism above was inspected in pinned 1.1.2.
