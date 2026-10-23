#!/bin/sh
# Build only the pinned native transport/toolchain, without changing system packages.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
revision=5e6ba94242b92e363220bc2163d55ce3554d4ecc
source="$root/.local/src/grpc-1.78.0"
prefix="$root/.local/grpc"
marker="$prefix/.alojan-$revision-cxx20-v1"
if [ -f "$marker" ]; then exit 0; fi
if [ ! -d "$source/.git" ]; then
    git clone --branch v1.78.0 --depth 1 https://github.com/grpc/grpc.git "$source"
fi
test "$(git -C "$source" rev-parse HEAD)" = "$revision"
# Each gitlink is pinned by the verified parent revision; test-only submodules are omitted.
git -C "$source" submodule update --init --depth 1 --jobs 4 -- \
    third_party/abseil-cpp third_party/boringssl-with-bazel third_party/cares/cares \
    third_party/protobuf third_party/re2 third_party/zlib
cd "$root"
uv run --frozen cmake -S "$source" -B .local/build/grpc -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DgRPC_BUILD_GRPC_CPP_PLUGIN=ON \
    -DgRPC_BUILD_GRPC_CSHARP_PLUGIN=OFF -DgRPC_BUILD_GRPC_NODE_PLUGIN=OFF \
    -DgRPC_BUILD_GRPC_OBJECTIVE_C_PLUGIN=OFF -DgRPC_BUILD_GRPC_PHP_PLUGIN=OFF \
    -DgRPC_BUILD_GRPC_PYTHON_PLUGIN=OFF -DgRPC_BUILD_GRPC_RUBY_PLUGIN=OFF \
    -DABSL_PROPAGATE_CXX_STD=ON -Dprotobuf_BUILD_TESTS=OFF -DRE2_BUILD_TESTING=OFF
uv run --frozen cmake --build .local/build/grpc --parallel "${BUILD_JOBS:-4}"
uv run --frozen cmake --install .local/build/grpc
touch "$marker"
