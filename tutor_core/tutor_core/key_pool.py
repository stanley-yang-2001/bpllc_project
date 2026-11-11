"""Several Groq keys for the same model, used one after another (11 Nov 2026).

Groq counts the free tier per account and per model, so a second key for the SAME model is a second allowance. A key's variable name is
its base name plus an optional number: GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3 ... (up to _9); the same for GROQ_QWEN_API_KEY,
GROQ_JUDGE_API_KEY and GROQ_AUDIT_API_KEY. Two names holding the same key count once.

`rotating(call, pool)` wraps a call `call(prompt, key_var)`:
  * it uses the first key that is not blocked and not over its budget, and keeps using it while it works;
  * a rate-limit error (a minute's limit or the daily one) blocks THAT key for the time the error names (a minute if it names none) and the
    same prompt is tried at once on the next key, so no time is lost;
  * `budget` (tokens a key may spend, estimated from the text size; 0 = no budget) switches BEFORE the limit: a key whose estimated spend plus
    this call would go over its budget is skipped while another key has room;
  * when every key is blocked, the last error is raised, so `patient` waits it out (a short hint) or the run stops with --resume (a daily limit).
Any other error is raised at once. The clock is a parameter so tests do not wait. Keys are never printed: only the variable names."""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

from .patient import _tokens, is_rate_limit, wait_hint

MAX_KEYS = 9
PLACEHOLDER = "your-groq-api-key-here"
DEFAULT_BLOCK_SECONDS = 60.0


def key_vars(base: Optional[str] = None, environ=None) -> list[Optional[str]]:
    """The variable names of the keys for one step, in order. The first is `base` (None means GROQ_API_KEY itself, which is also what a
    step with no key of its own falls back to); duplicates and empty or placeholder values are left out."""
    environ = os.environ if environ is None else environ
    own = bool(base and (environ.get(base) or "").strip())
    base_name = base if own else "GROQ_API_KEY"          # a step with no key of its own falls back to GROQ_API_KEY and its numbered extras
    names = [base if own else None] + [f"{base_name}_{n}" for n in range(2, MAX_KEYS + 1)]
    out, seen = [], set()
    for name in names:
        value = (environ.get(name or "GROQ_API_KEY") or "").strip()
        if not value or value == PLACEHOLDER or value in seen:
            continue
        seen.add(value)
        out.append(name)
    return out


class KeyPool:
    def __init__(self, names: list, budget: int = 0, clock=time.monotonic, say: Optional[Callable] = None):
        self.names = list(names) or [None]
        self.budget, self.clock, self.say = max(0, int(budget)), clock, say
        self.spent = {n: 0 for n in self.names}
        self.blocked_until = {n: 0.0 for n in self.names}
        self.current = 0
        self.events: list[str] = []
        self.last_error: Optional[Exception] = None

    @staticmethod
    def label(name: Optional[str]) -> str:
        return name or "GROQ_API_KEY"

    def _note(self, text: str) -> None:
        self.events.append(text)
        if self.say:
            self.say("  " + text)

    def pick(self, cost: int) -> Optional[str]:
        """The key to use now, or "" when none is free (None is a valid key name: GROQ_API_KEY). The current key is kept while it is free."""
        now = self.clock()
        order = [(self.current + k) % len(self.names) for k in range(len(self.names))]
        free = [i for i in order if self.blocked_until[self.names[i]] <= now]
        if not free:
            return ""
        roomy = [i for i in free if not self.budget or self.spent[self.names[i]] + cost <= self.budget]
        i = (roomy or [min(free, key=lambda j: self.spent[self.names[j]])])[0]
        if i != self.current:
            why = "over its budget" if roomy and self.blocked_until[self.names[self.current]] <= now else "at its limit"
            self._note(f"switching key {self.label(self.names[self.current])} -> {self.label(self.names[i])} ({why})")
            self.current = i
        return self.names[i]

    def spend(self, name: Optional[str], tokens: int) -> None:
        self.spent[name] += tokens

    def block(self, name: Optional[str], seconds: float) -> None:
        self.blocked_until[name] = self.clock() + seconds


def rotating(call: Callable[[str, Optional[str]], str], pool: KeyPool) -> Callable[[str], str]:
    """`call(prompt, key_var)` -> a `prompt -> text` function that moves to the next key at a rate limit."""
    if len(pool.names) < 2 and not pool.budget:
        return lambda prompt: call(prompt, pool.names[0])      # one key: exactly the old behaviour

    def wrapped(prompt: str) -> str:
        cost = _tokens(prompt)
        while True:
            name = pool.pick(cost)
            if name == "":
                raise pool.last_error or RuntimeError("every key is at its limit")
            try:
                out = call(prompt, name)
            except Exception as error:      # noqa: BLE001 - only a rate limit moves on; everything else is raised
                if not is_rate_limit(error):
                    raise
                hint = wait_hint(error)
                pool.last_error = error
                pool.block(name, hint if hint is not None else DEFAULT_BLOCK_SECONDS)
                pool._note(f"{pool.label(name)} is rate limited" + (f" (try again in {hint:.0f}s)" if hint is not None else ""))
                continue
            pool.spend(name, cost)
            return out
    return wrapped
