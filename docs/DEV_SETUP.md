# Development setup

## Current state

2026-10-27 activation fix: apply migration 0026 and refresh management/readiness roles
before starting the updated API/agent. Management `ALOJAN_VOICE_NODE_ID` assigns new
publications to the matching node. Current publications and verified active bindings
are discovered in the background; `managed-node.json` permits empty `targets`.
Explicit legacy targets remain pinned until removed by the operator. Republish historical
unbound releases through rollback before binding. Publishing never switches a number.
Node health and per-release readiness remain separate.
[Linux deployment and verification](validation/publication-activation-2026-10-27.md).

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

The persistent large-v3-turbo worker runs independently on loopback port 15071.
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

### Live endpoint scheduling switch

For the agent carrier profile, `scripts/run-netgsm.sh` reads
`ALOJAN_TURN_PARTIAL_HINT` from the private carrier environment (default `0`).
The owner-directed 2026-10-24 deployment sets it to `1` on the Linux host. This
requires the compatible gateway and ASR scheduling implementation; it does not
change the LLM or silence thresholds. See
[deployment, rollback and the remaining quality gate](validation/endpoint-calibration-2026-10-24.md).


## Profile and system settings storage (PROF-02)

The existing migration command now includes additive `0003_profile_settings.sql`.
Use [the SQL setup guide](../infra/examples/README.md) for disabled sample profiles,
configuration ownership and isolated PostgreSQL checks. No SQL Server is required.
A fresh installation runs all migrations; existing installations retain migration
checksums and data. Sample profiles are optional and never activate carrier routes
or notifications. Current runtime does not yet consume these new tables.

## Native management application (AGP-02)

**2026-10-26 in-place trial update:** the owner authorized the existing unused line
as the evaluation environment. The existing database now has all 16 migrations;
the prepared owner configuration and number binding were installed. Managed voice
uses the existing workers; management HTTP and scoped summary/delivery use separate
containers without recreating PostgreSQL. Earlier statements below about an
unmigrated database or an exclusively loopback managed launcher are historical.
See [current deployment/evidence](validation/in-place-platform-2026-10-26.md).

`ALOJAN_VOICE_PROFILE=managed` selects the Netgsm managed launcher. Configure private
`ALOJAN_AGENT_PORT`, `ALOJAN_ASR_PORT`, `ALOJAN_TTS_PORT`, `ALOJAN_CALLED_SOURCE`
(`request_uri` by default), and `ALOJAN_CALLED_NATIONAL_PREFIX` (`none` by default).
For the current Netgsm trunk, retained signaling carries a ten-digit `850…`
Request-URI user: set `ALOJAN_CALLED_NATIONAL_PREFIX=0` explicitly. This enables
the existing exact Turkish-number normalization to the verified `+90850…` binding.
Leaving it at `none` rejects that carrier format with SIP 404 before agent setup.
Confirm the actual trunk format; do not infer it from the stored canonical number
or enable fallback to caller headers. The source allowlist remains mandatory.
Existing source allowlists, caller normalization and public/LAN addresses remain
infrastructure configuration. Do not pass global prompts or turn tuning to this
profile; publish a prepared engine revision instead. The explicit native managed
ports require adaptive turn models and trusted allowlisted SIP sources. Test-only
ports retain their previous loopback restriction.

Validate the pinned release with the exact summary/delivery worker image as well
as the live agent before declaring a deployment ready. A running idle worker does
not prove release compatibility: the first managed handset trial exposed an older
worker image with the former 6,000-character instruction limit, while the deployed
agent/management contract already accepted 20,000. Align the shared contract image;
do not truncate the user's instructions or reset pending job claims. Expired leases
allow the corrected worker to resume the existing summary exactly once at commit.

[Management setup and exact HTTP contract](../services/app-api/README.md) documents
public registration with private workspaces, scoped draft authoring, the independent
Docker image, cookie/origin configuration, private recovery and Linux validation.
Use additive migrations and a separate restricted management DB role for deployment.
Do not use the live migration role or activate routes from unprepared drafts.
The self-service voice runtime and live migration remain pending.


### Prepared release validation (AGP-02/06)

