"""Import a trusted, pre-generated EMA pack; never run inference in management."""

import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from psycopg import Error
from psycopg.types.json import Jsonb
from alojan_contracts.assets import validate_manifest, validate_wav
from alojan_contracts.configuration import EnginePreset, canonical_digest

from alojan.auth import AuthError, audit, connection
from alojan.catalog import qualified_model
from alojan.profiles import validate_draft


def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        import stat

        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Asset must be a regular file")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Asset exceeds size limit")
    return data


def install_pack(root, scope, manifest, files):
    parent = Path(root).resolve() / str(uuid.UUID(str(scope)))
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = parent / manifest.speech_digest
    payloads = {
        **files,
        "manifest.json": json.dumps(manifest.model_dump(), sort_keys=True).encode(),
    }
    staging = Path(tempfile.mkdtemp(prefix=".preparing-", dir=parent))
    try:
        for name, data in payloads.items():
            with (staging / name).open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        fd = os.open(staging, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.rename(staging, target)
        except OSError as exc:
            if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                raise
            # A concurrent import may have won. Never replace immutable prepared files.
            if target.is_symlink() or any(
                read_regular(target / name, 500000) != data for name, data in payloads.items()
            ):
                raise ValueError("Conflicting prepared pack") from None
        fd = os.open(parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target


def import_pack(dsn, scope, preparation, source, root):
    scope, preparation = uuid.UUID(str(scope)), uuid.UUID(str(preparation))
    source = Path(source)
    with connection(dsn) as conn:
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))
        row = conn.execute(
            """SELECT profile_id,content,content_digest,model_revision,speech_digest
            FROM agent_preparations WHERE scope_id=%s AND id=%s""",
            (scope, preparation),
        ).fetchone()
        if not row:
            raise AuthError("not_found", 404)
        draft = validate_draft(row[1])
        if draft.digest() != row[2]:
            raise ValueError("Preparation digest mismatch")
        model = qualified_model(conn, draft.model, row[3])
        preset = EnginePreset.model_validate(model["preset"])
        manifest = validate_manifest(
            json.loads(read_regular(source / "manifest.json", 8192)), draft, preset
        )
        if manifest.speech_digest != row[4]:
            raise ValueError("Preparation speech identity mismatch")
        files = {}
        for name in draft.speech_texts():
            data = read_regular(source / f"{name}.wav", 500000)
            validate_wav(
                data,
                getattr(manifest, name),
                leading_silence_ms=preset.greeting_pad_ms if name == "greeting" else 0,
            )
            files[f"{name}.wav"] = data
        target = install_pack(root, scope, manifest, files)
        digest = canonical_digest(manifest.model_dump())
        conn.execute(
            """INSERT INTO prepared_voice_assets(scope_id,speech_digest,manifest,manifest_digest)
            VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (scope, manifest.speech_digest, Jsonb(manifest.model_dump()), digest),
        )
        stored = conn.execute(
            "SELECT manifest_digest FROM prepared_voice_assets WHERE scope_id=%s AND speech_digest=%s",
            (scope, manifest.speech_digest),
        ).fetchone()[0]
        if stored != digest:
            raise ValueError("Conflicting prepared manifest")
        audit(conn, None, "agent.assets_imported", scope=scope, target=row[0])
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=uuid.UUID, required=True)
    parser.add_argument("--preparation", type=uuid.UUID, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    try:
        import_pack(
            os.environ["ALOJAN_DATABASE_URL"], args.scope, args.preparation, args.pack, args.store
        )
    except (AuthError, ValueError, OSError, Error):
        raise SystemExit(
            "Asset import failed; check preparation, trusted pack and private store"
        ) from None
    print("Voice pack verified and installed; no routing was changed.")


if __name__ == "__main__":
    main()
