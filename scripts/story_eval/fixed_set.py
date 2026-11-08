"""The fixed set of requests: two per language plus two extra, the same every run (7 Nov 2026).

Each request fixes the words (a starter pack, so no database), the tier, the kind of text, the topic and the random seed, so two methods
see exactly the same job and a later run can be compared with an earlier one."""
from __future__ import annotations

from tutor_core import starter
from tutor_core.languages import LANGUAGES
from tutor_core.prompts import TOPICS

TIERS = ("easy", "medium", "hard")
KINDS = ("story", "diary", "letter", "place", "routine", "anecdote")
EXTRAS = (("en", "hard"), ("zh", "medium"))          # the two requests beyond two per language


def _request(k: int, code: str, tier: str) -> dict:
    packs = starter.pack_ids()
    pack = packs[k % len(packs)]
    words = [w for w, _ in starter.pack_words(pack, code)]
    return {"id": f"{code}-{k}", "code": code, "tier": tier, "story_type": KINDS[k % len(KINDS)], "topic": TOPICS[(k * 3) % len(TOPICS)],
            "pack": pack, "words": words, "seed": 1000 + k}


def build(languages=None, per_language: int = 2, extras: bool = True) -> list[dict]:
    """The requests for `languages` (codes; default all nine). With the default arguments this is the fixed set of 20."""
    codes = [c for c in LANGUAGES if not languages or c in languages]
    out, k = [], 0
    for code in codes:
        for _ in range(per_language):
            out.append(_request(k, code, TIERS[k % 3]))
            k += 1
    if extras:
        for code, tier in EXTRAS:
            if code in codes:
                out.append(_request(k, code, tier))
                k += 1
    return [r for r in out if r["words"]]
