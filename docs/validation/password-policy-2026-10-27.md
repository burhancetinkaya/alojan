# Eight-character password minimum

AGP-02 / M0,M5, ADR 0011, requirements native password policy and US-08.
The owner explicitly requested an eight-character minimum and recovery of the
existing owner account. No credential value is recorded in this evidence.

## Behavior

Registration, password change and private operator recovery accept 8–128 Unicode
characters. Both authoring forms and translated validation messages match the API.
Scrypt parameters, maximum size, rate limits, CSRF/origin checks, auditing and
password-version invalidation remain unchanged. No database migration is needed.
The operator recovery path stored a fresh salted hash, incremented the account's
password version and removed its previous sessions. Existing personal MCP tokens
are invalidated by the password-version check and must be reissued if needed.

## Primary Linux verification and deployment

- Authentication and personal-token suites: **29 passed in 19.14s**. Includes
  rejected seven-character enrollment, accepted eight/128-character boundaries,
  eight-character registration/change/recovery, and session/token protections.
- Real isolated HTTPS browser suite: **45 passed (1.3m)**. Registration verifies
  the eight-character input minimum, rejects seven and persists a real account
  using an eight-character synthetic password.
- Web typecheck, production build, API/container builds passed. Mac Ruff and
  whitespace checks passed. Reviewed the complete task-specific diff.
- Only management API and web containers were replaced; both healthy. Twelve
  other Alojan container identities were preserved, including voice and MCP.
- Requested owner recovery succeeded. Public HTTPS login returned 200, the
  authenticated session matched the target account, and the verification session
  was logged out; a subsequent session request returned 401.
- No call, model inference, number binding, external message or full load test.
  Previously paused MCP capacity changes were not deployed by this task.

API image: `sha256:5558e1aeb08d2be9b34f62c558d9e4399fe98ca65a0367e6d1f76576d060a8d2`.
Web image: `sha256:48179ead7b1c72342bace95f4c4bb9bd8fae1cc3613d166d1ed14ca2d0a1986e`.
Private deployment receipts, previous configuration and logs remain under
`.local/password-policy-20261027/` on the primary Linux host. Browser evidence:
`.local/web-validation-f684359fe5b94ba89b59de70c441e955/`.
Rollback restores the backed-up service image references only; it must not restore
old credentials or sessions. Password recovery is deliberately independent of an
image rollback.
