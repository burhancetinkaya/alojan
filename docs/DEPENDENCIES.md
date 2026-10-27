# Introduced dependencies

## Management frontend (2026-10-26)

Direct exact versions and transitive integrity hashes are in `services/web/package-lock.json`.
Installed package metadata supplies the license labels below; these are inventory,
not redistribution approval. Preserve upstream copyright/license notices and the
standalone server’s transitive notices when packaging. No project LICENSE was added.

| Dependency | Exact pin / upstream source | Metadata license |
|---|---|---|
| Next.js | 16.4.3; https://github.com/vercel/next.js | MIT |
| React / React DOM | 19.3.1; https://github.com/facebook/react | MIT |
| shadcn component generator | 4.22.1; https://github.com/shadcn-ui/ui | MIT; copied/generated UI components |
| Radix UI | 1.8.1; https://github.com/radix-ui/primitives | MIT |
| Lucide React | 1.61.0; https://github.com/lucide-icons/lucide | ISC; retain icon notices |
| Tailwind / PostCSS adapter | 4.3.3; https://github.com/tailwindlabs/tailwindcss | MIT |
| class-variance-authority | 0.7.1; https://github.com/joe-bell/cva | Apache-2.0 |
| clsx / tailwind-merge | 2.1.1 / 3.6.0; https://github.com/lukeed/clsx / https://github.com/dcastil/tailwind-merge | MIT |
| TypeScript | 5.9.3; https://github.com/microsoft/TypeScript | Apache-2.0 |
| Playwright | 1.64.1; https://github.com/microsoft/playwright | Apache-2.0; browser binaries have additional notices |
| Type declarations | Node 22.20.5 / React 19.3.0 / React DOM 19.3.0; https://github.com/DefinitelyTyped/DefinitelyTyped | MIT |
| Prettier (one-off formatting) | 3.8.3; https://github.com/prettier/prettier | MIT; not shipped in runtime |

Node 22.23.1 Bookworm-slim and Playwright 1.64.1 Noble image digests are pinned
in the frontend Dockerfile/test harness. Private TLS reuses Nginx 1.28 Alpine at
a pinned digest in `infra/compose.web.yaml`; Nginx uses the 2-clause BSD license.
Node, browser, Debian/Ubuntu/Alpine and bundled OpenSSL packages require their own
release inventory. No external font, analytics, media CDN or new GPU dependency.
The shadcn generator ran once; its generated components use the existing `cn`
helper and were adapted for flat styling and bounded textareas.

Reference setup: https://ui.shadcn.com/docs/installation/next and
https://nextjs.org/docs/app/getting-started/installation.


