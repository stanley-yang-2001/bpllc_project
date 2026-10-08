from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict

import bcrypt
import jwt

from .errors import AppError

MAX_PASSWORD_BYTES = 72          # bcrypt silently ignores anything after byte 72, so we reject instead
LOCK_AFTER = 5
LOCK_WINDOW_SECONDS = 15 * 60


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:MAX_PASSWORD_BYTES], password_hash.encode())
    except ValueError:
        return False


def make_dummy_hash(rounds: int = 12) -> str:
    """Checked when the email isn't registered, so response time doesn't reveal which addresses have accounts."""
    return hash_password("not-a-real-password", rounds)


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
