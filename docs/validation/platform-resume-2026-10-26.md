# Rollback validation resumed and voice migration preparation

ADR 0003/0011; AGP-02/03/09, CFG-01/03, M4/M5; requirements §9–12.
Primary Linux execution, synthetic database/transport tests, no live cutover.

## Completed rollback checks

Source checksums matched after SSH returned. The remaining Compose overlay was copied
to Linux; maintained documents were mirrored without overwriting independent remote
root documents. The effective Compose configuration was compared privately: absent
ALOJAN_LEGACY_DATABASE_ENV fails interpolation; its supplied private path replaces
database_env for the old agent, health API and Telegram service; service definitions
are otherwise identical. No `up` or restart command ran, and no credentials were printed.

The first expanded test run had **71 passes and one failure in 72.60s**. Concurrent
retry consumption and dispatch use independent SKIP LOCKED acquisitions. One worker
can lock/reopen the job while another holds the global dispatch gate but still sees
the old terminal job. Both can return no claim for that poll. This is deferred work,
not lost consent or permission for a duplicate. The test now allows this ordering and
requires the next poll to claim the same job once. A deterministic test holds the
global gate, checks the consumed approval and pending job with zero attempts, releases
it, then verifies exactly one generation and attempt. Production scheduling was unchanged.

Focused tests: **2 passed in 3.01s**, 23 deselected. Expanded rollback, migration,
routing, scoped records, delivery management and action delivery: **115 passed in
124.70s**, zero skips. No additional external Telegram message was sent.

## Complete business instructions, unchanged technical ceilings

The preserved live backend matches its Docker image at SHA-256
`238ce47df6f6c48c0a77095be7856475b8551b6d22be88e5f20d1535288709d4`.
Its 18,159-character instructions match the retained legacy module at SHA-256
`048682c42ee3c4e4314b30ce5f09ad0fa523624e33c871b829b96ad95b32cd4f`.
The prior 6,000-character field could not store this required migration input.

Business instructions now accept at most 20,000 characters. This is an authoring
compatibility fix; draft storage stays at 60,000 bytes and the compiled prompt at
32,768 UTF-8 bytes. A long Unicode field can fit its character limit and still fail
compilation; it is never truncated or silently accepted over budget. Regression stores,
reads and compiles the full existing text, rejects 20,001 characters, and exercises
the unchanged compiled byte cap. Draft/runtime/release/managed-startup suites:
**71 passed in 26.06s**, zero skips.

A mode-0600 offline business draft and content-free review were prepared only on Linux
under `.local/kubra-migration-preparation/`. No account, database row, grant, publication
or binding was created. All 11 speech fields equal the retained LEGACY_RUNTIME values.
Default model settings match the preserved source: openai/gpt-oss-120b, Cerebras only,
medium reasoning, temperature 0.2 and 4096 tokens; provider fallback remains disabled.
The complete compiled prompt is 23,574 bytes, SHA-256
`3f33f718a2399118198e6ead75710a179b0bda9fc6d858cc9d1ca03eac545e31`.

The compiler adds mandatory platform policy/identity context: this prompt is **not**
byte-identical to the old live prompt. Real comparison must record the unchanged live
baseline, then hold the effective prompt/model/tools/audio fixtures constant for the
infrastructure comparison. Report migration behavior/prompt-length effects separately.
Compilation and default equality are not qualification of real EMA/ASR settings,
provider access, call quality, full summary behavior or performance. The scoped owner
account, provider reference, Telegram connection/grant, qualified assets/preset, verified
DID and matched real voice/PERF canary remain required. The second number stays disabled.

## Built packages and limitations

Both images were rebuilt after the shared contract change and passed network-disabled,
read-only, capability-dropped import/schema checks with temporary storage only:

- Management: `sha256:a3cb8c8c9198acadcd2124dfc890b056d834af712a593254e360344104bbfccf`.
- Action worker: `sha256:14bf4eee211536caf95976971bf0f9fd1c39fa542c302d30d7c1ce464475e8e1`.

The management CLI includes legacy-rollback provisioning; both packaged schemas expose
the new 20,000-character instruction bound. Ruff/format and diff whitespace checks
passed; graph index refreshed without persisted cache. Seven resident Alojan containers
remained healthy with their original start times. No production schema/credential/role/
ownership change, restart, audio generation, new inference load, SIP/carrier acceptance,
actual rollback, push or merge was performed. The prepared draft is not deploy-ready.
