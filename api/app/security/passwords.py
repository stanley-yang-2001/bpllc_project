"""Passwords: the rules a new one must meet, salting and bcrypt hashing, checking, and the dummy used to keep timing even."""
from __future__ import annotations

import base64
import hashlib
import secrets

import bcrypt

MAX_PASSWORD_BYTES = 72          # bcrypt silently ignores anything after byte 72, so we reject instead
MIN_PASSWORD_CHARS = 8


def check_password_rules(v: str) -> str:
    """The rules a new password must meet (sign-up and the account page share them)."""
    if len(v) < MIN_PASSWORD_CHARS:
        raise ValueError(f"must be at least {MIN_PASSWORD_CHARS} characters")
    if len(v.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
    return v


def new_salt() -> str:
    """16 random bytes as hex, made per password and stored in the users table beside the hash."""
    return secrets.token_hex(16)


def _salted_input(password: str, salt: str) -> bytes:
    """How the salt and the password are combined: SHA-256 over salt bytes followed by the password bytes,
    base64-encoded (44 bytes, so bcrypt's 72-byte limit can no longer cut a long password short)."""
    return base64.b64encode(hashlib.sha256(bytes.fromhex(salt) + password.encode()).digest())


def hash_password(password: str, salt: str, rounds: int = 12) -> str:
    """bcrypt of the salted digest. bcrypt adds its own salt inside the hash string as well."""
    return bcrypt.hashpw(_salted_input(password, salt), bcrypt.gensalt(rounds)).decode()


def verify_password(password: str, password_hash: str, salt: str | None = None) -> bool:
    """With a salt: the current scheme. With None: an account from before salts, plain bcrypt (upgraded at login)."""
    try:
        if salt is None:
            return bcrypt.checkpw(password.encode()[:MAX_PASSWORD_BYTES], password_hash.encode())
        return bcrypt.checkpw(_salted_input(password, salt), password_hash.encode())
    except ValueError:
        return False


def make_dummy_credentials(rounds: int = 12) -> tuple[str, str]:
    """(salt, hash) checked when the email isn't registered, so response time doesn't reveal which addresses have accounts."""
    salt = new_salt()
    return salt, hash_password("not-a-real-password", salt, rounds)
