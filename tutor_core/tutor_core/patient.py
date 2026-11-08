"""A story function that waits out the rate limit instead of failing (7 Nov 2026).

Groq's free tier allows about 8000 tokens a minute. A comparison or refresh run of many stories hits that limit; the plain call retries
three times 1.5 seconds apart and then gives up, and the story that was being made comes out as a failure. `patient(call)` wraps any
`prompt -> text` function:

  * pacing: it keeps a rolling one-minute count of the tokens it has spent (estimated from text size) and sleeps before a call that
    would go over `tpm`, so most waits never happen;
  * waiting: on a rate-limit error it reads the "try again in 7.5s" hint (hours, minutes, seconds or milliseconds), sleeps that long
    plus a second, and tries again, up to `max_waits` times;
  * a hint longer than `max_wait_seconds` (a daily limit) is not waited for: the error is raised so a run does not sit for an hour.

Any other error is raised at once. Clock and sleep are parameters so tests do not wait."""
from __future__ import annotations

import re
import time

_HINT = re.compile(r"try again in\s+((?:\d+(?:\.\d+)?\s*(?:h|ms|m|s)\s*)+)", re.I)
_PIECE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)", re.I)
_UNIT = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
COMPLETION_ESTIMATE = 700           # tokens a reply is assumed to cost when pacing (reasoning tokens count); the runs of 7 Nov used 300 to 600


def is_rate_limit(error) -> bool:
    text = str(error).casefold()
    return "429" in text or "rate limit" in text or "rate_limit" in text


def wait_hint(error):
    """Seconds named by "try again in 7m12.96s" / "2.5s" / "850ms" in an error message; None when there is no hint."""
    found = _HINT.search(str(error))
    if not found:
        return None
    return sum(float(n) * _UNIT[u.lower()] for n, u in _PIECE.findall(found.group(1)))


def _tokens(prompt: str) -> int:
    return len(prompt) // 3 + COMPLETION_ESTIMATE


def patient(call, *, tpm: int = 7000, max_waits: int = 8, max_wait_seconds: float = 180.0, margin: float = 1.0,
            sleep=time.sleep, clock=time.monotonic, say=None):
    """Wrap `call` so a rate limit is waited out. `tpm` stays below the real limit so there is room for the estimate being off."""
    spent = []          # (time, tokens) inside the last minute

    def pace(cost):
        now = clock()
        spent[:] = [(t, n) for t, n in spent if now - t < 60.0]
        total = sum(n for _, n in spent)
        if spent and total + cost > tpm:
            wait = 60.0 - (now - spent[0][0]) + 0.5
            if wait > 0:
                if say:
                    say(f"  pacing: waiting {wait:.0f}s to stay under the token limit")
                sleep(wait)
        spent.append((clock(), cost))

    def wrapped(prompt):
        pace(_tokens(prompt))
        waits = 0
        while True:
            try:
                return call(prompt)
            except Exception as error:      # noqa: BLE001 - only a rate limit is retried; everything else is raised
                hint = wait_hint(error)
                if not is_rate_limit(error) or waits >= max_waits or (hint or 0) > max_wait_seconds:
                    raise
                waits += 1
                delay = (hint if hint is not None else 5.0 * waits) + margin
                if say:
                    say(f"  rate limited: waiting {delay:.0f}s (try {waits}/{max_waits})")
                sleep(delay)
                spent.append((clock(), _tokens(prompt)))

    return wrapped
