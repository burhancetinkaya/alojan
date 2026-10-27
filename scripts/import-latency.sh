#!/usr/bin/env bash
# Read the existing content-free gateway measurements; never restart voice services.
set -euo pipefail
: "${ALOJAN_LATENCY_IMAGE:?Pinned management image required}"
: "${ALOJAN_VOICE_NODE_ID:?Node identity required}"
: "${ALOJAN_LATENCY_DATABASE_ENV:?Private dedicated-role environment required}"
docker logs --since=10m --tail=10000 alojan-local-gateway-1 2>/dev/null |
  docker run --rm --name alojan-latency-import --network=host --cpus=0.25 --memory=128m \
    --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m --cap-drop=ALL \
    --security-opt=no-new-privileges:true -i --env-file "$ALOJAN_LATENCY_DATABASE_ENV" \
    --entrypoint /opt/alojan/services/app-api/.venv/bin/python \
    "$ALOJAN_LATENCY_IMAGE" -m alojan.latency --node "$ALOJAN_VOICE_NODE_ID"
