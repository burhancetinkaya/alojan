#!/bin/sh
# Local-only SIP build: no device capture, video, or TLS dependency.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=2.16
checksum=3af2e481d51aaa095897820fa2ee26c30e530590c6ca56d23e4133bbdad369eb
archive="$root/.local/downloads/pjproject-$version.tar.gz"
prefix="$root/.local/pjsip"
mkdir -p "$root/.local/downloads"
if [ ! -f "$archive" ]; then
    curl --fail --location "https://github.com/pjsip/pjproject/archive/refs/tags/$version.tar.gz" -o "$archive"
fi
printf '%s  %s\n' "$checksum" "$archive" | shasum -a 256 -c -
# Reuse only this configuration's successful installation.
if [ -f "$prefix/.alojan-local-v1" ]; then exit 0; fi
mkdir -p "$root/.local/src"
tar -xzf "$archive" -C "$root/.local/src"
cd "$root/.local/src/pjproject-$version"
./configure --prefix="$prefix" --disable-video --disable-sound --disable-ssl \
    --disable-opencore-amr --disable-libyuv --disable-ffmpeg --disable-v4l2 \
    --disable-openh264 --disable-libwebrtc --disable-opus
make dep
make -j "${BUILD_JOBS:-4}"
make install
touch "$prefix/.alojan-local-v1"
