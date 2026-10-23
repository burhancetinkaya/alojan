# Netgsm immediate answer and greeting — 2026-10-23

Tasks M1-06/M1-07, supporting M1-08 carrier evidence; requirements §6/12.2,
DEC-05/14 and US-01. Branch `codex/netgsm-answer`, uncommitted source over
`a59675e`, preserving the existing foundation. Linux Ubuntu 24.04 / native
PJSIP 2.16; session date Europe/Istanbul (UTC+03:00).

The owner asked to continue from the prepared Linux UDP/Netgsm connectivity and
make incoming phone calls answer promptly. This explicitly authorizes the limited
live answer profile. No new product scope, router rule, host firewall rule or
public exposure of internal ASR/TTS/database services was introduced.

## Runtime result

The gateway is running natively on the Linux LAN interface, UDP 5060. Contact and
SDP advertise the existing public NAT mapping. The launcher restricts new calls
to the signaling source observed in the owner's earlier Netgsm test; the existing
Berqnet carrier allowlist remains the network boundary for signaling and media.
RTP candidates 10000–10098 plus RTCP 10001–10099 fit the forwarded range.
Actual endpoints are stored only in ignored mode-0600 `.local/netgsm.env`.

The caller receives the approved EMA-generated greeting naming Burhan Çetinkaya
and identifying the assistant as AI, followed by the existing unavailable/closing
message. No generation or API call delays the greeting. The owner reported:
**the call connected and the greeting was intelligible**. This is new real carrier
listening evidence, separate from earlier local listening/model tests.

| Observation | Call 1 | Call 2 |
|---|---:|---:|
| Codec | PCMA | PCMA |
| 200 answer state after incoming callback | 0 ms at integer resolution | 0 ms at integer resolution |
| Confirmed/ACK state | 13 ms | 13 ms |
| Media connections prepared | 14 ms | 14 ms |
| Local call lifetime | 3,770 ms | 7,285 ms |
| Valid 16 kHz input frames | 187 | 363 |
| Nonzero input samples | 15,509 | 39,278 |
| Invalid input frames | 0 | 0 |
| Last sampled inbound RTP packets | 164 | 341 |
| Last sampled loss / reorder / duplicates | 0 / 0 / 0 | 0 / 0 / 0 |
| Last sampled maximum jitter | 0 µs | 125 µs |
| Termination | Remote hangup | Local closing completed, session released |

These elapsed times begin at gateway call object creation, not phone dialing.
`media_started` means the audio ports were connected, not that the first sound
reached the handset. Zero-millisecond answer means below the log's millisecond
resolution, not zero network latency. RTP stats are periodically sampled and are
not a complete packet capture. The local closing uses the existing hangup status
internally; a separate raw on-wire BYE response trace was not collected.

Incoming nonzero PCM demonstrates a working return media path. It does not prove
the intelligibility or semantic correctness of caller speech: there was no live
ASR transcription, echo/listening test or caller recording. Full G2 acceptance,
live caller identity and forwarded-number behavior remain open for their explicit
criteria. The immediate-answer/greeting request itself is fulfilled.

## Validation and implementation

The gateway gains bounded/validated IPv4 bind, advertised address, inclusive RTP
range and exact-source options. Defaults remain loopback. Non-loopback use fails
closed without an advertised address and source allowlist. Untrusted incoming
calls receive 403 before identity processing/media; source is taken from the
received packet, never a claimed SIP header. The native launcher keeps raw audio
recording disabled and one-call admission unchanged.

Ten new synthetic-loopback tests passed in **3.38 s**: PCMA/PCMU immediate answer,
public Contact/SDP, greeting within one second after ACK, source-spoof rejection
and seven unsafe configuration cases. These are real native SIP tests, not carrier
tests. One known Python 3.12 audioop deprecation warning remains.

Final full pytest: **161 passed, no skips, 276.73 s**, with one known audioop
deprecation warning. Native build passed;
Ruff lint passed, 33 Python files were formatted, changed C++ clang-format and
launcher shell syntax passed. All **5 CTests passed in 2.08 s**.
The source graph was refreshed: 1,728 nodes / 3,909 edges, without a shared
graph artifact. The task diff and documentation links were reviewed.
Linux gateway SHA-256:
`624ed461fce0832c89da2e3cbee5c97ecdc10a73377261417ec0f1948238036c`.

## Operations and remaining scope

See [network setup](../NETWORK_NETGSM.md). Private runtime evidence is
`.local/logs/netgsm-gateway.log`, with `.local/netgsm-gateway.pid` identifying the
detached process. No raw SIP dump, audio capture, full telephone number or private
endpoint appears in this report. Both speech workers remain available on loopback;
the live answer profile currently plays the approved WAV files.

The gateway remains running for owner calls. It is not reboot supervised.
Conversational answers, message collection, M3 turn detection, M4 GPT integration,
full carrier/source-range review and broader call-quality/soak acceptance remain
separate. No push, publication, merge or license decision was made.
