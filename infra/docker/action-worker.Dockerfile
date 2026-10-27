FROM ghcr.io/astral-sh/uv:0.11.9@sha256:6b6fa841d71a48fbc9e2c55651c5ad570e01104d7a7d701f57b2b22c0f58e9b1 AS uv
FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS base
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 python3-venv=3.12.3-0ubuntu2.1 \
    ca-certificates=20260816ubuntu0.24.04.1 \
    && rm -rf /var/lib/apt/lists/*
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /opt/alojan
COPY services/action-worker/pyproject.toml services/action-worker/uv.lock ./services/action-worker/
RUN uv sync --frozen --no-dev --project services/action-worker
COPY services/agent/alojan_agent ./services/agent/alojan_agent
COPY services/voice-contracts/alojan_contracts ./services/voice-contracts/alojan_contracts
ENV PYTHONPATH=/opt/alojan/services/agent:/opt/alojan/services/voice-contracts UV_CACHE_DIR=/tmp/uv
USER 1000:1000
CMD ["uv", "run", "--frozen", "--no-sync", "--project", "services/action-worker", "--env-file", "/run/secrets/worker_env", "python", "-m", "alojan_agent.summary_worker"]
