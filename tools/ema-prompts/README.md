# Offline EMA prompt generation

This isolated Linux x86_64 / Python 3.12 environment generates the two M1-03
announcements with real CUDA inference. It is the owner-authorized offline portion
of M2-02 under [ADR 0004](../../docs/ADR/0004-ema-prompt-validation.md), not a live
TTS server. The root development environment remains independent.

On the authorized Linux server, from `~/ai/alojan`:

```sh
export PATH="$HOME/.local/bin:$PATH"
uv sync --frozen --project tools/ema-prompts
uv run --frozen --project tools/ema-prompts python tools/ema-prompts/generate.py \
  --output-dir .local/ema-prompts-reproduced
```

Use a fresh output directory; generation refuses to overwrite existing files.
The default output is `assets/prompts/tr-v3-ema`. Text comes from that version’s
`.txt` files; `--text-dir` selects a different directory containing `greeting.txt`
and `unavailable.txt`. To generate a new version, prepare its input text separately
and choose a fresh output directory. It does not use the old WAVs, a reference voice,
the microphone, a remote inference endpoint or an API key.

Pins: EMA Lightning 1.1.2 (wheel SHA-256
`821c737587d2db32f83a863abadd455610720d359872f6fb8b08ddd1c9b84840`),
PyTorch 2.6.0+cu124 and all transitive packages in `uv.lock`. Model revision:
`e7c96f2fc0ba843cd0f86e02786655bb56f50df8`; both checkpoint SHA-256 values are
verified before loading. Upstream uses `torch.load(..., weights_only=True)`.

EMA 1.1.2 does not expose a model revision argument. A scoped loader shim supplies
the already downloaded, pinned files to its constructor; no synthesis code is
replaced. Remove this shim when upstream supports revisions directly. Download,
compilation and calibration caches remain under ignored `.local/ema`; the Python
environment stays under ignored `tools/ema-prompts/.venv`.

The generator requires CUDA, creates one EMA instance and calls
`lightning(batch_size=1)` once. This explicit single-request batch avoids a broad
throughput search on the shared server. Compile workers and CPU threads are capped
at four. It checks that the graph validation succeeds and records warm-up warnings;
check these before claiming compiled execution. Host drivers/services are unchanged.

Each text is streamed at 48 kHz for high-quality preview and at 8 kHz for phone
playback, using speed 1.0 and seed 0. Mono float32 chunks are validated for finite
values, non-silence, amplitude and duration, then written as PCM16 with only final
20 ms alignment padding. Resampling and filter flushing use EMA's existing audio
path. No denoiser, custom resampler or volume normalization is added.

The manifest records package/model/device pins, hashes, sample counts, stream
timings, peak amplitude/RMS and PyTorch allocated/reserved peak memory. Those
memory values exclude some driver allocations. Timings cover this two-prompt run,
not service latency percentiles. GPU kernels may differ across software/hardware;
manifest timing fields naturally differ on reproduction. Human listening remains
separate from waveform integrity and SIP transport checks.

Sources and licenses: [EMA code](https://github.com/canberk7/ema-lightning),
[model revision](https://huggingface.co/canberkkkkkk/ema-lightning/tree/e7c96f2fc0ba843cd0f86e02786655bb56f50df8)
(upstream declares Apache-2.0), and
[PyTorch CUDA 12.4 distribution](https://pytorch.org/get-started/previous-versions/).
See [dependency inventory](../../docs/DEPENDENCIES.md) for release limitations.
