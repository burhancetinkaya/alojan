# License recommendation and dependency review

Date: 2026-10-09. Status: **proposal for owner approval; no Alojan license adopted**.

## Recommendation

Recommend **GPL-3.0-or-later** for original Alojan code, subject to checking the exact dependency/build inventory before a distributable release. This is an engineering recommendation, not a completed legal clearance.

PJSIP offers GPL-2.0-or-later or an alternative proprietary license. Its published terms require a combined program to comply with GPL, with specific linking exceptions and additional third-party requirements. A permissive license on Alojan alone would not remove those obligations. [PJSIP licensing](https://docs.pjsip.org/en/2.17/overview/license_pjsip.html)

GPLv3 is the proposed baseline because Apache-2.0 code can be combined into a GPLv3 work, whereas Apache-2.0 and GPLv2-only are incompatible. This does not assert that every separate service or model artifact forms one derivative work; distribution boundaries still need review. [Apache compatibility guidance](https://www.apache.org/licenses/GPL-compatibility.html)

If permissive or closed-source distribution is desired, obtain and review PJSIP's alternative terms and all other licenses before selecting that route. Do not assume service separation or Docker packaging alone resolves obligations. No commercial license has been acquired.

## Initial inventory

These are upstream observations, not a version-pinned redistribution clearance. Pin and verify license files for actual code, weights, transitive libraries and images when introduced.

| Component | Observed upstream license | Action before distribution |
|---|---|---|
| PJSIP/PJSUA2/PJMEDIA | GPL-2.0-or-later / alternative proprietary | Review exact build, linking exceptions, bundled codecs and source/notice obligations |
| [EMA Lightning model](https://huggingface.co/canberkkkkkk/ema-lightning) | Model card declares Apache-2.0 | Review selected code/weights revisions and text-frontend dependencies; retain notices |
| [Smart Turn](https://github.com/pipecat-ai/smart-turn/blob/main/LICENSE) | BSD-2-Clause | Preserve copyright/license/disclaimer; verify selected v3.2 artifact |
| [Silero VAD](https://github.com/snakers4/silero-vad/blob/master/LICENSE) | MIT | Preserve notice; verify ONNX artifact provenance |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) | MIT | Verify CTranslate2, model weights and bundled components separately |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python/blob/main/LICENSE) | MIT | Preserve notice; hosted API use is governed separately by service terms |
| [Ponytail](https://github.com/DietrichGebert/ponytail/blob/9cc65d03aa2da1db7121b912d03596409ee340b8/skills/ponytail/SKILL.md) | MIT | Local development tool only; source revision in DEV_SETUP |
| gRPC/protobuf, PostgreSQL, ONNX Runtime, CUDA/cuDNN/PyTorch, base images and remaining tooling | Exact versions and terms not yet reviewed | M0/M2 inventory must record source, revision, SPDX identifier where applicable, notices and redistribution conditions |

## Approval and release steps

1. Owner accepts or rejects the proposed project license independently of the implementation plan.
2. If accepted, add the exact license text, SPDX metadata and contributor guidance in a dedicated change; preserve third-party licensing independently.
3. Before release, review actual binaries/images/models, provide required notices and corresponding source/build material as applicable, and resolve proprietary-runtime redistribution terms.
4. Until then, README must state that no project license is selected. Do not market the repository as already licensed open source.
