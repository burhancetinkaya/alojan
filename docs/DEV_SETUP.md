# Development setup

## Docker runtime

The owner selected the complete [Docker runtime](DOCKER.md) under
[ADR 0011](ADR/0011-docker-runtime.md). Use that guide for the current deployment.
The native commands below remain development and rollback references.

## Historical native foundation

The first local foundation is implemented: native loopback PJSIP gateway, a PostgreSQL
schema/migration runner, API health endpoints, C++/Python protobuf bindings and automated
tests. The default gateway plays a synthetic Turkish AI introduction and unavailable
announcement; it cannot collect messages yet. This is not the complete voice assistant.
See [Linux validation and remaining work](validation/linux-development-2026-10-23.md) and [historical Mac evidence](validation/macos-foundation-2026-10-09.md).

## Primary Linux development workspace

The owner selected the Ubuntu GPU server and `~/ai/alojan` on 2026-10-23.
[ADR 0003](ADR/0003-linux-development.md) records the approval. Build and test new
changes there; the Mac checkout remains available for editing/review and optional
platform checks. This setup is the U0-01/M0-08 foundation, not production acceptance.

Private connection settings are in the Mac checkout's ignored `.local/remote.env`
(mode 0600): `ALOJAN_DEV_SSH` and `ALOJAN_DEV_ROOT`. Existing SSH key authentication
works; no SSH password is stored. The server's `.local/dev.env` contains a separate
random database password, created on the server with mode 0600.

From the Mac repository root, review remote changes before synchronizing. Preserve
independent remote edits by comparing or bringing them back first. The commands
below transfer tracked and nonignored source, including uncommitted work:

```sh
. .local/remote.env
ssh "$ALOJAN_DEV_SSH" 'cd ~/ai/alojan && git status --short --branch'
git ls-files -z --cached --others --exclude-standard > .local/remote-source-files
rsync -ani --from0 --files-from=.local/remote-source-files ./ "$ALOJAN_DEV_SSH:$ALOJAN_DEV_ROOT/"
rsync -a --from0 --files-from=.local/remote-source-files ./ "$ALOJAN_DEV_SSH:$ALOJAN_DEV_ROOT/"
ssh "$ALOJAN_DEV_SSH"
```

Do not add `--delete`: review and remove obsolete source explicitly. Do not transfer
`.git`, `.local`, `.venv`, `build`, `.env`, recordings or graph artifacts. Remote Git
uses the same focused `codex/` branch as the Mac checkout (currently `codex/asr-service`), with uncommitted source preserved.
No push, PR or merge is required to test these changes.

On the server, use the same pinned foundation commands below, starting with:

```sh
cd ~/ai/alojan
export PATH="$HOME/.local/bin:$PATH"
export BUILD_JOBS=8
```

`uv` 0.11.9 is installed per-user in `~/.local/alojan-tools/uv-0.11.9`, exposed
through `~/.local/bin`. Its upstream release archive checksum was verified.
The existing Ubuntu GCC 13.3.0/Python 3.12.3 and project-locked CMake/Ninja are used.
All native dependencies and build outputs are created on Linux, never copied from Mac.

## Run the foundation (Linux primary; macOS optional)

Prerequisites: a C++20 compiler (Xcode Command Line Tools on Mac), make, pkg-config,
curl, tar, git, shasum, uv 0.11.9 and Docker Compose. Commands run from the repository root.
The first build downloads pinned Python tools, PJSIP and gRPC with its dependencies.
The native gRPC build can take several minutes; `BUILD_JOBS` controls parallelism (default 4).
It installs into ignored `.local/grpc`, using C++20 consistently across dependencies. No system package install
or Git hook is performed by these build scripts.

```sh
uv sync --frozen
scripts/build-pjsip.sh
scripts/build-grpc.sh
scripts/generate-proto.sh
uv run cmake --preset local
uv run cmake --build --preset local
```

Create a private `.env` from `.env.example` and replace the password in both fields.
A random per-host development configuration is created in
`.local/dev.env` (permissions 0600); it is ignored by Git. Use that file below, or
substitute your own private environment file. Never reuse the CI test password.

```sh
docker compose --env-file .local/dev.env -f infra/compose.yaml up -d --wait
PYTHONPATH=services/app-api uv run --env-file .local/dev.env python -m alojan.migrate
uv run --env-file .local/dev.env pytest -q --tb=short
uv run ctest --preset local
uv run ruff check .
uv run ruff format --check .
uv run clang-format --dry-run --Werror services/voice-gateway/src/*.cpp services/voice-gateway/src/*.hpp tests/identity/*.cpp tests/audio/*.cpp tests/grpc/contract_probe.cpp tests/gpu/cuda_smoke.cu
scripts/generate-proto.sh
```

