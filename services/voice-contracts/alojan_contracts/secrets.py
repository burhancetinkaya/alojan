"""Authenticated credential envelopes, bound to their workspace and opaque identity."""

import json
from pathlib import Path
import uuid

from cryptography.fernet import Fernet


class SecretBox:
    def __init__(self, key):
        self.cipher = Fernet(key)

    @classmethod
    def from_file(cls, path):
        with Path(path).open("rb") as source:
            return cls(source.read(128).strip())

    @staticmethod
    def identity(scope, reference, purpose="openrouter"):
        if purpose not in {
            "openrouter",
            "telegram",
            "http",
            "mcp",
            "mcp-oauth-access",
            "mcp-oauth-refresh",
            "mcp-oauth-verifier",
        }:
            raise ValueError("invalid credential purpose")
        return [str(uuid.UUID(str(scope))), str(uuid.UUID(str(reference))), purpose]

    @staticmethod
    def validate(value, *, purpose="openrouter"):
        minimum, maximum = (1, 4096) if purpose.startswith("mcp-oauth-") else (16, 512)
        if (
            not isinstance(value, str)
            or not minimum <= len(value) <= maximum
            or any(not 33 <= ord(c) <= 126 for c in value)
        ):
            raise ValueError("invalid provider credential")
        return value

    def seal(self, scope, reference, value, *, purpose="openrouter"):
        return self.cipher.encrypt(
            json.dumps(
                [self.identity(scope, reference, purpose), self.validate(value, purpose=purpose)]
            ).encode()
        )

    def open(self, scope, reference, ciphertext, *, purpose="openrouter"):
        try:
            identity, value = json.loads(self.cipher.decrypt(ciphertext))
            if identity != self.identity(scope, reference, purpose):
                raise ValueError()
            return self.validate(value, purpose=purpose)
        except Exception:
            raise ValueError("provider credential unavailable") from None
