# Netgsm and office network preparation

Status as of 2026-10-23: native carrier answer/playback is running; broader M1-06/M1-07 acceptance remains partial.
Owner-provided packet summaries show real Netgsm INVITEs arriving at Linux UDP
5060 through Berqnet. An agent-run external UDP echo probe passed on all 101
ports in 10000–10100 after the owner temporarily allowed the probe source.
The temporary listeners closed, and the owner confirmed removing that source
exception while retaining Netgsm permissions. This is not a completed SIP call
or real RTP audio validation by itself. The subsequent owner-authorized live
profile answered two actual PCMA calls; the owner confirmed intelligible greeting
audio. See [network evidence](validation/netgsm-network-2026-10-23.md) and
[live answer evidence](validation/netgsm-answer-2026-10-23.md).

## Required owner/operator inputs

The configured public IPv4 matched the server's observed egress address, and
inbound reachability was demonstrated through the owner-managed Berqnet rules.
Confirm the permanent LAN address assignment, complete provider signaling/media
source ranges, codecs, port expectations, and whether authentication or
registration is required. Full router topology/CGNAT status was not independently
audited. Keep actual addresses outside Git. The initial requirements assume an
IP-directed trunk, not REGISTER.

## Native live answer profile

The owner explicitly requested inbound phone answering after confirming the
Linux/Netgsm network preparation. This authorizes the limited live profile below;
ADR 0003's default loopback development profile remains unchanged. No router,
host firewall, other application or internal worker exposure was changed here.

`scripts/run-netgsm.sh` reads ignored `.local/netgsm.env` on Linux (mode 0600):

```sh
ALOJAN_SIP_BIND=<Linux LAN IPv4>
ALOJAN_SIP_PUBLIC=<forwarded public IPv4>
ALOJAN_SIP_SOURCE=<verified carrier signaling IPv4>
```

The Netgsm launcher enables Turkish national-number normalization by default
(`ALOJAN_CALLER_NATIONAL_PREFIX=0`). An observed direct carrier INVITE used a
national-format mobile number in `From`; without this option the gateway rejected
it as invalid. Set `ALOJAN_CALLER_NATIONAL_PREFIX=none` to disable national-format
conversion for a deployment that requires international-format input. This does
not change the carrier source allowlist, identity precedence or privacy handling.
Caller ID remains a hint, never authentication.

Actual values were recovered from the owner's earlier network test and the
current egress address was checked against that public mapping. They are not
committed. The launcher uses UDP 5060, RTP candidates 10000–10098 and paired
RTCP 10001–10099, all within the forwarded 10000–10100 range. PJSIP's inclusive
`portRange` applies to RTP and adds one for RTCP; the correct range value is 98.

The gateway now accepts `--bind-address`, `--public-address`,
`--rtp-port-range` and repeatable `--allow-sip-ip` (maximum 16 exact IPv4 sources).
Non-loopback networking requires an explicit non-loopback advertised address
and at least one allowed source. Incoming calls from other transport source
addresses receive 403 before identity parsing/media starts; SIP identity headers
cannot bypass this check. The router remains responsible for the complete SIP
and RTP source allowlist. Only the observed signaling source is configured;
additional carrier failover/media sources must be verified, not guessed.

The process is native and detached, with private PID/log files at
`.local/netgsm-gateway.pid` and `.local/logs/netgsm-gateway.log`. It is not reboot
supervised. Run `scripts/run-netgsm.sh` from a Linux project session to restart
after stopping the existing instance. Never start a second instance on the same
port. The carrier launcher now sends 180 Ringing and waits at least 3000 ms
before answering. The original greeting-only profile plays the approved named AI
greeting plus unavailable/closing WAV, then hangs up after playback.
Greeting playback does not wait for ASR, EMA synthesis or an agent/API. This live
profile does not collect messages or generate conversational responses.

## Network configuration

Use Linux host networking for the gateway, with internal services restricted to loopback/private interfaces. Start with SIP UDP 5060 and RTP/RTCP UDP 10000–10100, then validate the carrier offer and paired port allocation before applying rules. DNAT must match the gateway's advertised Contact/Via/SDP address and media ports. Allow only verified provider sources. Check SIP ALG if signaling or audio is rewritten unexpectedly.

Cloudflare Tunnel must carry only protected HTTP management traffic, never SIP or RTP. Check TLS/SRTP availability with the provider; do not claim transport encryption without a negotiated test.