SIP tests generate a temporary 8 kHz sine-wave fixture, place real loopback SIP calls,
send/receive G.711 packets and shut down each gateway. No microphone or real caller
recording is used. Database tests use temporary isolated schemas and clean them up.
Without ALOJAN_DATABASE_URL those tests explicitly skip; that is not a DB pass.

`uv run pytest tests/test_grpc.py -q` starts an ephemeral loopback-only Python test
peer and invokes the native `voice-contract-probe`. It checks binary PCM in both
directions, stream finalization, deadline expiry, cancellation/reuse, validation,
call isolation and slow-consumer cleanup. The peer is under `tests/support`; it
echoes bytes and produces synthetic audio, loads no model, and has no production
entry point. See [contract semantics](../proto/README.md). The gateway defaults to
WAV playback; the explicit M2-03 profile below connects SIP media to inference.

From the repository root, run the default dependency-unavailable profile:

```sh
build/local/voice-gateway
```

It plays the versioned Turkish AI introduction followed by the unavailable/closing
announcement, then ends with `reason=dependencies_unavailable`. The full agent
pipeline is not connected, so startup reports `voice_pipeline_ready=0`; there is no
flag to claim model readiness. `--prompt-dir /absolute/path/to/prompts` selects a
directory containing `greeting.wav` and `unavailable.wav`. See
[fixture text, provenance and reproduction](../assets/prompts/tr-v3-ema/README.md).
No fixture generator is needed at runtime.

For a transport-only test with your own non-private mono PCM16 8 kHz WAV:

```sh
build/local/voice-gateway --wav /absolute/path/to/test.wav
```

The gateway listens **only on 127.0.0.1**, SIP UDP 15060 and media starting at 14000.
It accepts one call, rejects overload with 486, plays the supplied WAV, meters incoming
audio without storing it, and closes after playback. `--max-call-seconds` defaults
to 30 seconds from call creation; `--rtp-timeout-ms` defaults to 10000 and accepts
100–300000 ms. After connection, missing inbound RTP ends the call; silent RTP
packets still count as activity. This is a transport timeout, not a conversation
silence/VAD policy. SIGINT/SIGTERM initiates teardown, bounded by a two-second
dialog-drain window before endpoint cleanup. No NAT/public exposure setting is implemented.
Default speech starts only after ACK confirms the call; pre-ACK keepalive/silence
packets may still come from PJMEDIA. Two no-loop single-file PJSIP players
sequence the announcements on the main event loop, with a tested handoff gap of
at most 100 ms. This avoids PJSIP 2.16 playlist read-ahead EOF truncation. On the
final single-file EOF, the existing 150 ms playout drain precedes hangup.
Remote BYE, shutdown, maximum duration and RTP inactivity remain higher-priority
termination conditions. In particular, missing inbound RTP can interrupt an
announcement; silence packets count as activity.

Before binding SIP, the gateway checks RIFF/chunk completeness and opens every file
through PJSIP to verify PCM16 mono 8 kHz, at least 20 ms and at most 30 seconds per
file, and an overall file-size bound of 1 MiB. The default speech profile rejects a
maximum call duration shorter than both files plus answer delay and a one-second
margin. Do not mutate prompt files while serving calls; if a file disappears between
startup and call playback, that call ends with `playback_error` and the gateway
continues accepting calls. `--wav` and `--prompt-dir` cannot be combined.

The default v3 fixtures are generated with EMA on the authorized GPU host. The
owner rejected the old v1 formant fixtures as unintelligible; they remain only for
historical tests. The owner accepted v2 as clearly intelligible and requested a
named greeting. The owner also accepted v3, which introduces Burhan Çetinkaya.
The [native Linux G1 scenario set is complete](validation/linux-m1-development-report-2026-10-23.md);
carrier intelligibility and the full product remain unverified.
For the isolated, pinned offline generator, see
[EMA prompt reproduction](../tools/ema-prompts/README.md). The live TTS service is
not connected to calls; playing generated WAVs does not change pipeline readiness.
A custom `--wav` tone remains only a transport test and ends with `playback_complete`.

