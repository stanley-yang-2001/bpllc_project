"""The short-lived story cache.

It exists only because the top-level Agent has been seen calling the story tool 3 to 5 times for one request. It is keyed by
(learner, language, type, topic, ...): the earlier language-only key would have served one learner's story, built from their
words, to another learner. Successes and failures are kept for different times: a success is reusable for a while, a failure only
briefly, so repeated Agent calls during a rate limit do not each re-run the retries but a genuine retry a bit later still gets a
real attempt. A dict, so tests can clear it and look at its keys."""
from __future__ import annotations

SUCCESS_TTL_SECONDS = 20
FAILURE_TTL_SECONDS = 15


class StoryCache(dict):
    def fresh(self, key, now: float):
        """The remembered result, or None when there is none or it is too old for what it was."""
        if key not in self:
            return None
        stamp, result = self[key]
        return result if now - stamp < (SUCCESS_TTL_SECONDS if result.ok else FAILURE_TTL_SECONDS) else None

    def remember(self, key, now: float, result):
        self[key] = (now, result)
        return result
