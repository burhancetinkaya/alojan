FROM ghcr.io/astral-sh/uv:0.11.9@sha256:6b6fa841d71a48fbc9e2c55651c5ad570e01104d7a7d701f57b2b22c0f58e9b1 AS uv
FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS base
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 python3-venv=3.12.3-0ubuntu2.1 \
    ca-certificates=20260816ubuntu0.24.04.1 \
    && rm -rf /var/lib/apt/lists/*
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /opt/alojan
COPY services/app-api/pyproject.toml services/app-api/uv.lock ./services/app-api/
RUN uv sync --frozen --no-dev --project services/app-api
COPY services/app-api/alojan ./services/app-api/alojan
COPY services/voice-contracts/alojan_contracts ./services/voice-contracts/alojan_contracts
COPY infra/migrations ./infra/migrations
ENV PYTHONPATH=/opt/alojan/services/app-api:/opt/alojan/services/voice-contracts UV_CACHE_DIR=/tmp/uv
USER 1000:1000
CMD ["uv", "run", "--frozen", "--no-sync", "--project", "services/app-api", "--env-file", "/run/secrets/management_env", "python", "-m", "alojan.api"]
