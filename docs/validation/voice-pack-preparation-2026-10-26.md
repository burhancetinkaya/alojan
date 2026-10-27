# Candidate voice pack prepared from deployed EMA artifacts

Date: 2026-10-26. Ponytail full; ADR 0003/0011, AGP-02/03/09,
M2/M4/M5, requirements §11.2/12. No live activation or performance acceptance.

## Source and resulting package

Inspected the running gateway image's launcher: `scripts/run-netgsm.sh` selects
`assets/prompts/tr-v5-kubra`. Its two text files, two WAVs and legacy manifest match
the retained repository files byte-for-byte. Source manifest SHA-256:
`c3b18c88a0c35cb4f1ab575c69a6ad12cbcfe0d7cc4f92a002470b89168fa116`.
Existing provenance records resident EMA synthesis with model revision
`e7c96f2fc0ba843cd0f86e02786655bb56f50df8`; this turn did not regenerate audio.

The candidate greeting differed only in a straight versus curly apostrophe in the
owner's genitive form. Updated that single editable field through the restricted
profile application method, producing candidate draft v2. All other draft fields,
including full instructions, tools, model and Telegram references, compare equal.
The earlier private owner-state file remains a historical v1 record; subsequent
work must use `.local/voice-preparation-20261026/owner-state.json` on Linux.

The new operator `alojan.voice_pack` command validates trusted legacy metadata,
original text hashes, exact stripped spoken text, model revision, audio hashes,
sample count, PCM16/mono/8 kHz format, 20 ms alignment, duration, non-silence and
greeting padding. Paths are fixed and bounded regular-file reads reject symlinks.
Only after validation does it use the existing immutable scoped installer. No
audio is synthesized, resampled, trimmed or rewritten. Source hashes prove integrity;
operators remain responsible for provenance. Untrusted uploads cannot establish it.

| Asset | Duration | SHA-256 |
|---|---:|---|
| Greeting | 5360 ms, including 400 ms silence | `6b3451931fe830dabadadf4617907586f7403049b7c074cbdae2b21ccc036189` |
| Unavailable | 4000 ms | `b0d128fcafd2b3da17aef73fea48462108cd805e93a8303a946873f37bf9be18` |

Both WAVs are byte-identical to the resident gateway's files. New release-format
speech digest: `239fda312f2fb34a6df99c3750aaeda500c1cdd9d9aafb822f2716b6e7e379b5`.
Manifest digest: `f941f1b814fb823393f1742bf2a331ec6149e2a5e44ebf6e018603ac608b5325`.
Private staging is `.local/voice-preparation-20261026/voice-store/` on Linux,
with workspace/speech-digest subdirectories. Private draft/preset snapshots and
the exact owner/profile/path mapping are retained alongside it.

## Validation and limits

Primary Linux `test_voice_pack.py`, `test_agent_releases.py` and
`test_prepared_releases.py`: **49 passed in 8.95 seconds**, zero skips/failures.
Coverage includes byte-preserving repeat installation, separate workspace paths,
changed identity, mismatched text/audio/revision/sample count/padding/rate, duplicate
entries, path substitution and symlink rejection, plus existing release/cache checks.
The initial format check requested formatting for both new files; formatted them,
then Ruff and tests passed. No guard or model qualification was relaxed.

Candidate profile mutation/package validation passed using the restricted management
role and existing application methods. Temporary login was revoked. Candidate
database still contains zero prepared asset rows, releases, grants, bindings and
action jobs. Model qualification remains disabled. Files are staged for subsequent
qualification/import; file existence does not make an agent ready for calls.

The management image was rebuilt for the new operator module. Its CLI help and full
candidate package conversion both passed with network=none, read-only root, dropped
capabilities, 0.5 CPU/512 MiB/64 PIDs and no GPU. Image identity:
`sha256:31e099acf447fa9b4250a2f013da4406f4d3f503c7a8000efee691782a4d92d2`.
Source checksums match Mac/Linux; private Linux result files retain the details.
All seven resident containers remain healthy with their original 2026-10-24 start
times. The graph was refreshed without persisted artifacts. No new HTTP listener, model
process, carrier call, external send, production schema update or route change.

Exact reuse needs no GPU reservation or call interruption. New synthesis and matched
real inference remain pending an explicit maintenance fence. Inspection confirmed
that SIGTERM drains for at most two seconds before shutdown, so it is not a safe
long-call drain. The capacity plan's zero-admission reload is still a design. Do not
substitute a one-time idle observation or use synthetic tests as real inference
qualification. No new listening acceptance or PERF-01–06 result is claimed.
