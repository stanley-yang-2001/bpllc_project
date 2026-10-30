"""A request limit per learner."""
from __future__ import annotations

import time
from collections import defaultdict, deque


class RequestLimiter:
    """At most `limit` calls per learner per `window` seconds (decision 4: a learner on their own key skips the shared token
    budget but not a request limit)."""

    def __init__(self, limit: int = 10, window: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        now, hits = self.clock(), self._hits[user_id]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True
