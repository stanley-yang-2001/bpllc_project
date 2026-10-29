"""Starter word packs: a few small sets of everyday words (greetings, food and drink, people and places, numbers and days) written
out for every supported language, so a new learner can fill a list in one click instead of typing words one at a time.

Each word comes with a short English gloss. The gloss is only offered as a meaning when the learner reads English; for anyone else
the words are added without a meaning, and the tutor writes meanings in the language they chose (see definitions.py)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).parent / "data" / "starter_packs.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_FILE.read_text(encoding="utf-8"))


def pack_ids() -> list[str]:
    return [p["id"] for p in _data()["packs"]]


def has_packs(language: str) -> bool:
    return language in _data()["words"]


def pack_words(pack_id: str, language: str) -> list[tuple[str, str | None]]:
    """[(word, English gloss or None)] for one pack in one language; empty when there is no such pack or language.
    English has no gloss: the words are their own meaning."""
    data = _data()
    glosses = next((p["glosses"] for p in data["packs"] if p["id"] == pack_id), None)
    words = data["words"].get(language, {}).get(pack_id)
    if glosses is None or words is None:
        return []
    return [(w, None if language == "en" else g) for w, g in zip(words, glosses)]
