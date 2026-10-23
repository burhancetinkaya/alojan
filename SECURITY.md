# Security policy

## Supported versions

There are no released or production-supported versions. The default development gateway and internal services bind to loopback. The owner-authorized native Netgsm test profile binds the Linux LAN address behind the existing carrier-restricted router rules, with an additional incoming-call source check. This is not a hardened production deployment; see [carrier setup](docs/NETWORK_NETGSM.md).

## Reporting a vulnerability

Use GitHub's **Report a vulnerability** action on the repository Security page if private vulnerability reporting is enabled:

https://github.com/burhancetinkaya/alojan/security

Its availability has not been verified. If the action is unavailable, open an issue containing only a request for a private security contact. Do not include vulnerability details, exploits, credentials, recordings, or personal information. A maintainer must establish a private channel before receiving sensitive material. A working private reporting channel is a release prerequisite.

Privately include the affected revision, expected and observed behavior, minimal synthetic reproduction, impact, and suggested mitigation. No response-time SLA is promised at this stage. If a credential was exposed, revoke it through its provider; deleting a public issue or Git commit is insufficient.

## Development requirements

Keep credentials outside Git, raw audio recording disabled, and test data synthetic. Redact SIP headers, telephone numbers, transcripts, and model traces. Restrict SIP/RTP to verified carrier sources; expose management HTTP only through authenticated access. Do not test third-party infrastructure without authorization.

See [runtime security design](docs/SECURITY.md) and [license review](docs/LICENSING.md).
