FROM ghcr.io/astral-sh/uv:0.11.9@sha256:6b6fa841d71a48fbc9e2c55651c5ad570e01104d7a7d701f57b2b22c0f58e9b1 AS uv
FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS base
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 python3-venv=3.12.3-0ubuntu2.1 \
    build-essential=12.10ubuntu1 curl=8.5.0-2ubuntu10.16 git=1:2.43.0-1ubuntu7.4 \
    pkg-config=1.8.1-2build1 libsndfile1=1.2.2-1ubuntu5.24.04.1 \
    ca-certificates=20260816ubuntu0.24.04.1 perl=5.38.2-3.2ubuntu0.6 \
    && rm -rf /var/lib/apt/lists/*
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /opt/alojan

FROM base AS python-deps
ARG SERVICE
COPY services/${SERVICE}/pyproject.toml services/${SERVICE}/uv.lock ./services/${SERVICE}/
RUN uv sync --frozen --no-dev --project services/${SERVICE}

FROM base AS python
COPY --from=python-deps /opt/alojan/services ./services
COPY services ./services
COPY generated/python ./generated/python
COPY infra ./infra
COPY scripts ./scripts
ENV PYTHONPATH=/opt/alojan/services/agent:/opt/alojan/services/asr:/opt/alojan/services/tts:/opt/alojan/services/app-api:/opt/alojan/services/voice-contracts:/opt/alojan/generated/python
ENV UV_CACHE_DIR=/tmp/alojan-runtime-uv

FROM base AS gateway-build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY scripts ./scripts
RUN scripts/build-pjsip.sh && scripts/build-grpc.sh
COPY tools/turn-eval ./tools/turn-eval
RUN uv sync --frozen --project tools/turn-eval && \
    uv run --frozen --project tools/turn-eval python scripts/prepare-turn-models.py
COPY CMakeLists.txt CMakePresets.json ./
COPY services/voice-gateway ./services/voice-gateway
COPY generated/cpp ./generated/cpp
COPY tests ./tests
RUN uv run --frozen cmake --preset local -DALOJAN_TURN_MODELS=ON && \
    uv run --frozen cmake --build --preset local -j 4 && \
    uv run --frozen ctest --preset local

FROM gateway-build AS validation
COPY services ./services
COPY infra ./infra
COPY tools ./tools
COPY assets ./assets
ENV PYTHONPATH=/opt/alojan/services/agent:/opt/alojan/services/asr:/opt/alojan/services/tts:/opt/alojan/services/app-api:/opt/alojan/services/voice-contracts:/opt/alojan/generated/python
COPY generated/python ./generated/python

FROM base AS gateway
COPY --from=gateway-build /opt/alojan/build/local/voice-gateway ./build/local/voice-gateway
COPY --from=gateway-build /opt/alojan/.local/turn-models ./.local/turn-models
COPY --from=gateway-build /opt/alojan/tools/turn-eval/.venv/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime.so.1.31.0 /usr/local/lib/libonnxruntime.so.1
RUN ldconfig
COPY assets/prompts ./assets/prompts
COPY scripts/run-netgsm.sh ./scripts/run-netgsm.sh
COPY infra/docker ./infra/docker
ENV LD_LIBRARY_PATH=/usr/local/lib
