from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
from collections import defaultdict

import bcrypt
import jwt

from .errors import AppError

MAX_PASSWORD_BYTES = 72          # bcrypt silently ignores anything after byte 72, so we reject instead
MIN_PASSWORD_CHARS = 8


def check_password_rules(v: str) -> str:
    """The rules a new password must meet (sign-up and the account page share them)."""
    if len(v) < MIN_PASSWORD_CHARS:
        raise ValueError(f"must be at least {MIN_PASSWORD_CHARS} characters")
    if len(v.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
    return v
LOCK_AFTER = 5
LOCK_WINDOW_SECONDS = 15 * 60


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


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def create_token(user_id: int, session_id: str, secret: str, hours: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "jti": session_id, "iat": now, "exp": now + hours * 3600},
                      secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> tuple[int, str] | None:
    """(user_id, session_id) for a well-formed, unexpired, correctly signed token; otherwise None.
    This only proves the token is genuine: the session row must still exist (see services/sessions.py)."""
    try:
        data = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["sub", "jti", "exp"]})
        return int(data["sub"]), str(data["jti"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


class LoginGuard:
    """5 failures per email in 15 minutes -> locked. Lives in memory: resets on restart and works only
    with a single worker process. That is acceptable for a local demo and is stated in the design."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._fails: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        cutoff = self._clock() - LOCK_WINDOW_SECONDS
        fresh = [t for t in self._fails[key] if t > cutoff]
        self._fails[key] = fresh
        return fresh

    def check(self, key: str) -> None:
        with self._lock:
            fresh = self._recent(key)
            if len(fresh) >= LOCK_AFTER:
                wait = int(fresh[0] + LOCK_WINDOW_SECONDS - self._clock()) + 1
                raise AppError("login_locked", "Too many failed attempts. Try again later.", 429, retry_after=max(wait, 1))

    def failure(self, key: str) -> None:
        with self._lock:
            self._recent(key).append(self._clock())

    def success(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)
