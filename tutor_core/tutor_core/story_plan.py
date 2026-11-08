"""Plan constraints (8 Nov 2026, the cascade plan). OFF unless STORY_PLAN=1.

Models given a long word list use far more of it than the tier asks (a "3 words" story that used all 12), and the story turns into a word
list in sentences. So the prompt names only about one learner word per 17 words of the target length (never fewer than the tier asks for), and
says how many may be used at most (1.5 times that). The other words of the list are simply not mentioned.
"""
from __future__ import annotations

import math

from .vocab import sample_words

WORDS_PER_FEATURED = 17
MAX_FACTOR = 1.5


def featured_count(difficulty: dict) -> tuple[int, int, int]:
    """(words to name, the fewest to use, the most to use) for a tier's targets."""
    own = int(difficulty.get("own_words") or 1)
    named = max(own, round(int(difficulty["length"]) / WORDS_PER_FEATURED))
    return named, own, math.ceil(named * MAX_FACTOR)


def plan_words(words: list, difficulty: dict, language: str, rng=None) -> tuple[list, str]:
    """(the words to name in the prompt, a sentence to add to it)."""
    named, low, high = featured_count(difficulty)
    chosen = sample_words(words, named, rng) if len(words) > named else list(words)
    low = min(low, len(chosen))
    high = max(low, min(high, len(chosen)))
    note = (f"Use between {low} and {high} of the words listed above, each inside a natural sentence. You do not need to use all of them, "
            "and the text must not read like a list of words.")
    return chosen, note
