"""Encrypting a learner's own API key at rest (docs/CUSTOM-MODEL-DESIGN.md, section 4).

The key is encrypted with Fernet, using a key derived from MODEL_KEY_SECRET. Without that secret the custom model feature is
off for everyone: the site refuses to store a key it cannot protect. Changing the secret makes saved keys unreadable; the
learner enters them again."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class SecretsUnavailable(RuntimeError):
    pass


def _fernet(secret: str) -> Fernet:
    secret = (secret or "").strip()
    if len(secret) < 16:
        raise SecretsUnavailable("MODEL_KEY_SECRET is not set")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("tutor-model-key:" + secret).encode()).digest()))


def encrypt(secret: str, plain: str) -> str:
    return _fernet(secret).encrypt(plain.encode("utf-8")).decode("ascii") if plain else ""


def decrypt(secret: str, token: str) -> str:
    """The stored key, or "" when there is none or it cannot be read with the current secret."""
    if not token:
        return ""
    try:
        return _fernet(secret).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def last4(plain: str) -> str:
    return plain[-4:] if len(plain) >= 8 else ""
