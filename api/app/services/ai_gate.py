"""The AI gate (design section 11).

Groq's free tier has one rate limit for the whole app, so every call that reaches Groq (directly or
through Langflow) first passes through here:

  * at most `slots` calls at once across all learners (default 2);
  * at most one call per learner at a time, so a double click or a second tab cannot queue two.

A caller that cannot get a slot within `wait_seconds` gets `tutor_busy` (HTTP 429, Retry-After), which the
page shows as "The tutor is busy, try again in a moment" and keeps the typed message. The routes that
use it are plain `def` functions, so they run in FastAPI's thread pool and blocking here is fine.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from ..errors import AppError


class AiGate:
    def __init__(self, slots: int = 2, wait_seconds: float = 5.0, retry_after: int = 15):
        if slots < 1:
            raise ValueError("slots must be at least 1")
        self._slots = threading.Semaphore(slots)
        self._wait = wait_seconds
        self._retry_after = retry_after
        self._mutex = threading.Lock()
        self._users: set[int] = set()
        self._in_flight = 0

    @property
    def in_flight(self) -> int:
        with self._mutex:
            return self._in_flight

    @property
    def active_users(self) -> set[int]:
        with self._mutex:
            return set(self._users)

    @contextmanager
    def slot(self, user_id: int):
        with self._mutex:
            if user_id in self._users:
                raise AppError("tutor_busy", "You already have a request in progress. Wait for it to finish.",
                               429, retry_after=5)
            self._users.add(user_id)
        try:
            if not self._slots.acquire(timeout=self._wait):
                raise AppError("tutor_busy", "The tutor is busy. Try again in a moment.", 429,
                               retry_after=self._retry_after)
            try:
                with self._mutex:
                    self._in_flight += 1
                yield
            finally:
                with self._mutex:
                    self._in_flight -= 1
                self._slots.release()
        finally:
            with self._mutex:
                self._users.discard(user_id)
