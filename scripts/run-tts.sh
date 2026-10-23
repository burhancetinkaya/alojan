#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
export PYTHONPATH="$root/services/tts:$root/services/voice-contracts:$root/generated/python"
exec uv run --frozen --project services/tts python -m alojan_tts "$@"
