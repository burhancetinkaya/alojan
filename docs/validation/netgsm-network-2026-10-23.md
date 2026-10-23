# Netgsm network reachability evidence

Date: 2026-10-23 (Europe/Istanbul session date).
Tasks: M1-06, supporting M1-07 and the M1-08 carrier addendum.
Milestone/gate: M1 / G2, partial evidence only; G2 is not passed.
Requirements: DEC-05/14, sections 6 and 12.2; US-01/03 carrier acceptance remains open.
Record: uncommitted working tree on `codex/speech-gateway`; this report adds no
runtime changes or new build evidence. Existing Linux environment details are in
[development setup](../DEV_SETUP.md).
Testers: owner (Netgsm/Berqnet configuration, phone call and packet summaries),
agent (SSH inspection and external UDP probes).

## Preconditions and observations

- The owner enabled Netgsm SIP Trunk routing to the office public IPv4, UDP 5060,
  and configured Berqnet forwarding to the Linux server. The owner also configured
  UDP 10000–10100 for media. Actual addresses and telephone numbers are omitted.
- The configured public IPv4 matched the Linux server's observed internet egress
  IPv4. This comparison alone does not establish inbound reachability or topology.
- At the initial inspection, no SIP listener was present on UDP 5060 or 15060.
  The owner reported UFW inactive; other firewall layers were not fully audited.
- The owner ran `sudo timeout 60 tcpdump -ni any -nn 'udp dst port 5060'` while
  making a direct call to the Netgsm number. Initial attempts showed no packets.
  A later owner-provided excerpt showed four inbound SIP INVITEs arriving on the
  Linux physical interface at local UDP 5060, with displayed times from
  15:09:59.875367 to 15:10:03.314865. The capture clock/timezone was not independently
  calibrated. The excerpt is consistent with INVITE retransmissions; response
  traffic was not established by this inbound-only filter.
- This demonstrates real carrier-originated inbound signaling delivery through
  the configured NAT path. It does not demonstrate SIP answer, ACK/BYE, codec
  negotiation, caller identity correctness or an established media session.

## UDP range probe

The agent used Python standard-library UDP sockets on the Linux server and the
Mac client over a different public internet connection. The transient server
bound every port from 10000 through 10100 inclusive, without address reuse; all
101 binds succeeded. It accepted only an exact random per-run synthetic token
and echoed that token to the sender. No speech or caller content was used.
Listeners had a 12-second lifetime and were closed in cleanup.

For each run the client sent to every bound port, waited three seconds for replies,
then retried only ports without a matching response and waited another three
seconds. Replies were accepted only with the expected token, target public IP and
matching source port. Server receive counts were checked independently of client
reply counts. The final run first verified that the client's current public IP
matched the temporary Berqnet source exception.

| Attempt | Observed result | Interpretation |
|---|---|---|
| Initial restricted-source probe | 101 binds; 0 ports received a valid token; 0 roundtrip replies | The owner subsequently confirmed Netgsm-only source permissions; no conclusion about carrier RTP |
| Retry after owner reported changing the source to any | 101 binds; 0 ports received a valid token; 0 roundtrip replies | Still unsuccessful; the applied firewall/NAT state was not independently inspected |
| Retry after owner explicitly allowed the probe source IP | 101 binds; 101 ports received a valid token; 101 matching roundtrip replies; no missing ports; remote exit 0 | Pass for synthetic UDP reachability and reply routing on every tested port under that temporary source policy |

The owner subsequently confirmed removing the test source exception and retaining
Netgsm permissions. Listener cleanup was confirmed by the probe output. No
persistent test service was installed. The passing run does not verify Netgsm
media source ranges, RTP framing, negotiated ports, jitter/loss or audible speech.

## Evidence handling and remaining acceptance

Only sanitized observations and aggregate probe results are recorded here. The
owner's packet-summary excerpt and transient tool output are in the chat; no raw
capture, recording, telephone number, actual endpoint address or credential was
copied into the repository. The probe was an ad hoc diagnostic, not a committed
test runner; the procedure above describes its reproduction.

1. M1-06 remains in progress: configure/verify the gateway's live listen address,
   advertised public Contact/Via/SDP and media allocation within UDP 10000–10100.
2. Confirm the complete operator signaling and media source ranges and validate
   the final restricted Berqnet policy. A signaling source is not evidence of the
   complete media allowlist. No need to repeat the successful generic range test
   unless routing or firewall rules change.
3. M1-07 / G2 remain open: answer a direct Netgsm call, verify 200/ACK/BYE, codec,
   SDP/NAT agreement, intelligible bidirectional audio and prompt teardown. The
   existing unavailable-dependency WAV profile can isolate transport from AI.
4. Live caller identity and forwarded-call behavior remain separate US-03 / G6
   checks. These network results establish no ASR/TTS/GPU or full-agent readiness.
