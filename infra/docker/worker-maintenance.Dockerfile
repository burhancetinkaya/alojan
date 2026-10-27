# Staged source-only Linux validation context; preserve verified installed runtimes.
# Verify the explicit local base tag's image ID before building with --pull=false.
ARG ALOJAN_WORKER_BASE
FROM ${ALOJAN_WORKER_BASE}
COPY services ./services
COPY generated/python ./generated/python
COPY health.py ./infra/docker/health.py
