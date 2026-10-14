"""The AI gate (design section 11).

Groq's free tier has one rate limit for the whole app, so every call that reaches Groq (directly or
through Langflow) first passes through here:

  * at most `slots` calls at once across all learners (default 2);
  * at most one call per learner at a time, so a double click or a second tab cannot queue two;
  * at most `tokens_per_minute` tokens in any minute, app-wide (the free tier limits tokens, not calls).

A caller that cannot get a slot within `wait_seconds` gets `tutor_busy` (HTTP 429, Retry-After), which the
page shows as "The tutor is busy, try again in a moment" and keeps the typed message. The routes that
use it are plain `def` functions, so they run in FastAPI's thread pool and blocking here is fine.
"""
from __future__ import annotations

import math
import threading
import time
from contextlib import contextmanager

from ..errors import AppError


class Ticket:
    """What one call has reserved from the token budget. `settle` replaces the estimate with the real count."""

    def __init__(self, entry=None, mutex=None):
        self._entry, self._mutex = entry, mutex

    def settle(self, actual) -> None:
        if self._entry is not None and isinstance(actual, int) and not isinstance(actual, bool) and actual >= 0:
            with self._mutex:
                self._entry[1] = actual


class TokenBudget:
    """At most `per_minute` tokens in any sliding `window` seconds, for the whole app (Groq's free tier limit is
    per organisation, not per learner). A call reserves an estimate first; the reservation stays in the window even
    if the call fails, because Groq may well have counted it. 0 switches the limiter off."""

    def __init__(self, per_minute: int, window: float = 60.0, clock=time.monotonic):
        self.per_minute, self.window, self._clock = per_minute, window, clock
        self._uses: list[list] = []                       # [time, tokens], oldest first
        self._mutex = threading.Lock()

    def _prune(self, now: float) -> None:
        self._uses = [u for u in self._uses if u[0] > now - self.window]

    @property
    def used(self) -> int:
        with self._mutex:
            self._prune(self._clock())
            return sum(t for _, t in self._uses)

    def reserve(self, tokens: int) -> Ticket:
        if not self.per_minute or tokens <= 0:
            return Ticket()
        tokens = min(tokens, self.per_minute)             # one call bigger than the whole budget can still run alone
        with self._mutex:
            now = self._clock()
            self._prune(now)
            used = sum(t for _, t in self._uses)
            if used + tokens > self.per_minute:
                freed, wait = 0, self.window
                for when, count in self._uses:
                    freed += count
                    if used - freed + tokens <= self.per_minute:
                        wait = when + self.window - now
                        break
                raise AppError("tutor_busy", "The tutor is busy. Try again in a moment.", 429,
                               retry_after=max(1, math.ceil(wait)))
            entry = [now, tokens]
            self._uses.append(entry)
            return Ticket(entry, self._mutex)


class AiGate:
    def __init__(self, slots: int = 2, wait_seconds: float = 5.0, retry_after: int = 15,
                 tokens_per_minute: int = 0, clock=time.monotonic):
        if slots < 1:
            raise ValueError("slots must be at least 1")
        self._budget = TokenBudget(tokens_per_minute, clock=clock)
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
    def tokens_per_minute(self) -> int:
        return self._budget.per_minute

    @property
    def tokens_used(self) -> int:
        return self._budget.used

    @property
    def active_users(self) -> set[int]:
        with self._mutex:
            return set(self._users)

    @contextmanager
    def exclusive(self, user_id: int):
        """Claim the learner's marker without using an AI slot: for work that must not overlap one of their chat
        turns (deleting the account). Refused, like a second chat request, while one is in flight."""
        with self._mutex:
            if user_id in self._users:
                raise AppError("tutor_busy", "You already have a request in progress. Wait for it to finish.",
                               429, retry_after=5)
            self._users.add(user_id)
        try:
            yield
        finally:
            with self._mutex:
                self._users.discard(user_id)

    @contextmanager
    def slot(self, user_id: int, tokens: int = 0):
        """A place for one AI call. `tokens` is the estimate reserved from the per-minute budget; the caller
        may `settle` the yielded ticket with the real count."""
        with self.exclusive(user_id):
            ticket = self._budget.reserve(tokens)         # refused before waiting for a slot, and holds nothing if refused
            if not self._slots.acquire(timeout=self._wait):
                raise AppError("tutor_busy", "The tutor is busy. Try again in a moment.", 429,
                               retry_after=self._retry_after)
            try:
                with self._mutex:
                    self._in_flight += 1
                yield ticket
            finally:
                with self._mutex:
                    self._in_flight -= 1
                self._slots.release()
