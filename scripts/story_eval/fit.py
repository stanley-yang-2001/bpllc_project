"""Does a story sit at the level it was asked for? (19 Nov 2026)

The level note in the story prompt says how long a sentence should be: "about 5 to 8 words" (easy), 8 to 12 (medium), 10 to 16 (hard) (tutor_core/difficulty/note.py).
The free score has one ruler for every level (6 to 12 words), so a hard story with 14-word sentences loses points and an easy one with 5-word sentences does too: the
score cannot say whether a story fits its OWN level. This module can, from what the run already measured (`score.measured.mean_sentence`), with no model call.

The 18 November ablation (30 English requests, 10 per level), the mean sentence inside the range the level asks for:
    baseline 13 of 30 (7 too short, 10 too long)    cascade 26 of 30    review_repair 29 of 30    cascade_pick 26 of 30
The baseline is not told the range: STORY_RANGE_PROMPT is off in the app (docker-compose passes an empty default), so it writes the same sentences at every level.
Every other method asks for the range. The `plan` method (the range prompt and the plan, no model review at all) was in range for 13 of 13 stories in the two earlier
multi-language cascade runs where the baseline was for 6 of 13: so the gain here is probably that one prompt and not the cascade or the repair. That is the claim a
30-request run of `range` and `plan` (the `controls` group) would settle.

The ranges are read from the level note itself, so this table cannot drift from what the writer was told; a test pins that."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from tutor_core import difficulty as _d
from tutor_core.difficulty.note import LEVELS

from . import stats

IN, SHORT, LONG = "in", "short", "long"
_ASKED = re.compile(r"about (\d+) to (\d+) words")


def _range_of(text: str) -> Optional[tuple]:
    found = _ASKED.search(text or "")
    return (int(found.group(1)), int(found.group(2))) if found else None


# {"easy": (5, 8), "medium": (8, 12), "hard": (10, 16)}, taken from the words the writer is given
SENTENCE_RANGE = {tier: got for tier, text in LEVELS.items() if (got := _range_of(text))}


def sentence_fit(entry: Optional[dict], tier: str, code: str) -> Optional[str]:
    """'in' when the story's mean sentence is inside the range its level asks for, 'short' or 'long' when outside. None when it cannot be told: no story, a story the
    score could not measure (gated), a language counted in characters (Chinese and Japanese, whose sentence size is not in words) or a level with no range."""
    if not entry or not entry.get("ok") or _d.is_unspaced(code) or tier not in SENTENCE_RANGE:
        return None
    mean = ((entry.get("score") or {}).get("measured") or {}).get("mean_sentence")
    if mean is None:
        return None
    low, high = SENTENCE_RANGE[tier]
    return SHORT if mean < low else LONG if mean > high else IN


def by_method(pairs: Iterable) -> dict:
    """For one method, from its (request, entry) pairs: how many stories are in the asked range, too short or too long, in all and for each level, and the 95% range of
    the share in range. {} when no story could be told."""
    total = {IN: 0, SHORT: 0, LONG: 0}
    tiers = {}
    for request, entry in pairs:
        got = sentence_fit(entry, request.get("tier"), request.get("code"))
        if got is None:
            continue
        total[got] += 1
        slot = tiers.setdefault(request["tier"], {IN: 0, SHORT: 0, LONG: 0})
        slot[got] += 1
    n = sum(total.values())
    if not n:
        return {}
    return {"stories": n, **total, "in_range": stats.wilson(total[IN], n), "tiers": tiers}


def asked(tier: str) -> str:
    """'5 to 8' for the table's column heading."""
    got = SENTENCE_RANGE.get(tier)
    return f"{got[0]} to {got[1]}" if got else "?"
