#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
. "${ALOJAN_NETGSM_ENV:-$root/.local/netgsm.env}"
: "${ALOJAN_SIP_BIND:?Set the Linux LAN IPv4}"
: "${ALOJAN_SIP_PUBLIC:?Set the forwarded public IPv4}"
: "${ALOJAN_SIP_SOURCE:?Set the verified carrier signaling IPv4}"
case "${ALOJAN_VOICE_PROFILE:-greeting}" in
    greeting) set -- --max-call-seconds 20 "$@" ;;
    interruption)
        set -- --max-call-seconds 60 --turn-model-dir "$root/.local/turn-models" \
                  --barge-in 1 --asr-port "${ALOJAN_ASR_PORT:-15071}" "$@"
        ;;
    agent)
        set -- --max-call-seconds 120 --turn-model-dir "$root/.local/turn-models" \
            --barge-in 1 --asr-port "${ALOJAN_ASR_PORT:-15171}" \
            --turn-partial-hint "${ALOJAN_TURN_PARTIAL_HINT:-0}" \
            --agent-port "${ALOJAN_AGENT_PORT:-15073}" "$@"
        ;;
    managed)
        set -- --turn-model-dir "$root/.local/turn-models" --barge-in 1 \
            --managed-agent-port "${ALOJAN_AGENT_PORT:-15073}" \
            --managed-asr-port "${ALOJAN_ASR_PORT:-15173}" \
            --managed-tts-port "${ALOJAN_TTS_PORT:-15072}" \
            --called-source "${ALOJAN_CALLED_SOURCE:-request_uri}" \
            --called-national-prefix "${ALOJAN_CALLED_NATIONAL_PREFIX:-none}" "$@"
        ;;
    *) echo "Unknown ALOJAN_VOICE_PROFILE" >&2; exit 2 ;;
esac
if [ "${ALOJAN_VOICE_PROFILE:-greeting}" != managed ]; then
    set -- --prompt-dir "$root/assets/prompts/tr-v5-kubra" --answer-delay-ms 3000 "$@"
fi
# The existing router allowlist protects SIP and RTP; this adds an INVITE source check.
# PJSIP adds RTCP at RTP+1, so the final RTP candidate is 10098, not 10100.
exec build/local/voice-gateway \
    --bind-address "$ALOJAN_SIP_BIND" --public-address "$ALOJAN_SIP_PUBLIC" \
    --allow-sip-ip "$ALOJAN_SIP_SOURCE" --trusted-identity-ip "$ALOJAN_SIP_SOURCE" \
    --caller-national-prefix "${ALOJAN_CALLER_NATIONAL_PREFIX:-0}" \
    --port 5060 --rtp-port 10000 --rtp-port-range 98 "$@"
