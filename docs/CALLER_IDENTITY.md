# Caller identity policy

M1-04 implements requirements US-03 and sections 6/14 for the native development
gateway. Identity is copied into each admitted session before the first provisional
response. It owns its strings after the receive pool is released. It is a hint for
future message collection, never authentication or permission to invoke a tool.
No raw SIP headers, display names, hostnames or phone numbers enter application logs.

## Configuration

The default trust list is empty, precedence is `pai-first`, and national-number
interpretation is disabled. The gateway remains bound to loopback. For a synthetic
local peer only:

```sh
build/local/voice-gateway --wav /absolute/path/to/test.wav \
  --trusted-identity-ip 127.0.0.1 \
  --identity-precedence pai-first \
  --caller-national-prefix 0
```

`--trusted-identity-ip` can repeat up to 16 times and accepts exact IPv4 literals.
It matches the received packet's socket address, never Via, Contact, From host,
SDP or a claimed forwarding header. CIDRs, hostnames, ports and wildcard trust are
rejected. This is operator-source selection, not caller authentication, and does
not implement the future carrier firewall allowlist. Loopback trust only supports
the test profile; real operator addresses and network protection require M1-06.

`--identity-precedence` accepts `pai-first` or `from-first`. Only configured
transport sources may supply P-Asserted-Identity (PAI), Diversion or History-Info.
Untrusted PAI and redirect headers are ignored. From remains an unverified hint
regardless of transport source. In `pai-first`, a present but malformed/conflicting
trusted assertion produces an unavailable identity rather than falling back to
From. `from-first` prefers a valid From and otherwise considers trusted PAI.

`--caller-national-prefix` accepts `none` (default) or `0`. The latter explicitly
selects the Turkish profile: ten-digit national numbers, leading trunk zero and
bare `90` plus ten digits normalize to `+90`. Both profiles accept explicit `+`
and `00` international notation. Telephone visual separators `- . ( )` are removed;
other characters, extensions, URI passwords, unknown local phone contexts and
control characters are rejected. A TEL `phone-context=+90` requires the Turkish
profile. Turkish numbers require ten national digits with a nonzero, non-one first
digit. Other international numbers receive syntax/length checks, not a global
number-allocation lookup. Successful normalization proves neither assignment nor
ownership. Carrier-specific prefix changes remain subject to actual evidence.

## Selection and privacy

PJSIP supplies the parsed From URI and its name-address list parser handles
extension headers, including SIP/SIPS/TEL URIs and quoted commas. Matching SIP/TEL
PAI values are accepted; conflicting values produce `ambiguous`. Duplicate From
headers also produce `ambiguous` when From is selected. Empty/unknown/unavailable,
invalid, anonymous and withheld identities remain distinct states with no invented
number. Display names never become identity inputs.

Anonymous/withheld From or trusted PAI overrides the selected precedence. Privacy
headers also suppress identity: `none` and `session` alone permit identification;
identity/privacy extensions, including unknown extensions, fail closed. One privacy
request cannot be canceled by another header saying `none`. Suppression clears all
redirect metadata, too. Diversion's `privacy` parameter suppresses that entry unless
explicitly `off`. URI query parameters are not interpreted as caller numbers.

Trusted Diversion/History-Info entries are retained separately, in received order,
with normalized numbers, source names and availability states. They never replace
the caller. This slice does not reconstruct a History-Info routing tree or infer
which forwarding entry represents the original caller. Header values are bounded
to 1024 bytes, 16 relevant headers, eight PAI values and eight redirect entries;
excess input fails closed. These bounds are in addition to PJSIP's receive limits.

`event=caller_identity` uses a local call serial, fixed status/source labels,
`caller_number=redacted|unknown`, operator-source status and ignored/redirect counts.
It never emits even the last digits of a number. Accepted canonical numbers exist
only in the session record in this slice. Persistent call/DB correlation is still
pending; logs deliberately cannot be used to reconstruct the number.

## Evidence and remaining gates

The [Linux identity report](validation/linux-caller-identity-2026-10-23.md) records
parser, security-boundary and actual loopback INVITE checks. Fixtures are synthetic;
no real phone numbers, recordings or private headers are used. The C++ test releases
each parse pool before inspecting results and checks that subsequent parses do not
alter prior identities. Live direct/forwarded/withheld operator behavior remains
M1-07/M6-01 and gates G2/G6. Durable identity persistence remains part of call-record
integration; full US-03 is not accepted by these local tests alone.