## Verification sequence

1. Pass G1-Ubuntu before connecting the trunk; G1-local on Mac supports development but does not validate the office deployment.
2. Confirm actual WAN/public mapping and restricted reachability; record a sanitized configuration summary.
3. Place an authorized direct 0850 call, inspect INVITE/ACK/BYE and negotiated PCMA/PCMU, then verify intelligible audio in both directions.
4. Check RTP sequence/pacing, packet loss and jitter, public SDP mapping, and prompt release after hangup.
5. Later compare direct, Turkcell-forwarded, and withheld calls at G6. Preserve original caller and redirecting number as distinct concepts. Never treat an untrusted header as authenticated identity.

Capture only the minimum authorized diagnostic material. Packet captures can contain speech and personal information; keep originals private, redact reports, and remove temporary captures according to the agreed retention policy. [Call test plan](CALL_TEST_PLAN.md) defines evidence fields and unresolved dependencies.

Provider reference: [Netgsm SIP trunk documentation](https://bilgibankasi.netgsm.com.tr/sabit-telefon/sip-trunk-yoenlendirme-hizmeti), checked on 2026-10-23. It describes IP/domain routing, configurable port and number prefixes; it does not establish this account's complete signaling/media source ranges. Actual account settings and observed transport evidence take precedence over examples.

## Owner-authorized live interruption follow-up

The owner subsequently requested a real-phone M3-02 check. The explicit launcher
profiles are now `ALOJAN_VOICE_PROFILE=greeting` (default) and `interruption`.
After confirming no active call and stopping the existing gateway, the test uses:

```sh
ALOJAN_VOICE_PROFILE=interruption ALOJAN_ASR_PORT=15171 scripts/run-netgsm.sh
```

The selected updated ASR worker must already be SERVING on loopback; EMA remains
on loopback 15072. This enables `--barge-in 1`, the pinned CPU turn models and a
60-second call deadline. The original private carrier addresses/source policy
are reused. It does not enable an agent, message persistence or a notification.
The approved opening greeting is still uninterruptible; generated responses can
be interrupted. The generated text is still the fixed unavailable closing.

The profile is currently active for development. [Live evidence](validation/netgsm-interruption-2026-10-23.md)
records two ordinary generated replies, one owner-confirmed interruption with a
new generation, and one incomplete-turn fallback. Full G4 is not passed. To return
to the greeting behavior, confirm the line is idle, stop only this gateway, and
start `ALOJAN_VOICE_PROFILE=greeting scripts/run-netgsm.sh`; do not run both profiles
on the same port. The updated test ASR is a separate detached process with its
own ignored PID file; the old resident ASR and EMA were preserved.
## Current M4 carrier development profile

The owner's M4 continuation supersedes the historical interruption profile above.
Current worker ports are ASR 15172, EMA 15072 and agent 15073. Launch with
`ALOJAN_VOICE_PROFILE=agent ALOJAN_ASR_PORT=15172 ALOJAN_AGENT_PORT=15073
scripts/run-netgsm.sh`. The gateway has a 120-second call bound and remains an
explicit development profile, not full pipeline readiness.

Private `.local/netgsm-active-profile.json` and `.local/netgsm-gateway.pid` identify
the running process. Idle-line activation preserved actual mapped executables,
arguments and logs under `.local/carrier-before-agent`, `carrier-before-fast-agent`
and `carrier-before-waiting-agent`. For the independent M3 rollback use the first
directory's executable and saved argument array while its ASR 15171 and EMA
15072 are healthy. Stop only the current idle gateway, launch the saved binary,
verify readiness and update the PID/profile files. Never log the private arguments
or interrupt an active call to roll back.

The owner confirmed correct message readback but reported excessive waiting.
Confirmation closing is now local and fast; a cancellable waiting phrase covers
part of the remaining model delay. Final listening/latency acceptance is pending.
See [sanitized carrier and Linux evidence](validation/linux-agent-2026-10-23.md).

## Greeting opening-word follow-up

The owner reported missing `Merhaba`. The stored v3 audio includes it, confirmed
by pinned-file hashes and local CUDA ASR. The launcher now selects v4 with 400 ms
of silent RTP before the unchanged greeting. This protects a short connection
startup interval without delaying SIP answer or later replies. Both-codec local
packet tests emulate losing 300 ms at startup; real handset acceptance remains
pending. See [v4 provenance](../assets/prompts/tr-v4-ema/README.md).