Telegram delivery directly pins **httpx2 2.16.0**, already present transitively in the
worker/root OpenAI Agents lock. Installed metadata identifies
[source](https://github.com/pydantic/httpx2) and BSD-3-Clause; preserve its notices and
review redistribution separately. Its pinned httpcore2 2.16.0 transport supports the
SNI hostname extension used to retain certificate verification while connecting to a
vetted IP literal. Client retries default to zero, ambient proxies/redirects are disabled,
and HTTP log propagation is suppressed because Bot API paths contain credentials.
No new HTTP framework/server or GPU dependency was introduced. Telegram receipt/error
interpretation follows [sendMessage](https://core.telegram.org/bots/api#sendmessage) and
[ResponseParameters](https://core.telegram.org/bots/api#responseparameters); real service
acceptance remains separate from synthetic tests.

Provider credentials reuse cryptography **50.0.2**, already pinned in the development
lock and now declared directly in management/action-worker projects. Source:
https://github.com/pyca/cryptography. Installed package metadata declares
`Apache-2.0 OR BSD-3-Clause`; retain its bundled OpenSSL/third-party notices and review
redistribution before release. Fernet supplies authenticated encryption; application
envelopes bind workspace/reference/provider, with the key outside PostgreSQL.
This is not a new custom cipher or a license-approval claim. The separate worker pins
openai-agents 0.24.0, psycopg 3.2.6 and pydantic 2.14.1; complete transitive versions/
hashes are in services/action-worker/uv.lock. Its image reuses the existing pinned
Ubuntu/Python/uv foundation, installs no GPU/media runtime and is independently built.

These pins describe the local foundation; they do not approve distribution or claim
unmeasured model compatibility. Linux foundation/GPU smoke evidence is recorded separately. The project license remains pending.

| Dependency | Pin/source | License / use |
|---|---|---|
| PJSIP | 2.16 source archive; SHA-256 `3af2e481d51aaa095897820fa2ee26c30e530590c6ca56d23e4133bbdad369eb`; https://github.com/pjsip/pjproject/tree/2.16 | GPL-2.0-or-later / commercial; local native gateway |
| PostgreSQL | 17.4-bookworm image at `sha256:304ab813518754228f9f792f79d6da36359b82d8ecf418096c636725f8c930ad` | PostgreSQL license; image/base packages need release inventory |
| grpcio / grpcio-tools | 1.78.0, PyPI hashes in uv.lock | Apache-2.0; Python contract generation/runtime |
| gRPC C++ | 1.78.0, revision `5e6ba94242b92e363220bc2163d55ce3554d4ecc`; https://github.com/grpc/grpc | Apache-2.0; native transport, protoc plugin; see transitive pins below |
| protobuf | 6.33.5, uv.lock | BSD-3-Clause; message runtime |
| psycopg / psycopg-binary | 3.2.6, uv.lock | LGPL-3.0; PostgreSQL client and bundled libpq review needed |
| Python | 3.12 series; locally resolved 3.12.13 | PSF; uv-managed environment |
| CMake / Ninja | 3.31.6 / 1.11.1.3, uv.lock | BSD-3-Clause / Apache-2.0; build tooling |
| pytest / Ruff | 8.3.5 / 0.11.2, uv.lock | MIT; test/lint tooling |
| clang-format / pre-commit | 20.1.8 / 4.2.0, uv.lock | LLVM with exceptions / MIT; development tooling |

PJSIP's bundled SRTP, resampler and codecs are covered by upstream third-party
notices and must be included in a release inventory. The local build disables
sound-device capture, video, OpenSSL/TLS and optional external codecs; it is not a
production trunk build. Only PCMA/PCMU are enabled at runtime. Review upstream
security updates and transitive terms before release; these reproducible pins do
not imply that all dependency vulnerabilities have been audited.

Gateway development follows [PJSUA2 calls](https://docs.pjsip.org/en/latest/pjsua2/using/call.html)
and [audio media](https://docs.pjsip.org/en/latest/pjsua2/using/media_audio.html).

## Native gRPC source closure

`scripts/build-grpc.sh` verifies the gRPC revision and initializes only the required
gitlinks. These are the exact source pins used by that revision, not separately
floating release tags. Generated C++ uses protobuf 6.31.1 / protoc 31.1. The native
runtime and all native dependencies compile as C++20. Installation stays local.

| Source | Revision | License notice |
|---|---|---|
| https://github.com/abseil/abseil-cpp | `76bb24329e8bf5f39704eb10d21b9a80befa7c81` | Apache-2.0 |
| https://github.com/google/boringssl | `c63fadbde60a2224c22189d14c4001bbd2a3a629` | Apache-2.0 plus bundled third-party notices |
| https://github.com/c-ares/c-ares | `d3a507e920e7af18a5efb7f9f1d8044ed4750013` | MIT |
| https://github.com/protocolbuffers/protobuf | `74211c0dfc2777318ab53c2cd2c317a2ef9012de` | BSD-3-Clause |
| https://github.com/google/re2 | `0c5616df9c0aaa44c9440d87422012423d91c7d1` | BSD-3-Clause |
| https://github.com/madler/zlib | `f1f503da85d52e56aae11557b4d79a42bcaa2b86` | Zlib |

The build follows the [upstream CMake instructions](https://github.com/grpc/grpc/blob/v1.78.0/BUILDING.md).
Keep upstream license/copyright notices and bundled third-party notices when
distributing these libraries. This source inventory is not a complete release
SBOM or approval of the still-pending project license. Test transport is insecure
loopback only; building TLS support does not configure production authentication.

## Linux development host additions (U0-01)

AGP-02 management packaging reuses the root lock's existing Starlette 1.9.0,
Uvicorn 0.54.0, Pydantic 2.14.1 and psycopg[binary] 3.2.6 as direct, frozen
application dependencies in `services/app-api/uv.lock`. Upstream sources:
[Starlette](https://github.com/Kludex/starlette),
[Uvicorn](https://github.com/Kludex/uvicorn),
[Pydantic](https://github.com/pydantic/pydantic), and
[psycopg](https://github.com/psycopg/psycopg).
Preserve their license and bundled notices in the release inventory; independent
distribution/security review is pending. No new inference dependency is introduced.
The separate management Dockerfile reuses the live baseline's digest-pinned
Ubuntu 24.04 and uv 0.11.9 images and pinned Python/CA packages. Hashing uses
Python/OpenSSL scrypt rather than an additional authentication framework.

- uv 0.11.9: [upstream release](https://github.com/astral-sh/uv/releases/tag/0.11.9),
  `uv-x86_64-unknown-linux-gnu.tar.gz` verified against its published SHA-256;
  per-user tooling, MIT/Apache-2.0.
- NVIDIA Container Toolkit, toolkit-base, libnvidia-container-tools and
  libnvidia-container1: all `1.20.1-1`, signed NVIDIA APT packages.
  Sources: [toolkit](https://github.com/NVIDIA/nvidia-container-toolkit) and
  [libnvidia-container](https://github.com/NVIDIA/libnvidia-container), Apache-2.0
  with upstream third-party notices; host tooling only.
- CUDA smoke image: `nvidia/cuda:12.4.1-base-ubuntu22.04` at
  `sha256:0f6bfcbf267e65123bcc2287e2153dedfc0f24772fb5ce84afe16ac4b2fada95`.
  [Upstream image sources](https://gitlab.com/nvidia/container-images/cuda),
  NVIDIA CUDA terms and Ubuntu/base-package licenses require release review.
  This diagnostic image is not an approved production inference image.

The host's existing CUDA compiler 12.4.131, NVIDIA driver 550.120 and GCC 13.3.0
were inspected and retained, not newly installed. The CUDA kernel smoke does not
establish PyTorch, faster-whisper or EMA readiness. No model dependency was added
during that smoke step; the separately authorized EMA tooling is recorded below.

## M1 speech-fixture generator (offline tooling only)

The optional generator uses [eSpeak NG 1.51](https://github.com/espeak-ng/espeak-ng/tree/1.51),
Ubuntu amd64 package `1.51+dfsg-12build1`, GPL-3.0-or-later plus upstream/package
notices. Package SHA-256:
`ffeac730f1f43b5cdbca708a8215d6b7310bf3bd40d7dcf0affd6a62f86aa6df`.
The executable is extracted under `.local/prompt-tools`, with no system installation;
existing `libespeak-ng1`/`espeak-ng-data` of the same version are retained. CPython
3.12.3's PSF-licensed `audioop.ratecv` performs offline fixture conversion. Runtime
builds/tests use the checked-in WAVs and do not depend on eSpeak. This does not
replace DEC-09/EMA or establish speech-model readiness. See
[fixture provenance and release limitations](../assets/prompts/tr-v1/README.md).

## Offline EMA generation (M1-03 / limited M2-02)

[ADR 0004](ADR/0004-ema-prompt-validation.md) authorizes real CUDA generation of
replacement prompts after the owner rejected the formant audio. The isolated
`tools/ema-prompts/uv.lock` pins all 40 resolved packages with artifact hashes;
this is separate from the root environment and is not a production service image.

| Component | Exact pin / source | Upstream license / release action |
|---|---|---|
| EMA Lightning code | 1.1.2, [PyPI](https://pypi.org/project/ema-lightning/1.1.2/); wheel SHA-256 `821c737587d2db32f83a863abadd455610720d359872f6fb8b08ddd1c9b84840` | Apache-2.0; keep the packaged license and notices |
| EMA model weights | [revision e7c96f2fc0ba843cd0f86e02786655bb56f50df8](https://huggingface.co/canberkkkkkk/ema-lightning/tree/e7c96f2fc0ba843cd0f86e02786655bb56f50df8) | Model card declares Apache-2.0; review model and generated-output distribution separately |
| PyTorch | 2.6.0+cu124, [official CUDA 12.4 wheels](https://pytorch.org/get-started/previous-versions/) | BSD-style license plus third-party notices; CUDA/cuDNN/NCCL packages have separate NVIDIA terms |
| normalizer-tr | 0.8.0, [source](https://github.com/erdemtuna/normalizer-tr) | Apache-2.0; preserve notices |
| huggingface-hub | 2.3.0, [source](https://github.com/huggingface/huggingface_hub) | Apache-2.0; transitive transport dependencies in the lockfile |
| NumPy | 2.5.4, [source](https://github.com/numpy/numpy) | Wheel metadata: BSD-3-Clause, 0BSD, MIT, Zlib and CC0-1.0; preserve bundled notices |

Checkpoint SHA-256 values are verified before loading:

- `ema.pt`: `95aec03dafbe0e1d69bca774ab597c779464729a14bc99bfcb52480090c7dfe6`
- `decoder.pt`: `9595819b173f411340f63d11332695121a97f8bf1f6d8b6fef0b21cf99c7ad67`

The pinned PyTorch CUDA 12.4 build is selected for the existing 550.120 host driver;
no host driver or shared service upgrade is included. The wheel and model pins
establish reproducibility, not a security audit or release approval. Retain the
full transitive package/license inventory before distributing an environment.
The project LICENSE decision remains with the owner.

## Native ASR worker (M2-01)

The isolated `services/asr/uv.lock` contains the exact resolved package artifacts
and SHA-256 values. It does not alter the root development or EMA environments.

| Component | Pin / source | License / release action |
|---|---|---|
| faster-whisper | 1.2.1, [upstream](https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1) | MIT; retain notices |
| CTranslate2 | 4.6.0, [upstream](https://github.com/OpenNMT/CTranslate2/tree/v4.6.0) | MIT; native inference engine and bundled dependencies need release inventory |
| standard large-v3 conversion (default) | [Systran model at edaa852ec7e145841d8ffdb056a99866b5f0a478](https://huggingface.co/Systran/faster-whisper-large-v3/tree/edaa852ec7e145841d8ffdb056a99866b5f0a478) | Model card declares MIT; owner-selected standard Whisper large-v3, CUDA float16; pinned file checksums in `services/asr/model.json`; redistribution not approved |
| large-v3-turbo conversion | [dropbox-dash model at 0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo/tree/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf) | Model card declares MIT; conversion of OpenAI Whisper large-v3-turbo in float16, not a smaller-model substitution |
| grpcio-health-checking | 1.78.0, [gRPC source](https://github.com/grpc/grpc/tree/v1.78.0/src/python/grpcio_health_checking) | Apache-2.0; standard model-readiness endpoint |
| PyAV | 19.0.2, [source](https://github.com/PyAV-Org/PyAV) | BSD-3-Clause; bundled FFmpeg/component licenses require separate review |
| ONNX Runtime | 1.31.0, [source](https://github.com/microsoft/onnxruntime) | MIT; upstream dependency, model VAD is disabled in this worker |
| tokenizers | 0.23.3, [source](https://github.com/huggingface/tokenizers) | Exact wheel metadata omitted a license field; upstream/license bundle review remains required |
| NVIDIA cuBLAS / cuDNN | 12.4.5.8 / 9.1.0.70, locked PyPI artifacts | NVIDIA proprietary redistribution terms; retain package agreements, no project-license approval implied |

Shared pins: grpcio 1.78.0, protobuf 6.33.5, NumPy 2.5.4 and huggingface-hub 2.3.0.
The CUDA 12/cuDNN 9 requirements are documented by
[faster-whisper](https://github.com/SYSTRAN/faster-whisper#gpu). This pin was tested
with the existing 550.120 driver and RTX 4080; host packages were not upgraded.
The standard large-v3 model binary SHA-256 is
`69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1`;
all five model-file checksums are enforced by `services/asr/model.json` at startup.
The earlier Turbo profile used the `mobiuslabsgmbh` model URL, which redirects
to `dropbox-dash`; its immutable pin remains in Git history for rollback.
This inventory establishes reproducibility and observed runtime compatibility,
not a security audit or blanket distribution clearance.

### M2-02 persistent EMA environment

`services/tts/uv.lock` carries forward every version from the offline EMA lock
(EMA Lightning 1.1.2, torch 2.6.0+cu124, normalizer-tr 0.8.0 and CUDA 12.4 libraries)
and adds the already-used grpcio/grpcio-health-checking 1.78.0 and protobuf 6.33.5.
No host driver, CUDA toolkit or shared service was upgraded. It uses the same
pinned model revision/weight hashes as the accepted prompts; the config is also
verified with SHA-256 `27546c470dd4e86d9ab8172fd1c85c45a4bffdf52d9ccb3f511c4b0c3ae38241`.
Normal startup is offline. Existing upstream/license and redistribution caveats
continue to apply; this task does not approve a project license or redistribution.

The service adapter depends on EMA 1.1.2's private request/playhead interfaces
solely to bound its otherwise unbounded output queue and drain cancelled work.
Keep the version pinned and rerun lifecycle, numerical and GPU checks before any
upgrade; remove the adapter when equivalent public backpressure hooks exist.

## Native CPU turn detection (M3-01)

No new service or FFT package is introduced. Native ONNX Runtime reuses the locked
1.31.0 wheel from ASR or the separate CPU-only evaluation environment. Headers are
pinned to upstream revision `402979ac1bef89dcd55add41eaa7277c407599eb` (v1.31.0);
`scripts/prepare-turn-models.py` contains and verifies all six header SHA-256 values.
Retain the upstream MIT license and third-party notices before redistribution.

| Artifact | Immutable source / SHA-256 | License and use |
|---|---|---|
| Silero VAD v6.2 ONNX | [source](https://github.com/snakers4/silero-vad/tree/be95df9152c0d7618fa1edfeb296fc3dae32376f); `1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3` | MIT upstream; CPU VAD, not ASR |
| Smart Turn v3.2 CPU ONNX | [model revision](https://huggingface.co/pipecat-ai/smart-turn-v3/tree/f766f81d3cfdf7737ac64aad813d91bbfd56bf93); `2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f` | BSD-2-Clause model card; CPU dynamic int8, preserve model/code notices |
| Smart Turn reference | [code revision](https://github.com/pipecat-ai/smart-turn/tree/4786657e242dfe77dd138699ac564ee074a2a543) | BSD-2-Clause; eight-second left-pad/normalize feature interface |
| Speex/Kiss FFT | Existing PJSIP 2.16 archive pin above, `third_party/speex` | Bundled BSD-style notices; reuse existing floating-point native library, include bundled notices in release inventory |
| Transformers reference frontend | 4.51.3, [source](https://github.com/huggingface/transformers/tree/v4.51.3), `tools/turn-eval/uv.lock` | Apache-2.0; offline numerical calibration only, not runtime orchestration |

The native frontend implements 16 kHz, 400-point periodic Hann, 160-sample hop,
center-reflection padding and 80 Slaney-normalized mel filters; reference links
and notices identify the algorithm provenance. `tools/turn-eval/uv.lock` pins
NumPy 2.5.4, ONNX Runtime 1.31.0, Transformers 4.51.3 and their full resolved closure.
This environment does not install Torch or replace either CUDA worker environment.
Model checksums and numerical agreement do not approve public distribution or
complete the pending project/transitive license review.

## M4 agent additions

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python), `openai-agents==0.24.0`, MIT.
- [OpenAI Python client](https://github.com/openai/openai-python), `openai==3.37.0` in the lockfile, Apache-2.0.
- MCP and validation dependencies are transitive and fully locked with hashes in
  root and `services/agent/uv.lock`; their license/notice review remains part of
  release preparation. Preserve upstream notices; no project license is adopted.
- OpenRouter endpoint and exact model choice are in ADR 0005. API service terms
  and data policies are separate from SDK redistribution licenses.

## Optional Nemotron ASR evaluation/runtime (ADR 0008)

`services/asr-nemotron/uv.lock` isolates the candidate from the Whisper/EMA
workers. Direct pins include Transformers 5.13.0 (Apache 2.0), PyTorch
2.6.0+cu124 (BSD-style with separately licensed bundled components), librosa
0.11.0 (ISC), SoundFile 0.13.1 (BSD-style; bundled libsndfile terms apply), and
the existing pinned gRPC/protobuf interface. CUDA component redistribution terms
remain separate; this record is not a blanket license approval.

[NVIDIA Nemotron 3.5 ASR](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b)
revision `ea30d66debe3740a08b573244286791d423d6b3e` uses OpenMDW 1.1. Runtime verifies
all six required files against `services/asr/nemotron.json`. No remote repository
code execution or NIM/API service is used. Weights remain local and uncommitted.

The evaluation-only FLEURS corpus is CC BY 4.0; exact conversion revision, artifact
hash and attribution are in `tools/asr-compare/README.md`. PyArrow 19.0.1 (Apache
2.0) is used only to prepare this local corpus, not by the recognition worker.


## Optional offline denoising evaluation (2026-10-24)

These are evaluation-only dependencies, not linked into the shipping gateway.
[The build recipe](../tools/denoise-compare/build.sh) pins source/package SHA-256
values; [the comparison README](../tools/denoise-compare/README.md) records sources
and reproduction. Retain upstream notices for any later distribution; review
remains separate from this experiment and no project license is introduced.

| Dependency | Pin | Declared terms / use |
|---|---|---|
| WebRTC AudioProcessing | 2.1 source archive | BSD-style LICENSE and PATENTS; CPU C++ suppression |
| Abseil | 20240722.0, upstream wrap patch revision 3 | Apache-2.0; hashes checked by Meson wrap |
| RNNoise | v0.2, model 0b50c45 | BSD-3-Clause; CPU C library called by the C++ probe |
| SpeexDSP | 1.2.1-1ubuntu3 amd64 dev/runtime packages | BSD-style notices; privately extracted, noise suppression and resampling |
| Meson / Ninja | 1.7.0 / 1.11.1.3 | Apache-2.0; isolated build environment |
| DTLN original ONNX models | breizhn/DTLN `1de1f15a8b5b7e1c44905618ff2ef70ca8277fbc` | Upstream MIT; both hashes checked in `tools/denoise-compare/dtln.py`; evaluation only |

DTLN reuses ONNX Runtime 1.31.0 (MIT), CPU provider, and existing NumPy 2.5.4.
No LiveKit package or new live dependency is introduced. The upstream notice is
retained in `tools/denoise-compare/DTLN-NOTICE.txt`; review model redistribution
separately before publishing a bundle.

## Voice preparation host runtime

`services/voice-preparer/pyproject.toml` and its lock reuse the already pinned
versions of psycopg 3.2.6, pydantic 2.14.1, grpcio 1.78.0, protobuf 6.33.5 and
cryptography 50.0.2 (indirect management configuration import). No torch/CUDA/model
package is installed in this CPU coordinator; inference stays in the retained TTS
image. Existing upstream/license records apply; this adds no license-approval claim.

## MCP discovery compatibility (2026-10-26)

AGP-07 reuses **mcp 2.3.0**, **mcp-types 2.3.0**, **jsonschema 4.26.0** and
**httpx2/httpcore2 2.16.0**, already present at exact versions/hashes in the root and
action-worker frozen locks. No new package or model dependency is introduced.
Installed metadata identifies MCP and jsonschema as MIT; retain upstream notices
and review redistribution separately. Sources: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
[jsonschema](https://github.com/python-jsonschema/jsonschema).

The implemented discovery subset is pinned to protocol **2025-11-25**:
[Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
and [tool discovery](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).
The installed v2 SDK accepts a supplied httpx2 client and uses snake_case typed fields;
transport tests exercise its actual JSON/SSE handshake and pagination. Its automatic
same-origin redirect behavior is additionally blocked at Alojan's transport layer.
OAuth, external references, tool execution and automatic capability approval are
not provided by this discovery slice. No unreviewed license is claimed approved.

AGP-07 selection additionally pins the existing **jsonschema 4.26.0** validator in
`services/app-api/pyproject.toml` and its frozen lock. Transitive pins are attrs
26.1.0, jsonschema-specifications 2025.9.1, referencing 0.37.0 and rpds-py 2026.9.1.
Their hashes are recorded in that lock; existing root/action-worker dependencies
are unchanged. This reuses the installed validator rather than introducing a custom
JSON Schema implementation. The management image gains schema validation only;
voice-preparer imports remain independent. Upstream sources/notices must accompany
redistribution; no additional license approval is claimed.


AGP-07 OAuth adds a direct **httpx2 2.16.0** pin to the management project, reusing
the root/action-worker version. Its frozen lock records **httpcore2 2.16.0**,
**httpx2-jsfetch 1.0** (Emscripten only) and **truststore 0.10.5** plus their dependency hashes. No SDK,
framework or voice/model dependency is added. Inspect installed distribution metadata
and upstream notices before redistribution; this change does not grant license approval.
The DNS-pinned transport is shared between discovery and management OAuth requests.

Installed frozen-image metadata identifies httpx2/httpcore2 as BSD-3-Clause and
truststore as MIT. Sources: [httpx2/httpcore2](https://github.com/pydantic/httpx2)
and [truststore](https://github.com/sethmlarson/truststore). Preserve these license
and copyright notices in redistributed images; approval is still separate.

## Management MCP service (2026-10-27)

MCP-01–03 adds an independent frozen service lock, reusing installed versions:
**mcp 2.3.0**, **httpx2 2.16.0**, **starlette 1.9.0**, **uvicorn 0.54.0** and
**jsonschema 4.26.0**. Installed distribution metadata identifies MCP/jsonschema
as MIT and httpx2/Starlette/Uvicorn as BSD-3-Clause. Sources are the
[MCP SDK](https://github.com/modelcontextprotocol/python-sdk),
[httpx2](https://github.com/pydantic/httpx2),
[Starlette](https://github.com/Kludex/starlette),
[Uvicorn](https://github.com/Kludex/uvicorn) and
[jsonschema](https://github.com/python-jsonschema/jsonschema).
Preserve copyright/license notices in redistributed images; no new license approval
is claimed. No model/GPU package is added. Direct pins and all transitive hashes are
in `services/management-mcp/pyproject.toml` and `uv.lock`; base/runtime images are
pinned in its Dockerfile. HTTP tests explicitly exercise protocol 2025-11-25 and
also initialize through the installed official SDK client. Real cloud clients
remain a separate acceptance gate.
