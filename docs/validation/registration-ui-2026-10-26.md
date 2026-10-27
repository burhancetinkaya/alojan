# Registration journey — 2026-10-26

AGP-06 / M2,M5, ADR 0011; requirements §1/12/14–16.
Owner approved the registration mockup and requested implementation.

## Delivered behavior

The existing Next.js/shadcn frontend now offers the approved account → first agent
→ preparation journey. Account identity is distinct from agent identity; assistant
owner and instructions are editable. The native register API creates the account
and isolated workspace; authenticated `/baslangic` uses the existing scoped create
API. Shared voice/model defaults remain server-owned. Skipping creates no agent and
shows an honest empty state with a route back to agent creation or the workspace.

A saved draft opens the preparation checklist with links to the editor, number
verification and optional Telegram connections. No automatic synthesis, publication,
number binding, action permission or delivery occurs. Reload after saved/uncertain
creation resumes at the agent list. Existing login behavior and manual recovery stay
available. No backend, schema, dependency, model or media-path changes.

Pending submission is guarded with an immediate ref and disabled controls. On an
ambiguous registration response, the frontend probes the session once; if unavailable,
it clears the password and directs to login rather than retrying registration.
Ambiguous agent creation disables resubmission and offers inspection of saved agents.
Server validation errors preserve the form. Sessions and passwords are not persisted
in browser storage. Unsaved onboarding input does not survive a reload.

## Validation and review

Primary Linux host with the existing pinned Node/Playwright images:

- TypeScript, Prettier checks, isolated production build and deployable image build passed.
- Final isolated HTTPS browser suite: **17 passed in 31.1s**, no retries or skips.
  Covers real registration and workspace separation, password reveal, first draft
  persistence, independent owner/name/instructions, skip/resume, validation errors,
  truncated registration response with session recovery, lost create response without
  duplication, uncertain registration without session, and desktop/390px mobile views.
- Assertions prove empty number/release/action state after onboarding and exactly one
  registration/creation in the normal path. Existing CSRF/session, foreign-workspace,
  editing, publication, Telegram permission, call-detail, retry, rollback and performance
  browser scenarios also passed. Harness confirms unchanged synthetic binding/action
  job counts; no live calls, external sends or production configuration writes.
- Initial run: 13 passed / 4 failed due to test assertions: a broad alert selector also
  matched Next.js's route announcer, and an optional empty action field was expected
  to be serialized. Corrected selectors and aligned assertions with the existing
  empty-field serialization. A subsequent run passed all 17 in 29.9s. Final 31.1s run
  includes the visual correction below and supersedes it.
- Desktop/mobile screenshots reviewed. Corrected inherited anchor color on the
  primary checklist link to retain white text, and aligned heading/spacing with the
  approved design. No horizontal overflow observed at 390px.
- Scoped diff reviewed using the pre-task snapshot; unrelated work preserved.
  `git diff --check` passed. Code graph refreshed. No commit, push, PR or merge.

Final synthetic evidence:
`.local/web-validation-69fc74fe8d29441bada7a6577ae8bd1e/`.
Local review snapshot/screenshots: `.local/registration-ui-20261026/`.

## Private-preview deployment

Web image: `sha256:96e9c98977118884069d0aeb3508a729220218a40ecdee35b29e98bf0399c23e`.
Only the web service was recreated. Nine existing application peers retained their
container IDs; configured peer health checks remained healthy. Management was not
restarted; no database migration or voice configuration change was performed.

Deployed anonymous registration desktop/mobile rendering passed. Existing owner
login, agent configuration, immutable release history, prepared EMA audio decoding,
all navigation, call details, transcript, delivery result, latency page and logout
passed with zero browser errors. The smoke interceptor blocked every configuration
mutation. No owner account recreation, agent edit, new call or external send.

Rollback: restore `.local/registration-ui-20261026/web-compose.before.env` to the
private web compose environment and recreate only `web`. Previous image:
`sha256:8c4e331ee962d7a4a1f0aac0508d48210ecbe7e9c312c8ce8cb9b8ecc015ec45`.

## Limits and next work

This completes the approved onboarding slice, not all AGP-06 acceptance. Full new-user
voice preparation/publication/carrier routing acceptance, staged MCP/HTTP builders,
public email recovery and public launch remain separate. No new GPU, latency, load
or simultaneous-call acceptance. Serving capacity and the disabled second number are
unchanged. In-flight creation is not a new server idempotency contract; uncertain
results require inspecting saved agents before another explicit creation.
