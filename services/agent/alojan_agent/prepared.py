"""Bounded immutable release/audio preload; used only outside media callbacks.

One instance belongs to one agent event loop. Disk work runs on at most two worker
threads. Admission only pins an existing entry; no lazy disk IO or legacy fallback.
"""

import asyncio
from collections import OrderedDict
from contextlib import ExitStack
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import uuid

from alojan_contracts.assets import VoiceManifest, validate_wav
from alojan_contracts.runtime import AgentRuntime, compile_release


class PreloadError(ValueError):
    pass


def release_key(scope, release, digest):
    try:
        scope, release = str(uuid.UUID(str(scope))), str(uuid.UUID(str(release)))
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise PreloadError("invalid_preload_identity") from None
    return scope, release, digest


@dataclass(frozen=True)
class PreparedRelease:
    key: tuple[str, str, str]
    runtime: AgentRuntime
    greeting_pcm: bytes
    unavailable_pcm: bytes
    payload_bytes: int
    waiting_pcm: bytes = b""


def _read(directory, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("Non-regular asset")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Asset size limit")
    return data


def load_prepared(root, key, manifest_json):
    """Validate exact installed bytes before exposing any PCM or compiled prompt."""
    try:
        key = release_key(*key)
        if not isinstance(manifest_json, str) or len(manifest_json.encode()) > 131072:
            raise ValueError("Manifest size limit")
        runtime = compile_release(manifest_json, key[2], scope_id=key[0])
        expected = VoiceManifest.model_validate(json.loads(manifest_json)["voice_assets"])
        # Directory descriptors prevent symlink swaps of workspace/pack components.
        with ExitStack() as stack:
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, directory)
            for part in (key[0], expected.speech_digest):
                directory = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                stack.callback(os.close, directory)
            installed = VoiceManifest.model_validate(
                json.loads(_read(directory, "manifest.json", 8192))
            )
            if installed != expected:
                raise ValueError("Manifest mismatch")
            pcm = {}
            for name in ("greeting", "unavailable", *(["waiting"] if expected.waiting else [])):
                pcm[name] = validate_wav(
                    _read(directory, name + ".wav", 500000),
                    getattr(expected, name),
                    leading_silence_ms=expected.greeting_pad_ms if name == "greeting" else 0,
                )
        # Conservative text payload allowance; object overhead is also bounded by entry count.
        size = (
            len(pcm["greeting"])
            + len(pcm["unavailable"])
            + len(pcm.get("waiting", b""))
            + 4
            * (
                len(manifest_json.encode())
                + len(runtime.instructions.encode())
                + len(runtime.summary_instructions.encode())
            )
        )
        return PreparedRelease(
            key, runtime, pcm["greeting"], pcm["unavailable"], size, pcm.get("waiting", b"")
        )
    except (ValueError, OSError, EOFError, KeyError, TypeError):
        raise PreloadError("prepared_release_invalid") from None


class PreparedReleases:
    def __init__(self, root, *, max_entries=16, max_bytes=16 * 1024 * 1024):
        if type(max_entries) is not int or not 1 <= max_entries <= 128:
            raise ValueError("Invalid prepared entry limit")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 128 * 1024 * 1024:
            raise ValueError("Invalid prepared payload limit")
        self.root = Path(root).absolute()
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self.entries = OrderedDict()
        self.pins = {}
        self.pending = {}
        self.payload_bytes = 0
        self.closed = False

    async def preload(self, scope, release, manifest_json, digest):
        key = release_key(scope, release, digest)
        if (
            not isinstance(manifest_json, str)
            or len(manifest_json) > 131072
            or len(manifest_json.encode()) > 131072
        ):
            raise PreloadError("prepared_release_invalid")
        if self.closed:
            raise PreloadError("preload_closed")
        if key in self.entries:
            self.entries.move_to_end(key)
            return self.entries[key]
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= 2:
                raise PreloadError("preload_busy")
            task = asyncio.create_task(self._prepare(key, manifest_json))
            self.pending[key] = task
            # A cancelled waiter must not cancel its worker or hide a later exception.
            task.add_done_callback(
                lambda result: None if result.cancelled() else result.exception()
            )
        return await asyncio.shield(task)

    async def _prepare(self, key, manifest_json):
        try:
            prepared = await asyncio.to_thread(load_prepared, self.root, key, manifest_json)
            if self.closed:
                raise PreloadError("preload_closed")
            remaining = self.payload_bytes + prepared.payload_bytes
            count = len(self.entries) + 1
            evict = []
            for old_key, old in self.entries.items():
                if count <= self.max_entries and remaining <= self.max_bytes:
                    break
                if not self.pins.get(old_key):
                    evict.append(old_key)
                    remaining -= old.payload_bytes
                    count -= 1
            if count > self.max_entries or remaining > self.max_bytes:
                raise PreloadError("preload_capacity")
            # Failed loads/capacity checks never evict a usable existing entry.
            for old_key in evict:
                del self.entries[old_key]
            self.entries[key] = prepared
            self.payload_bytes = remaining
            return prepared
        finally:
            self.pending.pop(key, None)

    def pin(self, route):
        key = release_key(route.scope_id, route.release_id, route.manifest_digest)
        if self.closed or key not in self.entries:
            raise PreloadError("release_not_preloaded")
        self.entries.move_to_end(key)
        self.pins[key] = self.pins.get(key, 0) + 1
        return self.entries[key]

    def unpin(self, prepared):
        count = self.pins.get(prepared.key, 0)
        if count <= 1:
            self.pins.pop(prepared.key, None)
        else:
            self.pins[prepared.key] = count - 1

    async def close(self):
        self.closed = True
        await asyncio.gather(*list(self.pending.values()), return_exceptions=True)
        # Existing call references remain valid until their normal release.
        self.entries.clear()
        self.payload_bytes = 0
