# Linux caller identity validation — 2026-10-23

Tasks: M1-04 and its M1-05 local SIP coverage. Requirements: US-03, sections 6/14;
gates G1-Ubuntu supporting evidence, G2/G6 still not run. Tester: Codex, under the
owner's ADR 0003 Linux authorization. Date: 2026-10-23, Europe/Istanbul.

Source: `codex/caller-identity`, uncommitted changes on baseline
`a59675e9806e6fbe09cb4b8c3725ec89a7a27716`, retaining the prior foundation and
SIP-isolation work. No push, PR, merge or release. Mac is the editing copy; all
builds/tests in this report ran at `~/ai/alojan` on Ubuntu 24.04.2 x86_64, GCC 13.3.0,
Python 3.12.3, pinned PJSIP 2.16 and the frozen uv environment. GPU was not exercised
by this task; earlier CUDA smoke evidence is separate.

## Behavior exercised

- Native INVITE handling copies normalized caller/redirect identities into isolated
  session-owned records. PJSIP parses URI and address-list syntax; no new dependency.
- Explicit IPv4 transport-source trust, PAI/From precedence and Turkish national
  prefix configuration; an empty trust list and international notation are defaults.
- Turkish mobile-format variants and explicit international syntax, invalid lengths,
  control characters, URI passwords/extensions and local phone-context boundaries.
- Matching SIP/TEL assertions, quoted display-name commas, duplicate/conflicting
  assertions and From headers, malformed values, bounded headers/lists and exact
  source matching. Via/From host claims cannot establish trust.
- Anonymous/withheld/unknown state, privacy precedence and duplicate privacy headers;
  trusted redirect metadata remains separate from caller identity. Untrusted
  assertions/redirects are ignored, and private redirect numbers are suppressed.
- Complete number redaction, no display names or raw URI/host content in logs.
  Parsed records survive receive-pool release and subsequent calls.

Fixtures are synthetic numeric values and `.invalid` domains; no real caller data
or raw audio was retained. The application still plays test tones, not an AI speech
greeting. The existing two-way RTP, impairment, concurrency, cancellation, shutdown,
DB and gRPC suites ran alongside these changes.

## Commands and outcomes

From the Linux project root, with `~/.local/bin` on PATH:

```sh
uv run --frozen cmake --preset local
uv run --frozen cmake --build --preset local -j 8
uv run --frozen ctest --preset local
build/local/caller-identity-test
uv run --frozen pytest tests/sip-integration/test_sip.py -q -k identity --tb=short
uv run --frozen --env-file .local/dev.env pytest -q --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen clang-format --dry-run --Werror services/voice-gateway/src/*.cpp services/voice-gateway/src/*.hpp tests/identity/*.cpp tests/grpc/contract_probe.cpp tests/gpu/cuda_smoke.cu
```

| Check | Observed result |
|---|---|
| Frozen configure/build | Passed; native identity library/test and gateway linked |
| Focused SIP identity/configuration | 15 passed, 21 deselected, 1 known warning, 16.14 s |
| Final CTest | 2/2 passed, 1.03 s; no skips |
| Final native identity assertions | 260 checks passed, including fixture setup checks; not 260 independent scenarios |
| Full pytest with configured PostgreSQL | 69 passed, 1 known warning, 79.92 s; no skips |
| Ruff lint / format | Passed; 11 Python files formatted |
| clang-format | Passed for gateway, identity unit test, contract probe and CUDA smoke source |

Full pytest comprises 27 actual loopback SIP/media/lifecycle/identity cases,
9 invalid CLI-option cases, 4 database tests, 5 protobuf tests and 24 gRPC tests.
The only warning is the existing standard-library `audioop` deprecation under the
pinned Python 3.12; replace that test decoder before upgrading to Python 3.13.
Sanitized full-suite output is kept on the server in
`.local/logs/caller-identity-pytest.log` (ignored). No new test failure occurred in
this task. A final review added short international syntax, duplicate From and
case-insensitive headers and preserved anonymous PAI status before the final run.

## Limits and next step

M1-04 local parser and INVITE integration are complete. Canonical numbers exist in
session memory; durable call-record/DB correlation is not implemented here. Source
trust is an explicit operator policy, not caller authentication or a deployed
firewall. No real carrier IP/prefix was assumed. Number normalization is not
allocation or ownership verification, and History-Info entries do not reconstruct
a routing tree. See [the supported policy](../CALLER_IDENTITY.md).

G1-Ubuntu remains partial: spoken AI greeting/fallback (M1-03) and explicit codec
vectors/resampling acceptance still precede M2–M5. Full US-03 also needs durable
records and live direct/forwarded/withheld CLI checks. G2/G6, real ASR/TTS/API, Mac
revalidation, hosted CI and clang-tidy were not run. No carrier call, network
exposure or model-readiness claim is made.
