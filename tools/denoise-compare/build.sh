#!/bin/sh
# Isolated Ubuntu evaluation build. Does not install system packages or alter services.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
work="$root/.local/denoise-eval"
mkdir -p "$work/src"
fetch() {
    file="$work/src/$1"
    if [ ! -f "$file" ]; then curl -fL --retry 2 "$2" -o "$file"; fi
    printf '%s  %s\n' "$3" "$file" | sha256sum -c -
}
fetch webrtc-2.1.tar.xz \
    https://gstreamer.freedesktop.org/src/mirror/webrtc-audio-processing/webrtc-audio-processing-2.1.tar.xz \
    ae9302824b2038d394f10213cab05312c564a038434269f11dbf68f511f9f9fe
fetch rnnoise-0.2.tar.gz https://codeload.github.com/xiph/rnnoise/tar.gz/refs/tags/v0.2 \
    e4a17eb1493b7551f9f7781d2acc67b8847d6ed7c4b64db0fd62c017021ae1ec
fetch rnnoise_data-0b50c45.tar.gz https://media.xiph.org/rnnoise/models/rnnoise_data-0b50c45.tar.gz \
    4ac81c5c0884ec4bd5907026aaae16209b7b76cd9d7f71af582094a2f98f4b43
tar xf "$work/src/webrtc-2.1.tar.xz" -C "$work/src"
tar xf "$work/src/rnnoise-0.2.tar.gz" -C "$work/src"
tar xf "$work/src/rnnoise_data-0b50c45.tar.gz" -C "$work/src/rnnoise-0.2"
if [ ! -x "$work/build-env/bin/python" ]; then uv venv "$work/build-env"; fi
uv pip install --python "$work/build-env/bin/python" meson==1.7.0 ninja==1.11.1.3
export PATH="$work/build-env/bin:$PATH"
# The upstream wrap pins Abseil 20240722.0 and its Meson patch by SHA-256.
if [ -f "$work/webrtc-build/meson-private/coredata.dat" ]; then
    meson setup --reconfigure "$work/webrtc-build" "$work/src/webrtc-audio-processing-2.1"
else
    meson setup "$work/webrtc-build" "$work/src/webrtc-audio-processing-2.1" \
        --buildtype release --prefix "$work/install"
fi
meson compile -C "$work/webrtc-build" -j 4
meson install -C "$work/webrtc-build"
(
    cd "$work/src/rnnoise-0.2"
    # Host-specific benchmark binary, never redistribute it to another CPU.
    gcc -O3 -march=native -fPIC -shared -Iinclude -Isrc \
        src/denoise.c src/rnn.c src/pitch.c src/kiss_fft.c src/celt_lpc.c \
        src/nnet.c src/nnet_default.c src/parse_lpcnet_weights.c \
        src/rnnoise_data.c src/rnnoise_tables.c -lm -o "$work/librnnoise.so"
)
(
    cd "$work/src"
    apt-get download libspeexdsp-dev=1.2.1-1ubuntu3 libspeexdsp1=1.2.1-1ubuntu3
    printf '%s\n' \
        '89396abffb3013df467ce2be10c27914a1e63670c3d50ccbc2be62cdb0880fe9  libspeexdsp-dev_1.2.1-1ubuntu3_amd64.deb' \
        'c16ccd12c2964ca5f30bd25670651550cce2d611cce2952c4807de44244da5a1  libspeexdsp1_1.2.1-1ubuntu3_amd64.deb' | sha256sum -c -
    dpkg-deb -x libspeexdsp-dev_1.2.1-1ubuntu3_amd64.deb "$work/speex"
    dpkg-deb -x libspeexdsp1_1.2.1-1ubuntu3_amd64.deb "$work/speex"
)
g++ -std=c++20 -O3 -Wall -Wextra -Wpedantic -DWEBRTC_POSIX \
    -isystem "$work/src/webrtc-audio-processing-2.1/subprojects/abseil-cpp-20240722.0" \
    -isystem "$work/install/include/webrtc-audio-processing-2" \
    -isystem "$work/src/rnnoise-0.2/include" -isystem "$work/speex/usr/include" \
    tools/denoise-compare/probe.cpp \
    -L"$work/install/lib/x86_64-linux-gnu" -L"$work" \
    -L"$work/speex/usr/lib/x86_64-linux-gnu" \
    -Wl,-rpath,"$work/install/lib/x86_64-linux-gnu:$work:$work/speex/usr/lib/x86_64-linux-gnu" \
    -lwebrtc-audio-processing-2 -lrnnoise -lspeexdsp -o "$work/probe"
