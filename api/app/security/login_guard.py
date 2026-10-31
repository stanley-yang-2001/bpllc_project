"""Too many wrong passwords for one email: lock it for a while."""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from ..errors import AppError

LOCK_AFTER = 5
LOCK_WINDOW_SECONDS = 15 * 60


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