For exact reuse of a trusted historical EMA pack, use the operator-only
[`alojan.voice_pack` command](../services/app-api/README.md#immutable-publication-and-prepared-audio).
It checks source provenance inputs/integrity and produces a release-format pack without
inference, qualification or publication. Candidate Kübra v2 and its verified unchanged
WAVs are staged privately under `.local/voice-preparation-20261026/` on Linux; its
`owner-state.json` supersedes the earlier preparation state's draft version/path.
Do not use the earlier v1 state for subsequent preparation. See the
[2026-10-26 evidence](validation/voice-pack-preparation-2026-10-26.md). Changed speech
still requires fenced resident EMA generation; never relabel another profile's audio.

Use the updated [management contract](../services/app-api/README.md) for the native
email login, preparation/publication/rollback APIs, restricted database-role grants
and trusted prepared-WAV import command. All commands run on primary Linux.
`infra/compose.management.yaml` now connects management and PostgreSQL through a
private internal bridge and publishes HTTP on host loopback only. Its network change
requires a coordinated PostgreSQL container recreation at the approved rollout gate;
it has not been applied to the live stack. Preserve the current lifecycle release.

`tools/validate-management.py` accepts `--network`/`--database-host` together to test
a disposable management container against the existing database bridge. It creates
its own restricted role/schema/secret and cleans them up; no live schema migration.
Run the release tests alongside the existing account/draft/database/profile suites.
No catalog qualification, agent activation or target-account ownership migration
is implied by passing management tests. Production audio generation remains drained
resident EMA work, not an HTTP side effect or a second model process.


### Number binding and admission repository (AGP-03)

Migration 0008 and `tests/test_number_routing.py` extend isolated management validation
with verified ownership, node readiness, atomic release binding and async call
snapshots. Use [the management contract](../services/app-api/README.md) for protected
number endpoints, private evidence commands and `alojan.roles --purpose routing`.
The management deployment may set `ALOJAN_VOICE_NODE_ID`; this is system configuration,
not a user field. It does not create a ready node or authorize a carrier route.

The private agent setup path consumes snapshots and requires preloaded runtime/PCM;
the native gateway does not yet consume these releases. Do not mark production
readiness or apply live migrations until native/audio/scoped-storage consumers,
private RPC authentication, initialization/activation/cancellation and stale-call
reconciliation are integrated and tested against the newer live lifecycle release.
The existing second number remains disabled; do not synthesize private number/bot
configuration or infer agent ownership from an unverified email identifier.


## Private release readiness coordinator

AGP-03 now has a tested internal preload/health coordinator. The normal agent launcher
remains legacy and the native managed profile remains loopback-only. Do not attach a
routing service to a public/carrier deployment until credential/tool/action consumers,
qualification and migration are complete. Explicit isolated startup is described below.

Apply additive migration `0010_release_readiness_consumer.sql` using controlled
migration credentials before updated role provisioning. Existing receipt rows remain
unchanged; only the coordinator's fresh local pins can authorize managed admission.
Provision a separate existing unprivileged DB role with private operator credentials:

```sh
PYTHONPATH=services/app-api:services/voice-contracts uv run --project services/app-api \
  --frozen python -m alojan.roles READINESS_ROLE --purpose readiness --node-id VOICE_NODE
```

`ALOJAN_DATABASE_URL` in this provisioning command is the private migration DSN, never
a request parameter. Runtime ReadinessRepository uses the dedicated readiness DSN;
AgentService retains separate routing/record DSNs. Do not reuse a management, record,
summary or routing role. Reprovisioning is an operator action. No default credentials,
number claims or ready=true seed is provided. `infra/examples/agent_readiness.sql`
is a read-only diagnostic; its example identifiers never activate a release.

The caller supplies trusted deployment targets and existing private speech channels,
activates each target, runs the refresh task, and closes it before cache/channel
teardown. Tests use ephemeral ports, generated assets and disposable DB schemas;
there is no source/audio copy or EMA generation during a phone call. This component
adds no HTTP service. Future management startup must remain its separate Docker app.

## Explicit managed-node startup (isolated AGP-03)

### Supervised admission validation package

AGP-09, M1/M5: `infra/docker/supervise.py` and `health.py` retain the operator's
preserved lifecycle deployment source. The supervisor adds optional gateway admission
control; other workers keep their existing launch/probe behavior. The updated
`scripts/run-netgsm.sh` forwards supervisor startup arguments and retains the Linux
caller's national-prefix setting. See [the control contract](../services/voice-gateway/README.md#supervised-persistent-admission).

The operator-only `infra/compose.admission.yaml` overlay requires an explicit tested
`ALOJAN_ADMISSION_IMAGE` and absolute `ALOJAN_ADMISSION_DIR`. It mounts that directory
read-only and selects `/run/alojan-admission/state`. Before a compatible deployment,
create the directory with owner-only permissions, persist `drained\n` as its state,
and retain it across restarts. Change state using a same-directory temporary regular
file, flush/fsync it, atomically replace `state`, then fsync the directory. Only
`open\n` allows admission. Never mount the state file alone, since replacement would
leave the container reading the old inode. Do not send USR signals to the supervisor.

`infra/docker/gateway-admission.Dockerfile` is a staged Linux validation recipe.
Supply a verified local base tag with its recorded image ID, plus a context containing
the tested Linux `voice-gateway`, `supervise.py`, `health.py`, and `run-netgsm.sh`.
Do not use a Mac binary or the repository-wide build context. Docker's BuildKit
interprets a bare `sha256:...` FROM argument as an image name; tag the exact local
image ID, verify the tag's ID, and supply that tag with `--pull=false`. No registry
publication or new dependency installation is needed. Record both final image ID and
native binary hash. This derivative preserves the old runtime/model libraries; it
is not a replacement for a fresh full-source production build or managed-model gates.

Primary Linux artifacts are in `.local/supervised-drain-20261026/`: the staged image,
source backups, test logs, and Docker acceptance script/result. The isolated container
used no network, secrets, DB, GPU or carrier ports, and was removed after checks.
Compose was validated against the preserved `.local/call-lifecycle-release/infra/`
base and voice definitions; no `compose up` was issued. Applying the overlay to a
live project remains pending coordinated worker quiescence and rollout checks.
Do not recreate PostgreSQL or unrelated services as part of a gateway-only change.

For maintenance, wait for fresh native closed/local-drained acknowledgements after
the operator write, bound to the current container start identity. If the process
restarts, repeat receipt verification. Confirm all dependent work/leases and exclude
other GPU producers before a preparation or benchmark run. Resume only after that
work finishes. The tested overlay does not itself establish worker quiescence.

### Managed runtime preparation

#### Dependent-worker maintenance fence

Deployment update (2026-10-26): gateway and speech workers are admission-closed
after explicit owner-authorized bootstrap INVITE fencing. Actual startup/idle
receipts passed, but the agent is now stopped: its scoped consumer requires tables
absent from the unmigrated production DB. The strengthened startup check rejects
that schema before listening. Matching candidate schema/runtime is next. See
[rollout evidence](validation/maintenance-rollout-2026-10-26.md) for exact images,
rollback, private operator helpers and remaining acceptance gates. Earlier package
validation paragraphs below describe their historical pre-deployment state.

Compatible ASR, TTS, legacy-agent and managed-agent launchers now opt into an
operator-only gate with `ALOJAN_WORKER_ADMISSION_FILE`. This is separate from the
gateway's admission file: close gateway admission first and let calls finish before
closing the workers. Only an exact `open\n` regular file opens worker admission;
all other states fail closed. Use owner-only directories, atomic replacement and
file/directory fsync as described above. Mount the directory read-only, not its
individual state file. No management API or user profile can change this control.

`infra/compose.worker-maintenance.yaml` requires explicit tested ASR/TTS/agent image
references and an absolute worker-state directory. The existing supervisor still
probes ordinary service health, so intentional maintenance does not cause restart
loops. The separate maintenance check is **not** a container liveness check.

On a compatible process, existing gRPC Health **Check** for `voice.v1.Maintenance`
returns SERVING only when admission is closed, no tracked RPC/lease/active call or
agent summary/initialization/turn remains, native futures have completed successfully,
and cleanup is confirmed. It is computed for each check, not cached. Health Watch
does not provide this receipt. Ordinary service health keeps its original meaning.
Missing support, RPC errors, open/busy workers or unconfirmed cleanup all fail the
operator probe with a nonzero exit status and no credential/response-body logging.

```sh
docker exec "$ASR_CONTAINER" services/asr/.venv/bin/python infra/docker/health.py asr --maintenance
docker exec "$TTS_CONTAINER" services/tts/.venv/bin/python infra/docker/health.py tts --maintenance
docker exec "$AGENT_CONTAINER" services/agent/.venv/bin/python infra/docker/health.py agent --maintenance
```

Close new gateway admission, wait for its current local drain receipt, close the
separate worker state, then require all three current-process maintenance checks.
Keep both controls closed during the reserved interval. Capture container start
identities and `worker_maintenance instance=...` events; any worker restart invalidates
the reservation and requires a fresh check of all dependencies. Restart may warm a
model before its listener is ready; do not infer a globally reserved GPU from an old
receipt. Native futures/lease expiry alone and `nvidia-smi` idle snapshots are not
substitutes for these gates. Exclude other GPU producers and independent summary,
delivery or management work as required by the selected performance scenario.

The gate rejects new inference/setup RPCs with UNAVAILABLE, while existing requests
finish and cancellation, release, end-call and playback bookkeeping remain allowed.
Legacy summaries stop claiming new work but retain queued jobs and finish the current
job. DB reconciliation/readiness housekeeping can continue; the receipt is not a
database write lock or proof that an external provider has stopped computation.
No cancellation timeout forcibly converts an incomplete cleanup into success.
Unexpected cleanup errors and cancelled/failed native futures remain unready; inspect
and repair/restart the affected worker before accepting a fresh receipt.

After preparation, open worker admission first, verify normal health and managed
release readiness, then reopen gateway admission. If a benchmark intentionally uses
the resident workers, keep the gateway closed and reopen only the required workers
under exclusive operator control; their maintenance receipt is no longer valid while
the benchmark runs. Never start a second EMA instance to bypass the fence.

`infra/docker/worker-maintenance.Dockerfile` builds source-only validation derivatives
of verified retained local runtime images, using a staged context with Python sources,
generated Python contracts and `health.py`. Private logs, secrets, caches, model weights
and host virtual environments are excluded. The Linux artifact directory
`.local/worker-quiescence-20261026/` retains the exact base/final image IDs, packaging
script and import/CLI checks. These checks load no GPU model and are not full-source
production build or model readiness evidence. The resident containers are unchanged;
see [validation](validation/worker-quiescence-2026-10-26.md).

Native maintenance control: the updated gateway supports
[`--start-drained 1`, SIGUSR1 and SIGUSR2](../services/voice-gateway/README.md#operator-admission-drain).
Use only a verified compatible gateway PID and process-specific acknowledgement;
the resident lifecycle image and its supervisor have not been upgraded. In a
maintenance launch, preserve start-drained across automatic restarts. A local
`admission_drained` event does not establish remote GPU quiescence; unresolved
cleanup/leases and other inference producers must also be accounted for. Do not
replace a live long call with SIGTERM. See the local SIP evidence in
[admission drain validation](validation/admission-drain-2026-10-26.md).

Owner preparation update: the [2026-10-26 evidence](validation/owner-preparation-2026-10-26.md)
records a verified real live-backup restoration and the separate
`alojan_candidate_20261026` database. Its private account/connection identities, restricted
DSN and encryption key are in `.local/owner-preparation-20261026/` on Linux. Do not point
resident services at this candidate or mistake it for the live DB: it has no qualified
release, grant, phone binding or historical call records. Owner password setup is still
required before interactive use. Use the existing private `alojan.accounts reset-password`
flow with the **candidate** DSN; never pass a password in CLI arguments or chat. The
temporary HTTP probe has exited; no persistent API or host port was installed.

Live migration preflight: see the
[2026-10-25 report and cutover order](validation/platform-preflight-2026-10-25.md).
The [legacy rollback boundary](validation/legacy-rollback-2026-10-25.md) now provides
the operator-only `alojan.roles ROLE --purpose legacy-rollback` provisioning path and
`infra/compose.legacy-rollback.yaml` credential overlay. Linux record/consumer tests,
expanded regression, package imports and Compose configuration checks passed after
connectivity resumed on 2026-10-26. This is not a live rollback rehearsal. Do not restore
the old privileged database secret.
The resident deployment currently uses preserved `lifecycle-20261024` Docker images;
do not confuse it with the native development profile. Its old summary consumer has
no workspace filter and its DB role bypasses RLS. Stop that consumer before managed
jobs can exist; rollback needs a tested legacy-only consumer boundary too. Migration
must use explicit connection lock/statement budgets and a restorable backup. A recent
idle observation does not replace admission fencing for asset generation/cutover.

Rehearse the deployed three-migration schema and legacy data preservation without
copying any real records:

```sh
uv run --frozen --env-file .local/dev.env pytest tests/test_legacy_platform_upgrade.py -q
```

These tests create disposable schemas, verify repeat upgrade, late-error and lock-timeout
rollback, and check that no ownership/route/grant/action is seeded or historical send
requeued. They do not apply production migrations or activate any release.

`python -m alojan_agent.managed --config /absolute/private/managed-node.json` starts
the routed agent using only operator-selected immutable releases. It is a separate
entry point in the existing voice app, not an HTTP server or a new Docker service.
The original `python -m alojan_agent` and resident carrier launch scripts remain legacy.
Management HTTP continues in its own Docker service. Do not use this launcher for the
resident carrier until remaining action and qualification gates pass.

Copy `infra/examples/managed-node.json` to ignored private deployment storage and
replace synthetic identifiers with existing, prepared releases for the chosen node.
Use an absolute installed asset directory and three distinct, unused loopback ports.
Start compatible ASR/TTS workers with `--require-agent-release` on those ports first.
The file accepts only schema version 1 and 1–16 unique `(scope_id, release_id)` pairs;
it is bounded to 64 KiB. It contains no tokens, numbers, user engine knobs or generated
prompts. It never creates a release, prepares audio, verifies ownership or binds a DID.
The unavailable second number is omitted, not seeded or activated.

Provision separate routing, records and node-specific readiness roles using the existing
`alojan.roles` commands (`--purpose routing`, `--purpose records`, and
`--purpose readiness --node-id NODE`) after applying migrations through 0011 in the
intended environment. Supply their private connection strings via
`ALOJAN_ROUTING_DATABASE_URL`, `ALOJAN_RECORDS_DATABASE_URL` and
`ALOJAN_READINESS_DATABASE_URL`. Missing values fail startup; there is no fallback to
`ALOJAN_DATABASE_URL`. Role provisioning remains responsible for least privilege/RLS.
Managed mode additionally requires `ALOJAN_CREDENTIALS_DATABASE_URL` for a separately
provisioned `--purpose credentials` reader and `ALOJAN_CREDENTIAL_KEY_FILE` for the
external encryption key described below. Every selected release needs its own scoped
`model_connection` reference. Managed mode never reads `OPENROUTER_API_KEY`; structural
preflight does not verify provider quota/API access. Never use an admin/migration DSN
for runtime roles.

Example after loading the private runtime environment into the process:

```sh
PYTHONPATH=services/agent:services/voice-contracts:generated/python \
  uv run --frozen python -m alojan_agent.managed --config /absolute/private/managed-node.json
```

The launcher reserves its agent port exclusively before claiming receipts, checks
routing access, preloads/probes every target and refreshes the full set before serving.
Any failed target aborts the whole startup and withdraws owned receipts. A restart
revalidates installed assets/dependencies and obtains new consumer IDs. There is no
automatic activation of new releases or hot reload of this file; change explicit targets
through a controlled stop/start until a deployment controller is implemented.
Use one process per node identity. Different endpoints sharing a node identity still
have the coordinator's bounded successor fencing, not an atomic blue/green handoff.

SIGTERM/SIGINT stop local admission, withdraw owned receipts, cancel generations and
close RPC leases/cache/provider channels. Repeated stop signals do not interrupt cleanup.
The existing reconciliation loop checks this node's stale routes every 30 seconds;
600 seconds is the fixed system recovery age, above the 300-second engine ceiling.
Forced termination can leave uncertain calls until reconciliation and DB readiness
until its ten-second TTL. A stop is not a zero-downtime active-call migration.

The legacy summary/Telegram loop is not started here. Ended scoped calls persist
summary jobs for the separate worker; no external delivery is implied. Health SERVING
reports the running RPC service after startup, while each new call still needs fresh
release readiness. Dependency loss closes admission without changing existing call pins.
Real provider/CUDA, PERF-01–06, carrier and ownership migration remain separate gates.

## Scoped provider credentials and separate summary worker

Apply additive migration 0011 and reprovision dedicated roles in the intended test
environment before using the new API. `--purpose credentials` grants a read-only,
workspace-RLS credential reader with no account/call/publication/delivery access.
Management can insert ciphertext and read connection metadata, but cannot select
the ciphertext column. Other runtime roles cannot read credentials. Do not combine
these roles or pass the migration DSN to either executable.

One external encryption key is shared by the authorized management writer and
credential consumers. It is never stored in PostgreSQL, a release, the repository,
an image or a log. Create it once in private deployment storage (preserve/back it up
securely; replacing it makes existing ciphertext unreadable):

```sh
uv run --frozen python - <<'PY'
import os
from cryptography.fernet import Fernet
fd = os.open('.local/provider.key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'wb') as output:
    output.write(Fernet.generate_key())
PY
```

Set `ALOJAN_CREDENTIAL_KEY_FILE` to this file for the native managed agent. In the
management container, add the opt-in `infra/compose.credentials.yaml` overlay after
`infra/compose.management.yaml`; it mounts the key read-only and supplies its path.
The existing management configuration still runs without that overlay; credential
creation then returns `credential_storage_unavailable`, not a plaintext fallback.
Do not send the key or a provider token in a chat or command argument.

The protected API has workspace-scoped `GET/POST provider-connections` and
`POST provider-connections/{id}/revoke` resources. Creation accepts exactly
`provider: "openrouter"`, a label and `api_key`; responses/listing expose only ID,
provider, label and enabled status. Only owners create/revoke; existing origin/CSRF,
session, scope and body-size checks apply. Set `model_connection` to that UUID in the
agent draft, prepare/publish a release, then explicitly deploy it. Selected references
are rechecked under a lock at draft write/publication/rollback. A connection ID cannot
be transplanted from another workspace. `infra/examples/provider_connections.sql`
is a read-only metadata/reference example, never a token seed.

Connections and their encrypted identities are immutable. To change an API key,
create a new connection and explicitly republish/rebind the agent; old jobs keep the
old reference. Revocation is irreversible and prevents new provider requests after
bounded propagation. In-place credential rotation/master-key rotation is not yet
implemented. Historical manifests without `model_connection` retain their exact
digests and can be inspected/offline-published, but managed deployment rejects them.
Republish with an explicit connection before migration; there is no global-key fallback.

The node preloads at most 16 provider clients. Background readiness refresh checks
connection/workspace status; selection during a turn is memory-only. A two-second
monotonic freshness window bounds stale key use. Refresh preserves still-fresh access
while its IO runs and clears access on failure; missed refresh expires automatically.
Revocation or credential-storage outage blocks subsequent provider requests, including
later turns of existing calls. Already-dispatched requests are not forcibly recalled.
This is bounded revocation, not instantaneous cancellation or proof of provider quota.

`services/action-worker` is an independent pinned dependency environment; its launcher
is `python -m alojan_agent.summary_worker`. It requires only
`ALOJAN_SUMMARIES_DATABASE_URL`, `ALOJAN_CREDENTIALS_DATABASE_URL` and the key-file path.
It never reads the legacy database/model/Telegram environment. Provision summaries
with `--purpose summaries` and credentials with `--purpose credentials`. A private
`.local/worker.env` supplies the two runtime DSNs; use container-reachable PostgreSQL
addresses when running under Docker. The opt-in `infra/compose.worker.yaml` overlay
adds the worker in a separate container, with no published port, no GPU and bounded
CPU/memory/PIDs. It has outbound provider access; management HTTP stays independent.

```sh
PYTHONPATH=services/agent:services/voice-contracts \
  uv run --project services/action-worker --frozen --env-file .local/worker.env \
  python -m alojan_agent.summary_worker --once
docker compose --env-file .local/dev.env -f infra/compose.yaml \
  -f infra/compose.worker.yaml config --quiet
```

The first command consumes at most one scoped job and can call the configured provider;
run only in the intended accepted environment. Without `--once` it polls sequentially,
sleeping one second when idle/unavailable. Each job has an independent provider client
and pins its historical release, instructions, records and credential reference.
Cancellation/crash leaves the existing 60-second claim lease for retry; stale claims
cannot finalize over a successor. Credential absence/revocation or model failure emits
an explicit failed/null summary; infrastructure/input errors retain leased work for
retry. Successful finalization preserves note confirmation evidence and occurs once.
The summary worker itself never sends Telegram/webhook actions. Delivery is handled
by the separate process documented below. The worker has no placeholder health
endpoint; inspect its process/logs and scoped queue/finalization state. Initial Docker
validation builds images and imports entry points without starting resident services.
`.dockerignore` allows only reviewed source/lock/migration files into either image.


## Telegram connection authoring foundation

AGP-05 migration 0012 extends the isolated management schema. Apply migrations in
order with operator credentials, then re-provision the management role for metadata
SELECT, INSERT and UPDATE(enabled) on telegram_connections. All existing private-role
provisioners now require 0012 and reject Telegram ciphertext-read privilege, including
the OpenRouter credential reader. Do not add that privilege to the summary/voice roles.
The management readiness endpoint now requires migrations 0011 and 0012 as well as
its prior schema baseline. No live migration was performed during development.

Use the same external key and optional compose.credentials.yaml mount documented
above. The owner-only telegram-connections API stores a fixed numeric chat ID and
write-only bot token; GET returns metadata. There is no bot validation request, test
send, send grant or live activation on save. Never put a real token in CLI arguments,
SQL examples, logs, source files or manifests. Connection replacement creates a new
reference; master-key/token rotation in place remains unimplemented. The separate
summary worker continues to finalize calls without delivering Telegram messages.


## Reviewed post-call grants

Migration 0013 follows Telegram connection storage and is required by management
readiness. Re-provision management grants after applying it; no worker receives grant
writes. The API review/authorize/revoke flow is documented in services/app-api/README.md.
Initialize no owner grants from SQL, migrations, prompts or fixtures with real targets.
New action-bearing publications use schema v2 and pin the exact original grant.
With migration 0014 and the scoped delivery consumer below, runtime/preload supports
v2 for its exact workspace. Legacy v1 retains its original digests/behavior. Do not
manufacture readiness receipts; publication does not start a worker or certify delivery.
No live migration or resident restart accompanies this implementation.

## Scoped Telegram delivery

AGP-05 now includes migration 0014 and independent `alojan_agent.delivery_worker`.
Apply migrations with operator credentials in the intended schema, then re-provision
`--purpose summaries` for atomic job/scheduler insertion and a **new dedicated** role
with `--purpose actions`. Never combine it with management, records, summary or
provider-credential roles. Management readiness requires 0014. The migration creates
no jobs for old events, no targets and no grants; granting a role sends nothing.

The action role reads only its job projection, scoped grant/target, issuer enabled
state/membership and workspace enabled state; it cannot read raw call records,
provider ciphertext, passwords or sessions, nor author grants/jobs/destinations.
Both the release and its original grant are enforced by the job's composite FK.

Create an ignored, private `.local/delivery.env` with
`ALOJAN_ACTIONS_DATABASE_URL` for that role. The Docker overlay mounts it only into
`delivery-worker`, with the existing external `.local/provider.key` at
`ALOJAN_CREDENTIAL_KEY_FILE`. Use a container-reachable database address. The worker
and summary containers use the same pinned image but independent commands, DSNs,
resource limits and lifecycles. No credentials belong in source or CLI arguments.

```sh
# Inspect composition only; does not start a worker or send a message.
docker compose --env-file .local/dev.env -f infra/compose.yaml \
  -f infra/compose.management.yaml -f infra/compose.credentials.yaml \
  -f infra/compose.worker.yaml config --quiet
```

Only start the delivery service in a separately accepted environment: starting it
(or running its `--once` command) can send previously authorized pending jobs. Saving
a connection/draft/grant still sends nothing. Review metadata with
[the read-only SQL example](../infra/examples/action_delivery.sql), without displaying
payloads or credentials. Worker logs expose sanitized event/class only. Do not enable
HTTP wire logging: Telegram URLs carry credentials.

The former v2 compiler/preloader gate is removed because the scoped consumer now
exists; v2 requires its exact workspace. This does not manufacture node readiness or
real remote acceptance. Production rollout still needs the worker, roles, key mount,
accepted destination and the existing voice quality/PERF/carrier gates. Revocation
blocks subsequent dispatch checks, not already-authorized in-flight HTTP. Crashes or
ambiguous responses after sending begins produce terminal delivery_unknown, with no
automatic retry. The reviewed manual-retry workflow is documented below; never
reset terminal rows directly. No live migration or resident restart is implied.

## Delivery outcome and retry management

Apply migration 0015 with operator credentials in the intended schema and re-provision
both management and actions roles. Management readiness now requires 0015. No existing
job is reopened by migration. The migration adds a 0..3 retry_generation, scoped
immutable action_retry_requests, indexed history and unconsumed-request lookup. Only
the worker may set the request's consumed_at marker; consent itself cannot change.

Deploy management and the delivery worker together: management stores owner approval,
while the worker consumes at most 32 pending approvals per iteration before its
existing fair/rate-limited claim. Consumption and original-job reopening commit
atomically. Worker restarts cannot consume the same approval twice. An old worker
will leave approvals waiting rather than implicitly retrying them. No new service,
credential environment variable or dependency is introduced.

The [API contract](../services/app-api/README.md#delivery-outcomes-and-reviewed-retry-agp-05)
describes metadata-only history, owner-only exact-message review, the duplicate warning,
explicit acceptance and idempotent request_id replay. Approval alone is not delivery.
The same original grant/target and live requester membership must hold at dispatch;
permanently revoked grants/targets cannot be revived. Never reset terminal rows or
fabricate a success receipt. Frontend and real Telegram/carrier/PERF acceptance remain
separate. [SQL diagnostics](../infra/examples/action_retries.sql) omit review content.


## Approved private web preview (AGP-06)

The owner-approved Next.js/shadcn frontend is in `services/web`, with independent
web/TLS services in `infra/compose.web.yaml`. Follow its [README](../services/web/README.md)
for pinned Linux build/browser validation, exact-origin configuration and rollback.
Do not rebuild/restart voice services to deploy the frontend. Keep resource caps.

The current preview is reachable only through an SSH forward from the Mac:

```sh
. .local/remote.env
ssh -f -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 -L 127.0.0.1:13443:127.0.0.1:13443 "$ALOJAN_DEV_SSH"
```

Open `https://localhost:13443`; its private self-signed certificate requires a
browser exception. Do not change system trust or disable verification globally.
If the port is occupied, inspect the existing tunnel rather than opening another.
The tunnel can close on laptop sleep or connection loss; the Linux containers
remain independent. Use a real certificate/origin for a future public domain.

Private first-login details are in `.local/web-preview-20261026/giris-bilgileri.txt`
on the Mac; never paste them into logs, documentation, commits or screenshots.
Change the initial password through Account after first login. Read the
[validation report](validation/web-preview-2026-10-26.md) for feature limits.

### Prepared audio preview and Telegram action UI

The management container now needs a read-only mount of the trusted workspace voice
store at `ALOJAN_VOICE_ASSET_ROOT` for the two prepared preview clips. Absence returns
a sanitized 503 only for preview; it must not silently expose another directory or
invoke synthesis. The web/TLS resource limits and private origin are unchanged.
Deploy updated management/web only; keep voice/background/DB container identities.

Use the management project's pinned test dependency when running its regressions
from the root environment: `uv run --frozen --with httpx==0.28.1 --env-file
.local/dev.env pytest -q tests/test_voice_preview.py tests/test_agent_releases.py
tests/test_action_grants.py`. Run the isolated browser harness after rebuilding for
its test API port as described in the web README. Never run synthetic action tests
against the owner account. The real owner smoke only reads existing settings/audio;
it does not grant, revoke, publish, rebind or send a notification.

Rollback copies for this update are under `.local/web-actions-20261026`; restore
only the management configuration and web image environment, then recreate those
two services. No DB rollback or voice restart is needed. See
[validation](validation/web-actions-2026-10-26.md).

## Durable resident audio preparation (AGP-06)

The private preview now requests queued audio through the management API. Run the
[separate host coordinator](../services/voice-preparer/README.md) with its dedicated
SQL login, pinned runtime and operator-owned configuration. Migration 0016 adds only
the queue; reapply management grants. TTS must have its own admission file before
enabling the coordinator. It never loads a second model or runs inside HTTP.

The Linux deployment uses `.local/voice-preparer/` for private configuration, journal
and rollback evidence, and `alojan-voice-preparer.service` as a bounded user service.
Observe the documented recovery process after interruption; never treat expiry or
a generic healthy flag as a fresh drain receipt.

## Background response timing import

AGP-06/P1 uses the existing gateway's content-free `turn_latency` log records, not
conversation timestamps. Apply 0019 with migration credentials after backup and
provision the existing management role with `grant_management`. Create a fresh,
unprivileged login role and run `alojan.latency.grant_ingest(dsn, role, node)` using
private operator credentials. The collector reads route IDs for that node and
inserts bounded numeric samples; no credential/transcript/audio access is granted.

Keep these files private (0700 directory, 0600 files):

- `.local/latency/database.env`: `ALOJAN_DATABASE_URL` for the dedicated import role,
  in Docker environment-file syntax (the DSN value is not shell-quoted).
- `.local/latency/collector.env`: `ALOJAN_LATENCY_IMAGE=sha256:...` with a validated
  management image, `ALOJAN_VOICE_NODE_ID` matching the gateway's configured node,
  and absolute `ALOJAN_LATENCY_DATABASE_ENV` pointing to the first file.

Install `infra/systemd/alojan-latency-import.{service,timer}` in the Linux user's
systemd directory; adjust the default `%h/ai/alojan` paths if necessary. Run
`scripts/import-latency.sh` with the collector environment once, then enable/start
the timer. It reads at most 10000 gateway log lines from the last ten minutes every
minute and starts a short-lived non-root/read-only container with 0.25 CPU/128 MiB.
The host-side oneshot has a 45-second deadline and 256 MiB ceiling. It neither starts
nor restarts the gateway and exposes no HTTP port. Pinned images avoid mutable
checkout code in the import process. No raw log capture is stored.

Check `systemctl --user show alojan-latency-import.service -p Result -p ExecMainStatus`
and the timer's next activation. Journal output contains counters only; malformed,
unowned and duplicate observations are not presented as fresh samples. The UI's
last-import timestamp is the latest persisted observation, not a collector heartbeat.
An interruption longer than ten minutes or log rotation/tail limits can lose samples;
this is a bounded diagnostic view, not a lossless telemetry pipeline. A future wider
capacity rollout must qualify retention/throughput before changing these bounds.
An operator can explicitly replay a bounded older log window; existing samples will
not be duplicated and unscoped legacy identities will not be adopted.

Rollback: stop/disable the timer, allow its current oneshot to finish, restore the
prior management/web image IDs, and recreate only those HTTP services. Leave the
additive table and private role intact for investigation; no voice rollback or sample
deletion is needed. Deployment evidence lives in the ignored `.local/performance-ui-20261026`.

## Candidate MCP runtime (AGP-07)

Migrations 0020–0022 remain isolated candidate work; the serving schema is still
through 0019. Apply and validate all three before provisioning the separate discovery
and execution roles. Follow the [management provisioning](../services/app-api/README.md#mcp-release-pinning-and-execution-agp-07-runtime-slice)
and [managed-node contract](../services/agent/README.md#mcp-call-runtime-agp-07).
The optional executor uses the existing native managed agent; no new HTTP app or
unbounded per-agent process is added. Management HTTP remains its separate container.

Test with the frozen root environment and the management project's pinned HTTP test
dependency. `tests/test_mcp_runtime.py` uses real PostgreSQL service roles and the real
Agents/MCP SDKs with synthetic model/HTTP peers. It requires the private `.local/dev.env`
DB connection and never contacts an external MCP server. Include release/readiness,
summary/action, managed-startup and historical-compatibility suites before rollout.
Do not infer endpoint authorization or enable production MCP from a passing mock test.


## Candidate MCP OAuth (AGP-07)

Migrations 0020–0023 and matching API/worker/executor/web images remain coordinated
candidate work; serving schema remains through 0019. OAuth uses the already separate
management application and discovery worker; no additional web service is embedded
in voice. Follow the [provider/role/overlay setup](../services/app-api/README.md#oauth-lifecycle-agp-07-candidate).
The example registry is synthetic and must not be activated unchanged. A real approved
provider, preregistered public client, redirect origin and explicit real-server test
are prerequisites for activation. Do not send test calls to an arbitrary provider.

`tests/test_mcp_oauth.py` uses disposable PostgreSQL schemas and restricted production
roles with synthetic AS/token peers. Browser `mcp-oauth.spec.ts` intercepts OAuth API
and provider responses; it validates UI behavior but not real provider interoperability.
Run it through `tools/validate-web.py` with the newly built candidate API and pinned
Node/Playwright images. The ordinary 19 scoped API journeys remain real DB/API checks.
Do not reuse a serving schema, import user tokens into fixtures or archive raw callbacks.

## HTTP post-call candidate rollout (AGP-08 / migration 0024)

The candidate is documented in [HTTP evidence](validation/http-actions-2026-10-26.md).
No new daemon/container overlay or dependency is required: HTTP stays in the existing
independent management application, Next frontend and action delivery worker.

Before activation, back up schema/service identities and confirm no outstanding
sending lease is being replaced. Apply unchanged migrations in order through 0024
with the migration role; re-provision the existing management/actions roles using
their normal commands. New generated target columns backfill historical Telegram
jobs; adapter-specific foreign keys preserve workspace identity. Never bypass the
migration checksum runner or insert grants/retry requests through SQL.

Activate compatible management, action worker, voice-contract consumers and web
images together, using the existing controlled rollout/health/readiness procedure.
The actions role needs HTTP connection SELECT and action_jobs.http_status UPDATE;
management must not have ciphertext SELECT. An unreprovisioned worker lacks the new
column/table permissions and cannot dispatch. Do not enable an HTTP-bearing release
until a compatible worker is present. Pending MCP migrations/consumers and existing admission gates still apply.

Create a fixed HTTPS destination through the owner API/UI, then explicitly review
mapping and grant, publish and route separately. Saving/reviewing sends nothing.
A real endpoint test is an external write and needs explicit authorization. No new
network test button or automatic callback is added. API/worker `--once` can send queued
authorized actions; do not use production queues for synthetic transport tests.

Use [disabled SQL example](../infra/examples/http-actions.sql) only in a synthetic
workspace after 0024; it rolls back and seeds no job/grant. Candidate schemas/tests
must remain separate from serving PostgreSQL. Downgrade is not a destructive reverse
migration; preserve queued intent and use compatible images or reviewed recovery.

## Declared output candidate activation (AGP-08)

No migration 0025 is needed: definitions live in existing immutable draft/release JSON,
and outputs/statuses in existing final-event JSON. Existing MCP execution rows/indexes
supply scoped successful results. Apply earlier candidates through migration 0024 as
usual, then re-provision the `summaries` role through its normal call-record provisioning
command. It needs limited SELECT of scope/call/release/alias/status/ordinal/completed_at/
output on mcp_tool_executions, under existing workspace RLS. No management/action/record
role may read the raw output column; no new execution write permission is granted.

Activate matching shared contracts, management, summary/delivery workers, voice/preparer
consumers and Next frontend through the existing coordinated rollout. v4 releases and
v3 output consent reject unsupported older consumers; existing empty-output releases
retain their v1–v3 versions/digests. No automatic migration/republication/rebinding of
live agents or historical output backfill. A new publication is required to configure
outputs for future calls. Preserve original finalizations and uncertain job history.

Tests use disposable databases, synthetic model/tool transports and the pinned Agents
SDK. No external request or serving worker `--once` is needed to validate this slice.
See [evidence](validation/declared-outputs-2026-10-26.md) and the read-only PostgreSQL
example. Real inference/receiver acceptance and PERF-01–06 remain separate gates.

### Summary-conditioned post-call actions (AGP-08 candidate)

Non-default action conditions require release-v5/action-review-v4 consumers across
management, readiness/voice-preparer, voice and summary/delivery services. Upgrade
consumers together before publishing these agents; old default releases retain their
schema/digest. There is no new migration beyond the existing HTTP/output candidate
chain and no new role permission. Never replay historical finalizations as part of
activation. Run `tests/test_action_conditions.py` with the frozen root environment,
`--with httpx==0.28.1` and `.local/dev.env`, plus the compatibility/browser suites.
[Sanitized evidence and candidate images](validation/action-conditions-2026-10-26.md).

### Optional transcript sharing (AGP-08 candidate)

Upgrade release-v6/review-v5 shared-contract consumers together, including management,
voice/preparer/readiness, summary/action workers and web, before publishing opted-in
agents. No new migration or privilege beyond the pending HTTP/output chain. Default
off preserves existing releases and greeting identities; enabled agents need freshly
prepared disclosure audio. No automatic live-agent republication or historical replay.
Run `tests/test_transcript_sharing.py` with the frozen root environment,
`--with httpx==0.28.1 --env-file .local/dev.env`, then relevant compatibility and web
checks. Disposable DB and synthetic receivers only. [Evidence](validation/transcript-sharing-2026-10-26.md).

### Call lifecycle action activation (AGP-08 candidate)

Apply additive `0025_call_lifecycle_actions.sql` after the existing candidate chain.
It permits terminal `not_requested` in summary jobs/finalizations and performs no
backfill. Management readiness now requires it. Re-run normal routing-role provisioning
for scoped summary-job INSERT and records-role provisioning for scoped agent-release
SELECT; do not grant finalization/delivery writes to routing/records or summary-model
access to routing. Existing RLS and immutable-route constraints remain mandatory.

Activate release-v7/action-review-v6 consumers together (management, voice/readiness/
preparer, summary/delivery, web). Old releases keep behavior; no automatic publication,
rebinding or historical replay. Preserve forward-compatible schema and queued intent
on rollback; do not drop the new enum value while such jobs/events exist. Run frozen
`tests/test_lifecycle_actions.py` with httpx 0.28.1 and `.local/dev.env`, scoped lifecycle/
routing/action compatibility and web journeys. [Evidence](validation/call-lifecycle-actions-2026-10-26.md).


## Bounded MCP schema candidate (AGP-07)

Deploy compatible management, voice/readiness/preparation, summary/delivery and web
consumers before publishing release v8 / MCP review v2. No new migration/role grants
are introduced by this slice; keep the previously required 0025 chain. Existing strict
v1 MCP grants and releases retain their bytes. Do not auto-approve discovered tools or
republish an existing agent. The no-answer queue guard includes v8. Rolling back to
older readers requires binding a compatible older release; retain additive DB state.

`tests/test_mcp_schema.py` exercises bounded schema narrowing, exact grants, fixed/null/
omitted inputs, output rejection and unanswered-call queue compatibility using isolated
PostgreSQL schemas and synthetic network. `tests/test_mcp_hindsight_live.py` is excluded
unless `ALOJAN_HINDSIGHT_READ_ACCEPTANCE=1` is explicitly set after owner authorization.
It performs real discovery and at most one `list_banks` read on the documented Hindsight
endpoint with an unmatched random query and pinned limit/offset; it never writes remote
memory. The exact inspected tool digest must match. Changed metadata needs a new review,
not a bypass. Use the frozen Linux environment with `--with httpx==0.28.1` and the private
development env; do not run this opt-in case during routine CI. Never print remote bank
content, session credentials or DSNs on failure.

The browser harness requires `--with httpx==0.28.1`, a frontend build with
`ALOJAN_MANAGEMENT_URL=http://127.0.0.1:18181` and its matching candidate management image.
For `tools/validate-management.py`, also set `PYTHONPATH=services/voice-contracts`.
[Acceptance and remaining limits](validation/mcp-schema-2026-10-26.md).


## Real post-call extraction and receiver acceptance (AGP-08)

Run on the primary Linux host using disposable DB schemas; do not supply a production
records DSN. `tests/test_declared_outputs_live.py` requires `ALOJAN_REAL_OUTPUTS=1`,
`ALOJAN_OUTPUTS_EVIDENCE_DIR` and a provider key in the private environment. It uses the
real restricted worker/credential pipeline with authored synthetic conversations and
no post-call actions. `tests/test_agent_summary_live.py` and
`tests/test_managed_summary_live.py` require `ALOJAN_REAL_SUMMARY=1` and
`ALOJAN_SUMMARY_EVIDENCE_DIR`. The former covers the legacy/shared policy; the latter
runs the same correction/ambiguity corpus through scoped records, the immutable
release, restricted credentials and the separate worker. All use the pinned existing
model/provider. The opt-in fixture waits six seconds in test setup, outside the
production worker deadline, and reports only exception type/HTTP status, never response
bodies. Evidence destinations are checked before call setup/inference; database fixture
setup may already have occurred. These suites are semantic checks, not latency benchmarks,
and remain skipped in routine offline runs. `tests/test_live_summary_configuration.py`
checks evidence preflight and deadline separation without model or database access.
Shared assertions also require faithful verbs, caller/recipient responsibility,
withdrawn-action handling and complete ambiguous quotes, not merely matching nouns.
Consult [current fact-boundary evidence](validation/summary-fact-boundaries-2026-10-26.md)
before treating a previous corpus pass as current acceptance.

Before selecting a diagnostic alternative, inspect account-filtered model eligibility
and current key quota using read-only provider metadata. A public catalog or successful
model-list request does not prove inference access. Treat 403/key-limit errors as
unavailable access, not semantic model failure; stop further inference on an exhausted
key. Do not change billing/privacy policy or enable fallback as a test workaround.
A Mac project connection must not be assumed identical to the Linux connection.

Example (after explicit authorization to use the provider):

```sh
ALOJAN_REAL_OUTPUTS=1 ALOJAN_OUTPUTS_EVIDENCE_DIR=.local/output-acceptance \
ALOJAN_REAL_SUMMARY=1 ALOJAN_SUMMARY_EVIDENCE_DIR=.local/summary-acceptance \
~/.local/bin/uv run --frozen --with httpx==0.28.1 \
  --env-file .local/dev.env --env-file .local/agent.env \
  pytest -q -s --tb=short tests/test_declared_outputs_live.py \
    tests/test_agent_summary_live.py tests/test_managed_summary_live.py
```

`tests/test_http_receiver.py` needs only the disposable DB env. It starts an ephemeral
loopback HTTPS receiver, creates an ephemeral trusted certificate, and substitutes
only socket routing/trust and DNS answers in the test. The production HTTP client,
TLS hostname validation, scoped grant/finalization, delivery and persistence are real.
No production SSRF bypass or extra deployment service is added. No external receiver
gets a POST. This does not certify a customer's receiver or business idempotency.

[Current evidence](validation/real-outputs-receiver-2026-10-26.md) records a failed
expanded summary gate. Do not promote the candidate until that gate passes.


## Scoped summary rate-limit recovery (AGP-08)

The candidate scoped worker retries only explicit provider HTTP 429 failures. It
reuses the fenced processing lease as a durable 60–300 second cooldown, with at most
three total claims. No migration or additional role grant is needed. It creates no
final event/action while deferred and rechecks the pinned connection on every attempt.
Other jobs can proceed. Invalid/over-ceiling Retry-After, authentication failure and
exhaustion finalize as summary failure; cancellation retains existing recovery rules.
This does not add retries to the legacy rollback worker or the live voice turn path.

Run `tests/test_summary_worker.py` and `tests/test_scoped_call_records.py` using the
frozen Linux environment, disposable DB env and test-only httpx 0.28.1. The acceptance
covers cooldown, exhaustion, dates/seconds, revoked credentials, stale claim fencing
and another call proceeding during cooldown. It does not measure provider-wide limits.
[Current evidence](validation/source-fidelity-2026-10-26.md) keeps the summary-quality
gate open; do not activate this candidate yet.


## Coordinated private platform deployment — 2026-10-27

The owner-authorized deployment now includes migrations 0020–0025, current v8-capable
management/agent/worker/web readers, independent MCP discovery/execution identities,
and a matching pinned host voice-preparer runtime. Existing number/release/model/EMA
configuration is preserved. The exact active images, verified health, backup/recovery
receipts and remaining gates are in
[platform rollout evidence](validation/platform-rollout-2026-10-27.md).

Active private configuration remains in the existing in-place background/managed
Compose files and web-preview environment. MCP role files and the exact endpoint
allowlist are referenced from `.local/platform-rollout-20261027/attempt-2/`; preserve
those files and the provider key on host backup. Never sync them to Git or Mac source.
No OAuth provider or production MCP tool grant was automatically created.

### Management MCP development (ADR 0012)

See [service setup](../services/management-mcp/README.md),
[operation matrix](MANAGEMENT_MCP_OPERATIONS.md) and
[current evidence](validation/management-mcp-2026-10-27.md).
Use the primary Linux host for acceptance. Supplemental Mac tests require an
explicit disposable PostgreSQL `ALOJAN_DATABASE_URL`; pytest isolates schemas.
Run `tests/test_personal_tokens.py`, `tests/test_management_mcp.py`,
`tests/test_connection_setups.py` and `tests/test_call_search.py` with the existing
frozen root environment and test-client dependency. The independent transport
uses its own frozen lock. Apply migrations 0027–0029 before the new API and refresh
restricted management grants. Never copy private test environments, token values,
Mac virtual environments or graph caches to Linux. `infra/examples/management-mcp.sql`
contains read-only synthetic PostgreSQL examples; do not seed real token secrets.

## Shared waiting speech and Jev shadow (ADR 0014, VXP-01–06)

The candidate is developed/tested on the primary Linux host; copying source there
is not a live deployment. See [evidence](validation/voice-response-implementation-2026-10-27.md).
Use `response_experience` in the version-checked agent draft through HTTP or MCP;
the frontend exposes the same enable/style/optional text fields. An omitted field
keeps old behavior/digests. See [SQL data example](../infra/examples/response-experience.sql).
Enablement requires preparing a new voice pack, previewing the `waiting` clip,
publishing a new immutable release and passing existing readiness/number-binding
checks. Changing text invalidates old audio. Prepared waiting audio is limited to
five seconds and does not consume the call-time synthesis worker.

Upgrade agent, native gateway, generated contracts, management API/MCP, preparation
worker and frontend together before enabling a release. Reapply `grant_management`
for the serving management role using the existing privileged role setup procedure:
it now needs column-level read access to `utterances.source_generation_id` to derive
transcript kind. No table migration or new service is needed; do not grant table-wide
SELECT/UPDATE. Retain the old release for rollback and preserve all private config.

`ALOJAN_JEV_SHADOW=1` is the managed-runtime default under the owner's 2026-10-27
deployment approval. It enables observation only for runtimes with validated,
published conversational MCP tool grants, using the call's already prepared
workspace credential. A connection without selected tools, Telegram actions and
ordinary non-MCP agents do not trigger requests. `0` disables all Jev observations.
Values other than `0`/`1` fail startup. Never use a global fallback key. Jev cannot speak, execute tools or alter
routing. Roll back by setting `0` and by selecting the prior qualified agent release;
drain/fence calls using existing maintenance procedure before downgrading binaries.

Synthetic-only tools (existing authorized key in the process environment, never
CLI arguments) are `tools/evaluate-response-decisions.py --output <private-path>`
and `tools/benchmark-interim-metadata.py --output <private-path>`. The first sends
only the maintained labeled Turkish fixtures; the second forces synthetic tool
proposals without executing them. Neither establishes real EMA/SIP/handset latency.
Dynamic text/TTS and Jev-driven selection remain inactive until their quality,
latency and GPU isolation gates pass. No fast recipe/planner race is enabled.

### Resident EMA waiting comparison (VXP-01/02)

`tests/sip-integration/test_waiting_ema_live.py` is opt-in and must run inside the
existing exclusive voice-preparer operator window described above. The flag alone
is not a maintenance lock. Hold the preparation advisory lock, verify no active
preparation, stop the idle preparer, reserve `DockerWindow`, keep checking its
identity/gate receipts, and restore/restart only after its successful cleanup.
Use the existing resident TTS endpoint; do not start another GPU model process.

Prepare a synthetic `AgentDraft` with response experience enabled through
`generate_pack` in that window. Store its JSON as `draft.json` and the digest-bound
assets under `pack/` in a new ignored evidence directory. Set
`ALOJAN_WAITING_EMA_WINDOW=1` and `ALOJAN_WAITING_EMA_EVIDENCE` to that absolute
path only for the child pytest process. Run the whole four-case test file with the
existing development DB environment and pinned httpx test dependency. Leave
`ALOJAN_WAITING_EMA_TURNS` unset (14) for reporting; three-turn smoke output is not
accepted by the reporter. Continue window checks until the child exits and verify
all gates/routes, journal removal and preparer health afterwards.

Run `uv run --frozen python tools/report-waiting-ema.py <private-evidence-directory>`
afterwards. It requires all four complete ABBA calls and their expected waiting
segments. Keep raw output and synthetic WAVs ignored; publish sanitized numbers
and limitations. This setup scripts ASR, operations and answers and cannot qualify
production naturalness, barge-in or full-pipeline latency. See
[the first measurements](validation/voice-response-measurements-2026-10-27.md).

### Private MCP endpoint configuration

MCP server endpoints belong in private operator/user configuration, never Git.
The OAuth provider example intentionally leaves endpoint fields empty and must be
filled privately before use. The discovery SQL example requires the psql
`mcp_endpoint` variable. Live Hindsight acceptance requires both explicit opt-in
and `ALOJAN_HINDSIGHT_MCP_URL`; there is no built-in endpoint. Synthetic tests
construct reserved test destinations and mock transport/DNS without deployment defaults.
