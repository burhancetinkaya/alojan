#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
# Avoid OpenBLAS spinning many CPU workers for small mel-feature matrices.
export OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$root/services/asr:$root/services/voice-contracts:$root/generated/python"
# Let uv parse the private dotenv file; never execute it as shell code.
if [ -f "$root/.local/asr.env" ]; then
    backend=$(uv run --frozen --project services/asr --env-file "$root/.local/asr.env" python -c 'import os; print(os.environ.get("ALOJAN_ASR_BACKEND", "whisper"))')
else
    backend=${ALOJAN_ASR_BACKEND:-whisper}
fi
case "$backend" in
    whisper)
        project=services/asr
        # CUDA libraries must be discoverable before CTranslate2 is imported.
        asr_libs=$(uv run --frozen --project "$project" python -c 'import nvidia.cublas.lib, nvidia.cudnn.lib; from pathlib import Path; print(str(Path(nvidia.cublas.lib.__file__).parent) + ":" + str(Path(nvidia.cudnn.lib.__file__).parent))')
        export LD_LIBRARY_PATH="$asr_libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        ;;
    nemotron) project=services/asr-nemotron ;;
    *) echo 'ALOJAN_ASR_BACKEND must be whisper or nemotron' >&2; exit 2 ;;
esac
export ALOJAN_ASR_BACKEND="$backend"
if [ -f "$root/.local/asr.env" ]; then
    exec uv run --frozen --project "$project" --env-file "$root/.local/asr.env" python -m alojan_asr "$@"
fi
exec uv run --frozen --project "$project" python -m alojan_asr "$@"
