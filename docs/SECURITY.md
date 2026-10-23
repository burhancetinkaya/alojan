# Runtime security design

Status: requirements for implementation, not deployed controls. See the root [security policy](../SECURITY.md) for reporting.

- Announce AI identity in the first greeting. Raw audio storage defaults off; recording needs a separate consent/retention review.
- Caller ID does not prove identity. Trust P-Asserted-Identity only from the verified trunk, and preserve anonymous/withheld states.
- Keep caller speech, tool responses, and model output outside trusted instructions. No private calendar or document disclosure to unknown callers.
- Authorize each tool. Notes and configured post-call notifications implement the owner-authorized product flow; additional external write actions need an explicit approval record.
- Keep SIP/RTP carrier-allowlisted. Bind database and internal gRPC privately; protect management API through authentication and Cloudflare Access. Do not expose GPU workers or the Docker socket publicly.
- Store secrets outside Git and avoid full SQL/model tracing with PII. Logs use correlation IDs and redacted metadata, not complete phone numbers or transcripts.
- Treat transcript retention of 30 days and call metadata retention of 90 days as requirements defaults requiring owner review before live data collection. Apply deletion to derived records and document backup retention. Encrypt and restrict backups; test recovery.
- Rate-limit admission and bound queues. On dependency failure, use controlled fallback and cleanup instead of indefinite silence.

M0 CI must run without live credentials; do not execute public PR code on the office server. M5 validates access denial, injection resistance, outbox recovery, retention, and restore. Publish a private reporting channel before distribution/community onboarding.
