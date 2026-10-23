#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p generated/python
mkdir -p generated/cpp
uv run --frozen python -m grpc_tools.protoc -I proto \
  --python_out=generated/python --grpc_python_out=generated/python proto/voice/v1/voice.proto
.local/grpc/bin/protoc -I proto --cpp_out=generated/cpp --grpc_out=generated/cpp \
  --plugin=protoc-gen-grpc=.local/grpc/bin/grpc_cpp_plugin proto/voice/v1/voice.proto
