#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
export PYTHONPATH="$root/services/asr:$root/services/voice-contracts:$root/generated/python"
# CUDA libraries must be discoverable before CTranslate2 is imported.
asr_libs=$(uv run --frozen --project services/asr python -c 'import nvidia.cublas.lib, nvidia.cudnn.lib; from pathlib import Path; print(str(Path(nvidia.cublas.lib.__file__).parent) + ":" + str(Path(nvidia.cudnn.lib.__file__).parent))')
export LD_LIBRARY_PATH="$asr_libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec uv run --frozen --project services/asr python -m alojan_asr "$@"
