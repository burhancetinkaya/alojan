# Bootstrap validation — 2026-10-09

Environment: macOS authoring checkout; user date/timezone Europe/Istanbul.
Branch: `codex/agentic-bootstrap`.
Base: `a59675e9806e6fbe09cb4b8c3725ec89a7a27716`.
Scope: PRE-01/PRE-02 complete; PRE-03 documents delivered, owner plan approval pending. Changes are local and uncommitted; no push, published PR, or merge.

Historical note: the initial source-copy checks below describe bootstrap before the owner requested removal of the source brief. The repository now uses `docs/REQUIREMENTS.md`; no copy of the source brief is required for development.

## Results

- PASS: branch created from the inspected local main; main revision unchanged.
- PASS: Ponytail installed by bundled skill-installer at the recorded upstream commit; installed SHA-256 matches DEV_SETUP.
- PASS: PRD byte-for-byte comparison with the supplied source. SHA-256: `8da7548f9302bb220179a0db65811806e0ecb1220286d09ac6ab36c3b3de899e`.
- PASS: relative Markdown file links resolve across authored documents (original PRD excluded from rewriting).
- PASS: authored Markdown trailing-whitespace check and `git diff --check` for tracked modifications. The original PRD retains its intentional Markdown line breaks.
- PASS: ignore rules cover sample local credentials and packet captures while allowing `.env.example`.
- PASS: preparation review maps US-01–09 to tasks, retains DEC-01–15, and records EXT-01–08 as unresolved gates.
- PASS: no project LICENSE adopted; proposed GPL-3.0-or-later requires a separate owner decision.

## Not run

No application tests, build, CI job, Ubuntu SSH session, GPU inference, API smoke request, carrier call, iOS forwarding, or graph source indexing ran. There is no application source to build or index. No private reporting channel has been verified. Exact runtime dependency versions and redistribution inventory remain M0/M2 work.

## Recheck

Use `git branch --show-current`, `git rev-parse main`, `git diff --check`, requirements coverage against the technical baseline, and SHA-256 of the installed skill. Resolve local Markdown file targets against each document directory. Run `git check-ignore --no-index` against synthetic secret/capture paths and confirm example templates are not ignored. These checks validate preparation only, never G0–G7.

## Source brief removal follow-up

At the owner's request, removed the untracked source brief from the repository after extracting the remaining technical details into `docs/REQUIREMENTS.md`. Updated active instructions and links. The original outside the repository is unchanged.

Validated all 15 decision IDs, 9 acceptance IDs, 18 section numbers, exact protobuf field definitions, seven persistence tables, and local Markdown file links. Reviewed the retained thresholds, agent/tool policy, performance targets, API/events and external gates. Application tests remain not run: this change only updates documentation.

## macOS development plan revision

The owner approved adapting initial development to macOS while Ubuntu is unavailable. ADR 0002 amends DEC-01 and the carrier prerequisite for local M2–M5 development. Updated agent rules, task dependencies, development setup, requirements, README and gate register. G0/G1 now distinguish local and Ubuntu evidence; U0-01 handles deferred server validation.

PASS: relative file links and authored Markdown whitespace checks; reviewed removal of the Ubuntu/Netgsm prerequisite from local development tasks. No application code, build or runtime test was executed; all runtime gates remain not run. This is approval of the plan revision, not a claim of tested Mac compatibility.
