# Contributing to Alojan

Alojan has a local foundation, but no production release or selected project license yet. Read [the license proposal](docs/LICENSING.md) before contributing code intended for redistribution. Do not assume this repository currently grants open-source reuse rights.

Start with [technical requirements](docs/REQUIREMENTS.md), [agent rules](AGENTS.md), [development setup](docs/DEV_SETUP.md), and [task plan](docs/PLAN.md). Discuss scope changes before implementation; use existing task IDs in issues and PRs. The owner has authorized development/build/test on the Linux GPU server under ADR 0003; follow the task status and separate hardware/carrier gates.

## Making a change

1. Create a focused branch from the agreed base, using `codex/<topic>` for agent work. Never edit `main` directly.
2. Keep changes small and cohesive. Reuse existing code and dependencies; justify new dependencies and record their licenses and exact versions.
3. Write code, comments, commits, and maintained docs in English. Preserve the maintained requirements; Turkish speech fixtures belong in the product tests.
4. Add relevant behavioral/regression tests and update the affected docs. Use synthetic or explicitly consented, anonymized fixtures.
5. Inspect the diff and run available checks. Report skipped checks and unavailable infrastructure, not fabricated results.
6. Submit a PR when publication is authorized. Include task/requirements references, the problem and result, test evidence, and limitations. Await review before merging.

Use descriptive commit subjects such as `fix: discard cancelled audio generations`. Avoid unrelated formatting. Generated protobuf code must be reproducible from pinned tools and reviewed together with its source.

## Checks by stage

Run the commands in DEV_SETUP for the changed components. For prose-only changes, check relative links, requirements coverage, `git diff --check`, and document consistency.

The local foundation includes clang-format, Ruff, CTest/pytest and Python protobuf generation checks. clang-tidy and cross-language streaming checks remain pending. Linux CI must run without production credentials. GPU and live carrier checks belong on the authorized Ubuntu host, with a sanitized evidence report; do not expose that host as a public-fork CI runner.

Follow [the code of conduct](CODE_OF_CONDUCT.md). Report vulnerabilities according to [the security policy](SECURITY.md), without public exploit details or personal data.
