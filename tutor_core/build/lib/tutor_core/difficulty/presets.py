"""The three presets (Easy, Medium, Hard), the limits for the learner's own targets, and the note that goes into the story prompt."""
from __future__ import annotations

from typing import Optional


TIERS = {
    "easy": {"length": 60, "own_words": 3, "uncommon_pct": 5},
    "medium": {"length": 110, "own_words": 5, "uncommon_pct": 10},
    "hard": {"length": 200, "own_words": 8, "uncommon_pct": 20},
}
TIER_NAMES = tuple(TIERS) + ("custom",)
LIMITS = {"length": (20, 400), "own_words": (1, 30), "uncommon_pct": (0, 50)}   # (min, max), inclusive
LENGTH_TOLERANCE = 0.25        # a story within 25% of the target length counts as meeting it (24 Oct: Korean 134 words for 200 asked passed at 35%)
UNCOMMON_SLACK = 5             # and one with at most this many points more uncommon words than asked
CHARS_PER_WORD = 1.6           # Chinese and Japanese: a target of N words is about N * 1.6 characters
UNSPACED = ("zh", "ja")        # Chinese and Japanese put no spaces between words, so sizes are in characters


def is_unspaced(language: str) -> bool:
    return language in UNSPACED


def resolve(tier, length=None, own_words=None, uncommon_pct=None) -> Optional[dict]:
    """The targets for a request, as {"tier", "length", "own_words", "uncommon_pct"}, or None for "no difficulty asked".
    A preset takes no extra numbers. "custom" starts from the medium targets and takes the learner's own numbers.
    Raises ValueError (with a message fit to show) for anything else."""
    if tier is None or (isinstance(tier, str) and tier.strip().lower() in ("", "any")):
        if any(v is not None for v in (length, own_words, uncommon_pct)):
            raise ValueError("Choose Custom to set your own numbers.")
        return None
    name = tier.strip().lower() if isinstance(tier, str) else None
    if name not in TIER_NAMES:
        raise ValueError("Pick Easy, Medium, Hard or Custom.")
    given = {"length": length, "own_words": own_words, "uncommon_pct": uncommon_pct}
    if name != "custom":
        if any(v is not None for v in given.values()):
            raise ValueError("Choose Custom to set your own numbers.")
        return {"tier": name, **TIERS[name]}
    targets = dict(TIERS["medium"])
    for key, value in given.items():
        if value is None:
            continue
        lo, hi = LIMITS[key]
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise ValueError(f"{key.replace('_', ' ')} must be a whole number from {lo} to {hi}.")
        targets[key] = value
    return {"tier": "custom", **targets}


def _unit(language: str) -> str:
    return "characters" if is_unspaced(language) else "words"


def ask_size(code: str, length: int) -> int:
    """The size the prompt asks for, in words. Measured 25 Oct on Groq: longer Chinese and Japanese stories come out at about 70 to
    80% of what is asked and long Korean ones at about 58%, so the prompt asks for more. The report still judges against `length`."""
    factor = 1.0
    if code == "zh":
        factor = 1.2 if 100 <= length < 150 else (1.3 if length >= 150 else 1.0)
    elif code == "ja" and length >= 150:
        factor = 1.3
    elif code == "ko" and length >= 150:
        factor = 1.5
    return round(length * factor)