The receive port accepts mono PCM16 at 16 kHz in 320-sample / 20 ms frames.
PJMEDIA's conference bridge resamples the negotiated 8 kHz PCMA/PCMU stream with
its large filter (`medConfig.quality = 8`). The SIP/playback clock remains 8 kHz.
The callback counts valid samples and rejects unexpected frame types/sizes without
retaining audio. Closure logs report `input_rate_hz`, `input_frames`, `input_samples`
and `input_bad_frames`; valid frames contribute exactly 320 samples. This prepares
the receive format. The M2-03 scripted profile now connects ASR; VAD remains pending. Streaming filters
have startup delay and a tail; model input finalization remains part of M2.

`ctest --preset local` includes `audio-conversion`: independent G.711 reference
vectors, codeword roundtrips, full PCM16 quantization bounds, 8↔16 kHz duration,
passband/alias rejection, frame-boundary filter tails and per-context isolation.
The real SIP suite checks 16 kHz frame delivery for both codecs with clean and
impaired RTP. See [Linux audio conversion evidence](validation/linux-audio-conversion-2026-10-23.md).

`--test-max-calls 2` explicitly enables two concurrent **test** calls. Omit it for
the default single-call admission limit; values outside 1–2 are rejected. A third
call receives 486. This flag does not change loopback binding or promise production
capacity. Each session owns its playback position, input meter, RTP stream and
cleanup. The SIP suite tests staggered 440/880 Hz playback with different codecs,
a non-silent input versus silence, slot reuse and shutdown with/without BYE replies.

Caller identity is copied into each admitted session and logged with complete number
redaction. No operator source is trusted by default. `--trusted-identity-ip`,
`--identity-precedence` and `--caller-national-prefix` configure the local policy;
see [caller identity behavior and limitations](CALLER_IDENTITY.md). Do not infer
caller authentication or real carrier validation from a normalized number.
`ctest --preset local` includes the C++ identity parser/security test. The SIP suite
also checks real INVITEs with trusted/untrusted PAI, privacy and redirect headers.

At `call_closed`, `rx_packets`, `rx_loss`, `rx_reorder`, `rx_duplicates` and
`rx_jitter_max_us` contain the last active-media RTCP snapshot sampled at 100 ms
intervals, not guaranteed final wire totals. RTCP loss is net loss and duplicates
can offset it. The gateway uses the native PJSUA statistics API because PJSUA2 2.16
incorrectly maps the reorder field to loss. No raw headers or audio enter these logs.

The impairment profile deliberately drops two frames, reorders one pair, duplicates
one frame and delays one frame per 20 after initial stream validation. It also
crosses RTP sequence/timestamp rollover. A separate reorder-only case guards the
statistics regression. These are deterministic inbound loopback impairments, not
WAN quality or perceptual speech measurements. Spectral assertions use standard
library `audioop` under the pinned Python 3.12; replace that test decoder before
moving to Python 3.13, where it is removed.


```sh
PYTHONPATH=services/app-api uv run --env-file .local/dev.env python -m alojan.health
```

Health HTTP binds to 127.0.0.1:18080: `/health/live` checks the process and
`/health/ready` checks DB migration readiness only; `voice_pipeline_ready` stays false.
Stop it with Ctrl-C. Stop project containers without deleting data:

```sh
docker compose --env-file .local/dev.env -f infra/compose.yaml down
```

The GitHub Actions workflow is currently absent, so hosted CI is not configured.
Pre-commit configuration is provided; enabling hooks is optional via
`uv run pre-commit install`. `clang-tidy`, inference and separate production
runtime/migration DB roles remain pending. Dependencies are listed in [DEPENDENCIES.md](DEPENDENCIES.md).

Current branch: `codex/ema-prompts`, preserving the uncommitted bootstrap and Linux setup foundation. The original bootstrap branch `codex/agentic-bootstrap` was created from local `main` at `a59675e9806e6fbe09cb4b8c3725ec89a7a27716`. No push or PR publication is included in this preparation task.

## Agent tools

Ponytail is installed locally through the Codex skill-installer. It becomes discoverable on the next turn; its instructions were also read directly during bootstrap.

| Property | Value |
|---|---|
| Upstream | https://github.com/DietrichGebert/ponytail |
| Skill path | `skills/ponytail` |
| Source revision | `9cc65d03aa2da1db7121b912d03596409ee340b8` |
| Installed location | `~/.codex/skills/ponytail` |
| Level | `full` |
| Installed SKILL.md SHA-256 | `ba68ff26239c3c3b05b2a9a47ee0d9a6b93a69639a2555ec87a5d44bffaf2f0c` |
| License | MIT; tool license does not license Alojan |

To reproduce on a Codex host with the bundled skill-installer:

```sh
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo DietrichGebert/ponytail \
  --path skills/ponytail \
  --ref 9cc65d03aa2da1db7121b912d03596409ee340b8
```

