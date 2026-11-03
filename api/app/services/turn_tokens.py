"""Throwaway tokens for chat on a learner's own model (docs/CUSTOM-MODEL-DESIGN.md section 10).

A chat turn runs inside Langflow, which must never hold the learner's real key. So the API gives Langflow a random token that
stands for ONE learner and ONE turn; Langflow sends it back to the API's internal model route, and only the API turns it into the
real key. The token expires, allows a fixed number of calls (the Agent may call the model several times in a turn), and is revoked
when the turn ends. It lives in memory: the API runs one worker (api/Dockerfile), and a restart just ends the turns in flight."""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

PREFIX = "tt-"
DEFAULT_TTL = 300.0
DEFAULT_MAX_USES = 40


@dataclass
class Grant:
    user_id: int
    expires: float
    uses_left: int
    last_error: str = ""
    calls: int = field(default=0)


class TurnTokens:
    def __init__(self, clock=time.monotonic, ttl: float = DEFAULT_TTL, max_uses: int = DEFAULT_MAX_USES):
        self.clock, self.ttl, self.max_uses = clock, ttl, max_uses
        self._grants: dict[str, Grant] = {}
        self._lock = threading.Lock()

    def issue(self, user_id: int, ttl: float | None = None) -> str:
        token = PREFIX + secrets.token_urlsafe(24)
        with self._lock:
            self._prune()
            self._grants[token] = Grant(int(user_id), self.clock() + (ttl or self.ttl), self.max_uses)
        return token

    def use(self, token: str) -> int | None:
        """The learner this token stands for, and one use is taken; None for an unknown, expired or used-up token."""
        with self._lock:
            grant = self._grants.get(token or "")
            if grant is None or grant.expires <= self.clock() or grant.uses_left <= 0:
                return None
            grant.uses_left -= 1
            grant.calls += 1
            return grant.user_id

    def note_error(self, token: str, message: str) -> None:
        with self._lock:
            if token in self._grants:
                self._grants[token].last_error = message

    def last_error(self, token: str) -> str:
        with self._lock:
            grant = self._grants.get(token)
            return grant.last_error if grant else ""

    def revoke(self, token: str) -> None:
        with self._lock:
            self._grants.pop(token, None)

    def _prune(self) -> None:
        now = self.clock()
        for key in [k for k, g in self._grants.items() if g.expires <= now]:
            del self._grants[key]

    def __len__(self) -> int:
        with self._lock:
            return len(self._grants)
