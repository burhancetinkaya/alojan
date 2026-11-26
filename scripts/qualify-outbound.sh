#!/usr/bin/env bash
# One supervised handset trial. Run on the development host from the repo root.
set -euo pipefail
umask 077
source "${ALOJAN_NETGSM_ENV:-.local/netgsm.env}"
source "${ALOJAN_OUTBOUND_ENV:-.local/outbound-sip.env}"
read -rs -p "Authorized Turkish mobile test number (national format): " destination
echo
[[ $destination =~ ^05[0-9]{9}$ ]]
dir=$(mktemp -d)
trap 'rm -f "$dir/probe.cfg" "$dir/test.wav"; rmdir "$dir"' EXIT
python3 - "$dir/test.wav" <<'PY'
import sys
import wave

with wave.open("assets/prompts/tr-v3-ema/greeting.wav", "rb") as src:
    with wave.open(sys.argv[1], "wb") as output:
        output.setparams(src.getparams())
        output.writeframes(src.readframes(src.getnframes()))
        output.writeframes(bytes(2 * src.getframerate() * src.getnchannels() * src.getsampwidth()))
PY
cat > "$dir/probe.cfg" <<CFG
--id=sip:${ALOJAN_OUTBOUND_SIP_USER}@${ALOJAN_OUTBOUND_SIP_DOMAIN}
--realm=*
--username=${ALOJAN_OUTBOUND_SIP_USER}
--password=${ALOJAN_OUTBOUND_SIP_PASSWORD}
--proxy=sip:${ALOJAN_SIP_SOURCE}:5060;lr
--bound-addr=${ALOJAN_SIP_BIND}
--ip-addr=${ALOJAN_SIP_PUBLIC}
--local-port=15062
--rtp-port=10098
--null-audio
--no-tcp
--no-vad
--no-color
--play-file=/run/trial/test.wav
--auto-play-hangup
--duration=20
--max-calls=1
--auto-answer=486
--app-log-level=4
sip:${destination}@${ALOJAN_OUTBOUND_SIP_DOMAIN}
CFG
bin="$PWD/.local/src/pjproject-2.16/pjsip-apps/bin/pjsua-$(gcc -dumpmachine)"
if [[ ! -x "$bin" ]]; then
    bin="$PWD/.local/src/pjproject-2.16/pjsip-apps/bin/pjsua-x86_64-pc-linux-gnu"
fi
image=$(docker inspect -f '{{.Image}}' "${ALOJAN_GATEWAY_CONTAINER:-alojan-local-gateway-1}")
{ sleep 40; echo q; } | docker run --rm -i --network host --log-driver=none \
    --user "$(id -u):$(id -g)" -v "$dir:/run/trial:ro" -v "$bin:/probe:ro" \
    --entrypoint /probe "$image" --config-file=/run/trial/probe.cfg 2>&1 |
    python3 -uc '
import re, sys
for line in sys.stdin:
    event = re.search(r"(TX \d+ bytes Request msg (?:INVITE|ACK|CANCEL|BYE)|RX \d+ bytes Response msg \d{3}|state changed to [A-Z]+|DISCONNECTED \[reason=\d{3})", line)
    if event:
        print(event[0])
'
