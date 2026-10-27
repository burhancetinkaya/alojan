# Staged Linux validation context, not the repository root. See DEV_SETUP.md.
# Preserve verified runtime/model libraries; pin and verify the local base tag's ID.
ARG ALOJAN_GATEWAY_BASE
FROM ${ALOJAN_GATEWAY_BASE}
COPY voice-gateway /opt/alojan/build/local/voice-gateway
COPY supervise.py health.py /opt/alojan/infra/docker/
COPY run-netgsm.sh /opt/alojan/scripts/run-netgsm.sh
