# Outbound announcements

Publish the agent's outbound settings and bind that release to a verified DID.
The Outbound page lets a workspace editor or owner choose a line, enter a
Turkish geographic or mobile destination, submit text, and override the timers.
Viewers can inspect history. Each release supplies its AI introduction and voice.
The complete message is prepared before dialing. Completed means the gateway
sent the announcement. It does not identify a human recipient.

## Customer HTTP API

Use a workspace personal token with `outbound:submit` for POST and
`outbound:read` for GET. Each new request needs a fresh UUID idempotency key.
Reuse the same key and payload after an ambiguous HTTP result. Reusing the key
with different content returns 409. Retain the call ID from the 202 response.

```sh
curl --fail-with-body -X POST "$ORIGIN/v1/workspaces/$WORKSPACE/outbound-calls" \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $OPERATION_UUID" \
  -H 'Content-Type: application/json' \
  --data '{"agent_id":"00000000-0000-4000-8000-000000000001","to":"05320000000","text":"Bu bir deneme aramasıdır.","ring_timeout_seconds":30,"post_playback_seconds":2}'
curl --fail-with-body -H "Authorization: Bearer $TOKEN" \
  "$ORIGIN/v1/workspaces/$WORKSPACE/outbound-calls/$CALL_ID"
```

GET the collection for 50 masked records ordered newest first. Pass the returned
`next_cursor` as `after`. Details contain the full destination and message.
GET the collection's `eligible` subresource for published agents and their lines.
Specify `caller` from that list if an agent has multiple eligible lines.
Defaults are 30 seconds to answer and 2 seconds from sent audio to local
hangup. Per-call bounds are 1–120 and 0–30 seconds. Maximum text is 2,000
characters, including whitespace. Synthesis failure prevents dialing.
The terminal states are completed, busy, rejected, no_answer, interrupted,
failed and uncertain. None triggers a second carrier attempt.

## Linux deployment

Apply migration 0031 and refresh the management role's grants. Create a dedicated
unprivileged worker role, then provision it with `python -m alojan.roles ROLE
--purpose outbound` under the migration account. Use the same node ID as the
verified route. Deploy compatible release readers before publishing version 12.
Keep existing Compose settings and include `infra/compose.outbound.yaml` as an
additional overlay. Build the new gateway, web, management and outbound worker
images. Drain the gateway before replacing it and reopen only after health passes.

In the private state directory, create `outbound-spool` mode 0700, owned by the
gateway and worker runtime UID. Provide the following files mode 0600:

- `outbound-sip.env` supplies shell-quoted ALOJAN_OUTBOUND_SIP_USER (ten-digit
  verified DID), ALOJAN_OUTBOUND_SIP_DOMAIN and ALOJAN_OUTBOUND_SIP_PASSWORD.
  This release uses the site's existing verified Netgsm peer for UDP digest
  origination on port 5060 without registering the inbound DID.
- `outbound-worker.env` supplies ALOJAN_DATABASE_URL for the outbound role,
  ALOJAN_VOICE_NODE_ID and, if needed, ALOJAN_TTS_ENDPOINT (default
  127.0.0.1:15072). One SIP account per node is supported. Unconfigured
  originating identities fail before INVITE.

The worker purges completed message text after 30 days and destination/history
visibility after 90 days by default. Configure ALOJAN_OUTBOUND_TEXT_DAYS and
ALOJAN_OUTBOUND_HISTORY_DAYS to match workspace policy. Retained operation
identities prevent replay. The private spool holds synthesized output only
until reconciliation; protect it like the call database.

The operator-only `scripts/qualify-outbound.sh` uses the pinned PJSUA CLI
and a prepared greeting for one authorized handset test. It uses a separate
SIP port and media pair; run it while that pair is idle. It exercises carrier
signaling separately from the product gateway and customer API.
