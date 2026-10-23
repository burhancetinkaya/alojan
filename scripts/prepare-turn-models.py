"""Install pinned local CPU models/headers; run with a frozen ASR or CPU-evaluation environment on Linux."""

import hashlib
from pathlib import Path
import sys
import urllib.request

import onnxruntime

ROOT = Path(__file__).resolve().parents[1]
ORT = "402979ac1bef89dcd55add41eaa7277c407599eb"
SILERO = "be95df9152c0d7618fa1edfeb296fc3dae32376f"
SMART = "f766f81d3cfdf7737ac64aad813d91bbfd56bf93"
ARTIFACTS = {
    "turn-models/silero-v6.2.onnx": (
        f"https://raw.githubusercontent.com/snakers4/silero-vad/{SILERO}/src/silero_vad/data/silero_vad.onnx",
        "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3",
    ),
    "turn-models/smart-turn-v3.2-cpu.onnx": (
        f"https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/{SMART}/smart-turn-v3.2-cpu.onnx",
        "2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f",
    ),
}
HEADERS = {
    "onnxruntime_error_code.h": "5ce3b054e798eced8d14f5b86e98692fd33470463f96194ce0700a2d53dd8721",
    "onnxruntime_ep_c_api.h": "b64036772115dbc6f06a900487ce22d34e862100db03e2ad62210758e27a19b2",
    "onnxruntime_c_api.h": "43d584f596ef66820421317df32a79a95fc1d39ee46cb3971a870c08d8ba4baa",
    "onnxruntime_cxx_api.h": "1e80d494c47091b07d84de60ad570326f82ed841c6de66e5b3eb7dce17bfc467",
    "onnxruntime_cxx_inline.h": "908a50414c3f67f32fd556cd16f7779fa78380e12e9d08e44f5e6f66b965a7be",
    "onnxruntime_float16.h": "88b242845d25981633a0bbd1c148e273cf8bfb016ea3f57c4af41a06530f72b0",
}


def main():
    if sys.platform != "linux" or onnxruntime.__version__ != "1.31.0":
        raise RuntimeError("requires Linux and the locked ONNX Runtime 1.31.0 environment")
    artifacts = ARTIFACTS | {
        f"onnxruntime/include/{name}": (
            f"https://raw.githubusercontent.com/microsoft/onnxruntime/{ORT}/include/onnxruntime/core/session/{name}",
            checksum,
        )
        for name, checksum in HEADERS.items()
    }
    for relative, (url, checksum) in artifacts.items():
        path = ROOT / ".local" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (
            path.read_bytes() if path.exists() else urllib.request.urlopen(url, timeout=60).read()
        )
        if hashlib.sha256(data).hexdigest() != checksum:
            raise RuntimeError(f"checksum mismatch: {relative}")
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
    library = Path(onnxruntime.__file__).parent / "capi/libonnxruntime.so.1.31.0"
    if not library.is_file():
        raise RuntimeError("missing locked ONNX Runtime shared library")
    target = ROOT / ".local/onnxruntime/lib"
    target.mkdir(exist_ok=True)
    for name in ["libonnxruntime.so", "libonnxruntime.so.1", "libonnxruntime.so.1.31.0"]:
        link = target / name
        if link.is_symlink():
            if link.resolve() != library.resolve():
                raise RuntimeError("unexpected existing runtime symlink")
        elif link.exists():
            raise RuntimeError("refusing to replace existing runtime library")
        else:
            link.symlink_to(library.resolve())
    print(
        "Pinned native CPU model artifacts verified; runtime linked from the selected frozen environment"
    )


if __name__ == "__main__":
    main()
