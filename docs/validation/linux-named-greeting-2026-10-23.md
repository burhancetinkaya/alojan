# Named EMA greeting — 2026-10-23

Task: M1-03 (M1), with the already authorized offline M2-02 generation under
ADR 0004. Acceptance mapping: US-01, requirements §6 and §8.2 (audible AI
introduction, safe unavailable-dependency closing and interruption).

The owner accepted the v2 EMA voice as clearly intelligible, then requested the
name Burhan Çetinkaya instead of the generic line-owner phrase. The v2 manifest
now records that listening acceptance without changing its audio or text hashes.
The v3 greeting is:

> Merhaba, ben Burhan Çetinkaya’nın yapay zekâ asistanıyım.

The closing text is unchanged. Both v3 prompts were generated on the authorized
Ubuntu RTX 4080 host in `~/ai/alojan`, using the existing isolated EMA environment.
V3 is the gateway default; v1/v2 remain historical fixtures. No caller recording,
reference voice or remote inference service was used.

## CUDA generation

EMA Lightning 1.1.2 / PyTorch 2.6.0+cu124, model revision
`e7c96f2fc0ba843cd0f86e02786655bb56f50df8`, seed 0, speed 1.0, batch size 1.
The generator verified checkpoint checksums and successful lightning graphs.
Warm-up took 17.496 s with no captured warnings; 10 graphs were built.
Peak PyTorch allocated/reserved memory was 8471.5 / 8640.0 MiB, including warm-up.

| Phone output | Duration | First chunk | Total generation |
|---|---|---|---|
| Named greeting | 3.08 s | 12.210 ms | 24.031 ms |
| Unavailable closing | 4.00 s | 4.394 ms | 16.971 ms |

The versioned [manifest](../../assets/prompts/tr-v3-ema/manifest.json) records
waveform/text hashes, 48 kHz previews, package pins and signal integrity metrics.
The closing text is identical to v2, but its regenerated waveform has a different
hash; no byte-for-byte audio equivalence is claimed. Reproduction accepts
`--text-dir` to keep historical texts immutable:

```sh
uv run --frozen --project tools/ema-prompts python tools/ema-prompts/generate.py \
  --text-dir assets/prompts/tr-v3-ema --output-dir .local/named-greeting-reproduced
```

## Validation

| Check | Result |
|---|---|
| Locked Linux native build | Passed |
| CTest | 3 passed, 1.04 s |
| Full pytest with PostgreSQL | 89 passed, 1 warning, 121.62 s; no skips |
| Ruff lint / formatting | Passed; 14 files already formatted |
| clang-format, changed gateway source | Passed |
| Delivered waveform hashes / task diff whitespace | Passed |

The full suite includes 33 real loopback SIP scenarios, 9 admission/identity CLI
checks, 14 prompt/startup checks, 4 database tests, 5 protobuf tests and 24 gRPC
contract tests. Named greeting and closing playout passed for PCMA/PCMU, along with
mid-greeting/mid-closing BYE, ACK gating and missing-file recovery. The known
Python 3.12 `audioop` deprecation warning remains. GPU use returned to 24 MiB after
generation. Source and assets were synchronized to Linux; final checksum comparison
reported no differences.

Code review covered the task diff against an ignored pre-change snapshot, including
the new assets and their provenance. Graph discovery succeeded before the edit;
both refresh attempts failed with `Transport closed`. No new code symbols were
introduced. The graph refresh remains pending; source/test review used the already
located files. An initial direct `cmake` invocation was unavailable in the shell;
the build was rerun using the documented locked `uv run --frozen` toolchain.

Mac is the editing/playback delivery environment only. The new named pronunciation
has not yet received owner listening feedback. V2 acceptance is not a carrier-call
result. Live TTS integration, ASR coexistence and carrier acceptance remain outside
this change; gateway startup still reports `voice_pipeline_ready=0`.

## Subsequent owner acceptance — 2026-10-23

The owner accepted the delivered named greeting and requested the next task.
The v3 manifest now records this local listening acceptance; all audio/text hashes
remain unchanged. See [the M1 development completion report](linux-m1-development-report-2026-10-23.md)
for the consolidated G1 scenario audit and remaining carrier/product acceptance.
