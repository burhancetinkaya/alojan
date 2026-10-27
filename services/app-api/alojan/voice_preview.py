"""Scoped, bounded playback of already prepared speech; no synthesis or recordings."""

from pathlib import Path
import uuid

from alojan_contracts.assets import VoiceManifest, speech_identity, validate_wav
from alojan_contracts.configuration import EnginePreset

from alojan.auth import AuthError
from alojan.catalog import qualified_model
from alojan.profiles import locked_draft
from alojan.releases import prepared_assets
from alojan.voice_assets import read_regular


class VoicePreview:
    def __init__(self, accounts, root):
        self.accounts = accounts
        self.root = Path(root).resolve() if root else None

    def read(self, token, scope, profile, version, clip):
        with self.accounts.workspace(token, scope) as (conn, _):
            current, draft = locked_draft(conn, scope, profile)
            if current != version:
                raise AuthError("stale_version", 412)
            if clip not in draft.speech_texts():
                raise AuthError("not_found", 404)
            if self.root is None:
                raise AuthError("voice_preview_unavailable", 503)
            model = qualified_model(conn, draft.model)
            preset = EnginePreset.model_validate(model["preset"])
            manifest = VoiceManifest.model_validate(
                prepared_assets(conn, scope, speech_identity(draft, preset), draft, preset)
            )
        # Release the DB transaction before bounded disk/hash/WAV work.
        directory = self.root / str(uuid.UUID(str(scope))) / manifest.speech_digest
        try:
            if directory.resolve() != directory:
                raise ValueError("Symlinked asset directory")
            data = read_regular(directory / f"{clip}.wav", 500000)
            validate_wav(
                data,
                getattr(manifest, clip),
                leading_silence_ms=manifest.greeting_pad_ms if clip == "greeting" else 0,
            )
        except (OSError, ValueError, RuntimeError):
            raise AuthError("voice_preview_unavailable", 503) from None
        return data