The installer refuses an existing destination; inspect it rather than overwriting. If CODEX_HOME is customized, use that installation's skill-installer location. No repository hook, autonomous runner, or extra plugin is required.

Codebase Memory MCP is available and the source is indexed. Refresh the repository index after structural changes and use its returned project identity for graph queries. Other contributors may use text search if the connector is unavailable; see `../AGENTS.md`.

## macOS development profile

The Mac checkout remains an optional compatibility environment under [ADR 0002](ADR/0002-macos-development.md); primary builds/tests now run on the Linux server under ADR 0003. Keep local credentials in ignored files and private captures outside tracked paths. Verify the branch and working tree before edits. The original product brief is outside the repository. Use REQUIREMENTS.md for the maintained English engineering baseline.

Run the gateway and SIP test peer natively; run Python/gRPC services in uv. Use Docker Compose for PostgreSQL/support services bound to loopback. The current Compose file provides the Mac database profile without NVIDIA or Linux host-network requirements. Ubuntu service containers remain pending. Native Mac clients use loopback-published service ports; container-internal names are not host addresses.

Inspect the actual CPU architecture, compiler, CMake, Python/uv and Docker versions before pinning. Use the required ASR/TTS models on CPU only after compatibility checks. Where unavailable or too slow, explicitly select deterministic test services for local integration. Record model limitations, keep test-profile readiness separate from production readiness, and never silently use stubs or change the production model. Mac CPU latency is diagnostic only.

Linux CPU build/contract CI remains required when M0 establishes it. CUDA, production network behavior and live calls must be revalidated on Ubuntu; no Mac result substitutes for them.

## Ubuntu GPU development profile

Ubuntu access is available. The inspected host runs Ubuntu 24.04.2 x86_64 with
an RTX 4080 (16376 MiB), NVIDIA driver 550.120, CUDA compiler 12.4.131,
Docker 28.1.1 and Compose 2.35.1. NVIDIA Container Toolkit 1.20.1-1 was installed
from signed NVIDIA packages. Existing driver/CUDA/Docker versions were retained.
Only the NVIDIA runtime was registered and Docker configuration reloaded; other
containers retained their IDs and start times. No driver upgrade or host reboot occurred.

The daemon was already running before toolkit installation. Bare `--gpus all`
failed device-driver discovery after reload; use the tested explicit runtime below.
A future planned daemon restart may enable discovery, but is unnecessary for this
workflow and was not performed on this shared host. Configuration reload follows
[Docker's documented runtime reload support](https://docs.docker.com/reference/cli/dockerd/#configuration-reload-behavior);
installation follows [NVIDIA's toolkit guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

Run a real CUDA kernel and verify all 256 results on the host and in an isolated
container (network disabled, read-only executable mount):

```sh
cd ~/ai/alojan
/usr/local/cuda-12.4/bin/nvcc -ccbin g++ -arch=sm_89 tests/gpu/cuda_smoke.cu -o .local/cuda-smoke
.local/cuda-smoke
docker run --rm --network none --runtime=nvidia \
  -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
  -v "$PWD/.local/cuda-smoke:/cuda-smoke:ro" \
  nvidia/cuda@sha256:0f6bfcbf267e65123bcc2287e2153dedfc0f24772fb5ce84afe16ac4b2fada95 \
  /cuda-smoke
```

This optional hardware smoke is separate from CPU tests and requires the inspected
CUDA 12.4 compiler and RTX 4080 architecture (`sm_89`). It is not an inference
benchmark or ASR/EMA coexistence check. Offline EMA prompt generation now has a
separate pinned environment and model revision; full production service images,
readiness, separate runtime/migration roles and Linux container host-network
integration remain pending. The current gateway tests run natively on Linux loopback.

[Network preparation](NETWORK_NETGSM.md) and [call gates](CALL_TEST_PLAN.md) still
govern live tests. No carrier call, NAT/firewall opening or public service exposure
is implied by server access. See the [Linux evidence report](validation/linux-development-2026-10-23.md).

## Native ASR worker (M2-01)

The persistent standard large-v3 worker runs independently on loopback port 15071.
Follow [setup, contract limits and shutdown](../services/asr/README.md). Its isolated
`uv.lock` pins CUDA 12/cuDNN 9 libraries for the existing host driver; runtime
weights are offline and checksummed. Model health is serving only after real
CUDA warm-up. The M2-03 scripted gateway profile now connects this service.

Use `scripts/run-asr.sh` from the project root after the documented preparation.
The launcher limits its own OpenBLAS work to one thread. Optional exact spelling
aliases are loaded from ignored `.local/asr.env` as `ALOJAN_ASR_REPLACEMENTS` JSON;
see the ASR README for bounds and examples. Keep owner vocabulary private and
validate phone/date/short-answer cases before activation. No audio denoiser or
additional inference pass is installed. [Evidence](validation/asr-quality-2026-10-23.md).
The current development worker stays loaded across requests, but no reboot
supervisor is installed. `tests/test_asr.py` runs in the ordinary root environment
with a fake decoder; `tools/validate-asr.py` uses the actual running CUDA worker
and synthetic fixtures. See [measured results](validation/linux-asr-2026-10-23.md).

The input meter ignores empty PJMEDIA `NONE` heartbeat frames emitted while a
conference port is disconnected/muted. Empty or misaligned `AUDIO` frames and
nonempty `NONE` frames still count as bad; normal silent PCM still counts as audio.
The `input-meter` CTest guards these boundaries without a timing-dependent call.

## Persistent EMA worker (M2-02)

M2-02 was developed on `codex/tts-service`; current integration uses
`codex/speech-gateway`. On Linux, install the frozen
`services/tts` environment, verify/download its pinned model with the explicit
model module, then start `scripts/run-tts.sh`. Full commands, bounded streaming
semantics and cancellation limits are in [the TTS guide](../services/tts/README.md).
The worker binds only `127.0.0.1:15072`; standard gRPC health uses
`voice.v1.Synthesis`. ASR remains on `127.0.0.1:15071`. Run at most one EMA process;
the offline prompt generator and resampling calibration also load EMA.

`tools/validate-speech.py` exercises both persistent workers concurrently with
synthetic fixtures; `tools/validate-ema-rates.py` checks the pinned frontend and
8/16/24/48 kHz output separately. Their outputs belong under ignored `.local/`.
No caller recording is enabled. See [M2-02 evidence](validation/linux-tts-2026-10-23.md).
Development workers require restart after source changes and do not yet have
reboot supervision or production container deployment.


## Native SIP speech integration (M2-03)

Current branch: `codex/speech-gateway`. The existing pinned native gRPC library is
now linked into the gateway. No dependency/toolchain upgrade is required.
See [the gateway guide](../services/voice-gateway/README.md) for the explicit
`--speech-test-ms` profile, fixed capture/response semantics and queue/deadline
limits. Default startup remains the accepted WAV fallback profile.

Build with `uv run --frozen cmake --build --preset local -j 4`, then run the
`tests/sip-integration/test_speech.py` fake-inference integration suite. The real
CUDA path is `uv run --frozen python tools/validate-gateway-speech.py --output
.local/gateway-speech-new` with both model workers ready. It uses synthetic audio
only, completes local PCMA/PCMU calls and stores ignored diagnostics. Do not label
this scripted capture window a turn detector, live agent or carrier acceptance.

## Native Netgsm answer test

Branch: `codex/netgsm-answer`, tasks M1-06/M1-07. The owner authorized incoming
live tests after completing the network forwarding. See [carrier setup](NETWORK_NETGSM.md)
for the private environment file and `scripts/run-netgsm.sh`. Internal GPU workers
remain loopback-only. The test gateway uses the existing carrier-restricted router
rules, a concrete LAN bind, public Contact/SDP address and a transport-source check.

Build on Linux as above. `uv run --frozen pytest -q tests/sip-integration/test_carrier.py`
uses synthetic loopback peers and a documentation-only advertised address to check
public Contact/SDP, immediate and three-second answer profiles with greeting in both codecs, source rejection
and unsafe configuration. Actual owner calls are recorded separately in
[the live answer report](validation/netgsm-answer-2026-10-23.md). An existing detached
gateway must be stopped and restarted deliberately after rebuilding; do not
interrupt a connected call. The native process currently has no reboot supervision.

## Native CPU turn detection (M3-01)

Branch `codex/turn-detection` adds an opt-in adaptive single-turn test. It does not
replace the running carrier greeting process. On the primary Linux host:

```sh
uv sync --frozen --project tools/turn-eval
# Reuse the existing locked ASR ONNX Runtime; no GPU model is loaded by this step.
uv run --frozen --project services/asr python scripts/prepare-turn-models.py
uv run --frozen cmake --preset local -DALOJAN_TURN_MODELS=ON
uv run --frozen cmake --build --preset local -j 4
uv run --frozen ctest --preset local
uv run --frozen --project tools/turn-eval python tools/turn-eval/validate.py \
  --output .local/turn-calibration-new
uv run --frozen pytest -q tests/sip-integration/test_turn.py
```

For CPU-only CI/fresh setup, run `prepare-turn-models.py` with the frozen
`tools/turn-eval` environment instead of installing ASR/CUDA. It contains the same
ONNX Runtime 1.31.0. The script verifies six pinned native headers and both model
hashes, then links the installed runtime under ignored `.local/onnxruntime`.
It refuses to overwrite a conflicting runtime link or corrupt model. PJSIP's
existing pinned floating-point Speex/Kiss FFT is reused for Whisper features;
no extra FFT package is installed. Keep the selected Python environment intact
because the native runtime symlink points into it. Builds without this optional
feature still support fixed capture and reject attempts to enable turn models.
Mac model compilation/calibration is unverified.

Start an **updated** ASR worker (new `processed_audio_ms` field) on an unused
loopback port with `scripts/run-asr.sh --port PORT` and pass that port to the
adaptive gateway/validator. Existing workers do not hot-reload source changes.
The real validation used one temporary updated CUDA ASR worker alongside the
resident workers and removed only that temporary worker afterward. Do not launch
a second EMA process. Start with no active test call and preserve other host work.

The calibration compares native features and VAD states against pinned Python
reference interfaces on six synthetic cases. Dynamic int8 Smart Turn can amplify
small FFT differences, so feature error, same-feature inference agreement,
probability drift and threshold decisions are checked separately. This is
numerical calibration, not proof of human Turkish pause accuracy. The model pytest
cases explicitly skip when local model artifacts are absent; a skip is not a pass.
Hosted CI is currently not configured; the local CPU artifacts and calibration
checks must be run using the commands above.

## Native interruption profile (M3-02)

Branch `codex/barge-in` builds on the existing CPU turn-model setup. No new runtime
dependency or protobuf version is introduced. Build on Linux and run:

```sh
uv run --frozen cmake --build --preset local -j 4
uv run --frozen ctest --preset local
uv run --frozen pytest -q tests/sip-integration/test_interruption.py
build/local/voice-gateway --turn-model-dir .local/turn-models --barge-in 1 \
  --asr-port PORT --max-call-seconds 60
```

Replace `PORT` with the updated ASR worker's loopback port; the resident EMA port
remains 15072. This opt-in test listens during generated speech and can stop and
restart the fixed reply after a caller correction. It does not enable an agent.
The default Netgsm process remains on the approved WAV greeting profile. Its
mapped executable can differ from the newly built file; building is not a live
process restart.

For real model validation use `uv run --frozen python tools/validate-interruption.py
--output .local/interruption-new --asr-port PORT`. Use a fresh output directory.
As in M3-01, start at most one temporary updated ASR process when preserving the
old resident worker, wait for readiness and terminate only that temporary process
group afterward. Never start another EMA instance alongside the resident one.
The validator uses pinned synthetic fixtures and writes sanitized metrics; it
makes loopback calls only. Human/carrier acceptance, phrase-level text alignment,
semantic backchannel calibration and the 250 ms onset-to-stop goal remain open.

The later owner-authorized carrier check now uses the explicit launcher profile
`ALOJAN_VOICE_PROFILE=interruption ALOJAN_ASR_PORT=15171 scripts/run-netgsm.sh`.
This replaced the old gateway only while idle, after model health/coverage checks
and a private rollback snapshot. One real PCMA interruption/new-generation path
is owner-confirmed; one incomplete-turn fallback remains calibration evidence.
See [current live profile and rollback](NETWORK_NETGSM.md#owner-authorized-live-interruption-follow-up)
and [live evidence](validation/netgsm-interruption-2026-10-23.md). Do not confuse
this active test mode with full conversational readiness.

## M4 agent development profile

The owner subsequently authorized M4 and selected OpenRouter Pro (ADR 0005).
See [agent setup](../services/agent/README.md) for migrations, private environment
files and the resident loopback agent on port 15073. Current carrier development
uses `ALOJAN_VOICE_PROFILE=agent ALOJAN_ASR_PORT=15173 ALOJAN_AGENT_PORT=15073
scripts/run-netgsm.sh`; EMA remains the single resident worker on 15072.
Port 15173 includes bounded cancellation handoff, exact spelling aliases and the
one-thread BLAS launcher. The replaced live worker on 15172 was stopped after
validation; older rollback workers remain and should be retired after acceptance.

Run focused checks with the frozen root environment and `.local/dev.env`:

```sh
uv run --frozen --env-file .local/dev.env pytest -q tests/test_asr.py \
  tests/test_agent.py tests/test_agent_database.py tests/sip-integration/test_agent_dialogue.py
uv run --frozen --env-file .local/dev.env --env-file .local/agent.env \
  python tools/validate-agent.py
uv run --frozen --env-file .local/dev.env --env-file .local/agent.env \
  python tools/validate-agent-call.py --adaptive --asr-port 15172 \
  --output .local/agent-call-new
```

The first validator uses simulated audio receipts. The second uses synthetic
EMA caller audio in memory, real CPU/CUDA speech, actual API access and an isolated
DB schema. Use a new output directory. Neither makes a carrier call. Keep failed
attempts as evidence; see [M4 results](validation/linux-agent-2026-10-23.md).
Only switch the live listener while idle, after all worker health checks. Merely
copying source does not update already running Python workers or native binaries.

For the performance follow-up, add `tests/test_agent_phrases.py` to the focused
pytest command above. Native agent dialogue tests check per-phrase timing and
waiting classification with explicitly scripted inference. Use the existing real
adaptive validator for CUDA/API evidence; its `sent_history` includes the new
metrics. Definitions and known measurement exclusions are in the
[performance review](validation/performance-review-2026-10-23.md#measurement-contract).

Waiting-music changes also require the native build and `ctest --test-dir
build/local --output-on-failure` (`waiting-music` checks the original loop's level
and seam). Re-run `tests/sip-integration/test_agent_dialogue.py` for both-codec
music/response transition and music interruption. The real adaptive validator now
reports `waiting_music_ms`; music never appears in `sent_history`. Reload both the
agent and native gateway while idle to replace the old spoken waiting feedback.

The Netgsm launcher now selects `assets/prompts/tr-v4-ema`: the approved greeting
with a 400 ms silent RTP lead-in to protect its opening word during connection
startup. Generic loopback defaults remain v3. See [provenance and reproduction](../assets/prompts/tr-v4-ema/README.md).
Run `tests/test_prompts.py` and `tests/sip-integration/test_carrier.py` for the
first-word preservation regression. Restart only the idle gateway after changing
its prompt profile; resident inference workers do not need restarting.

Carrier ringing uses `--answer-delay-ms 3000` in `scripts/run-netgsm.sh`.
The interval starts after 180 Ringing; caller CANCEL must prevent a later 200.
Keep the greeting PCM lead-in separate from this pre-answer interval.
The 120B agent requires `respond`/`finish_call` speech tools and waits for their
complete validated arguments. Raw model text/commentary is never spoken; only
sent phrases enter history. See ADR 0005 and the 120B reasoning validation report
for the active medium-reasoning profile and its remaining boundary-test failure.

The active carrier opening is now `assets/prompts/tr-v5-kubra` (ADR 0006),
with the owner-approved Kübra/Burhan Bey text and unchanged 400 ms lead-in.
ADR 0007 supersedes automatic save-and-close: storage returns to the model for
a natural acknowledgement/follow-up, then a separate contextual farewell.
No readback question is used.
Agent closing waits three seconds plus 150 ms media drain before BYE.
Availability wording is owner-configured and applies only without a supplied
message. Notification delivery remains deferred. See the Kübra validation report.


## M3-01 silence recovery follow-up

Build the native gateway on Linux and upgrade the agent service before restarting
the idle carrier listener. Do not replace an active call. Preserve the previous
binary and agent `service.py`/`models.py` for rollback; ASR and EMA need no restart.
Runtime endpoint CLI flags and their bounds are documented in the
[gateway guide](../services/voice-gateway/README.md#m3-01-silence-recovery-and-runtime-calibration).
The current launcher retains the calibrated defaults; custom flags are for
explicit native calibration profiles until human acceptance.

Run the native CTests, agent/phrase/database tests and these SIP suites:
`test_silence.py`, `test_turn.py`, `test_interruption.py`, `test_agent_dialogue.py`.
Keep CPU/synthetic-service evidence separate from resident CUDA and real handset
checks. No caller recording or new inference model is needed.

## Optional Nemotron comparison (M2-01 / M5-03)

[ADR 0008](ADR/0008-selectable-asr.md) adds `ALOJAN_ASR_BACKEND=whisper|nemotron`
to the existing launcher and private `.local/asr.env`. The default and active
worker remain Whisper: neither tested Nemotron profile improved local Turkish
accuracy. [Worker setup](../services/asr/README.md#optional-nemotron-backend-adr-0008)
documents the separate frozen environment and explicit pinned model download.
[Evaluation instructions](../tools/asr-compare/README.md) keep public/synthetic
speech and detailed results under ignored `.local/`. Model preparation may need
several GB of disk/network; runtime itself does not download weights.

Use an unused loopback port, run comparison profiles sequentially, and stop only
the temporary worker. Copying source or changing the private backend variable
does not switch an already running process. An idle-line restart and successful
quality/lifecycle validation are required for future promotion. The initial
Nemotron adapter repeats cumulative audio for gRPC partials; it does not maintain
incremental caches across partial requests. [Measured limitations](validation/nemotron-asr-2026-10-23.md).

## Latency diagnostics and routing comparison (M4-01 / M5-03)

The default OpenRouter route remains selected. Optional `ALOJAN_AGENT_ROUTING`
values in the private agent environment are `default`, `latency`, `sticky` and
`latency-sticky`; invalid values fail startup. Restart the agent only on an idle
line after validating a configuration change. No new credential is required.

Run the comparison on the Linux development host, with a new ignored output path:

```sh
uv run --frozen --env-file .local/agent.env python tools/benchmark-agent-routing.py \
  --rounds 3 --output .local/routing-comparison.json
uv run --frozen python tools/report-latency.py \
  .local/logs/agent.log .local/logs/netgsm-gateway.log
```

The first command makes paid real API requests using synthetic callers, an
in-memory note store and simulated receipts. Three rounds produce up to 72 turns;
API failures are recorded and do not count as successful fast responses. The
second command is read-only and prints aggregate metrics without caller content
or call identities. Neither command places carrier calls or enables recording.
Details and limits: [routing evidence](validation/latency-routing-2026-10-24.md).

## Synthetic agent dialogue evaluation

The agent README documents `tools/evaluate-agent-dialogue.py`, an explicitly invoked
real-API check using synthetic fixtures and isolated loopback gRPC/in-memory notes.
Use the primary Linux host and private env files. It does not place carrier calls,
write production notes, or exercise CUDA speech. JSON output belongs under ignored
`.local/`; do not commit private transcripts. Nonzero exit indicates failed checks;
manual review of the rubric remains necessary even when automatic checks pass.

## Offline native noise suppression comparison

The owner-authorized M2-01/M5-03 experiment builds WebRTC 2.1, RNNoise v0.2 and
SpeexDSP 1.2.1 privately on Ubuntu. It does not change the gateway or resident
ASR worker. Follow [the pinned build/evaluation instructions](../tools/denoise-compare/README.md).
Use only the existing public/synthetic fixture manifest; keep audio, detailed
transcripts, native binaries and downloaded sources under ignored `.local/`.
See [results and rejected promotion](validation/denoise-2026-10-24.md).

The same evaluator also supports a pinned DTLN CPU follow-up, using the existing
ONNX Runtime through Python/NumPy. See the README's DTLN section for downloads,
model hashes, full/half-strength profiles and the distinction between processing
cost and signal delay. Results: [DTLN evaluation](validation/dtln-2026-10-24.md).


## Isolated endpoint replay

The endpoint scheduling candidate is opt-in and not accepted for deployment.
Regenerate protobuf bindings before building a client/worker pair. Linux checks:

```sh
uv run --frozen pytest -q tests/test_asr.py tests/sip-integration/test_turn.py tests/sip-integration/test_silence.py tests/sip-integration/test_agent_dialogue.py
uv run ctest --preset local
```

`build/local/endpoint-replay-probe MODEL_DIR ASR_PORT TTS_PORT MANIFEST` is a
synthetic test harness using the actual SpeechBridge. Manifest lines contain
`synthetic_case_id hint_0_or_1 expected_end_audio_ms absolute_pcm_path`.
Input is mono 16 kHz little-endian PCM16, at most 25 seconds. Use only synthetic
fixtures and isolated loopback workers; no real caller input belongs in this
manifest or in Git. A fake TTS worker is acceptable for endpoint-only measurements
and must be identified as such. The paired quality failure and private evidence
location are recorded in [the report](validation/endpoint-calibration-2026-10-24.md).

### Live endpoint scheduling switch

For the agent carrier profile, `scripts/run-netgsm.sh` reads
`ALOJAN_TURN_PARTIAL_HINT` from the private carrier environment (default `0`).
The owner-directed 2026-10-24 deployment sets it to `1` on the Linux host. This
requires the compatible gateway and ASR scheduling implementation; it does not
change the LLM or silence thresholds. See
[deployment, rollback and the remaining quality gate](validation/endpoint-calibration-2026-10-24.md).


## Telegram post-call worker

M5-01 setup, private bot pairing, isolated release deployment, retries and rollback
are documented in [TELEGRAM.md](TELEGRAM.md). The additive migration and standalone
worker do not require a gateway, ASR, TTS or live agent restart.
