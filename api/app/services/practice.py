"""Practice material made from a learner's own words (M7). Nothing here is stored: a result is shown and forgotten."""
from __future__ import annotations

import random
import re

from tutor_core.languages import LANGUAGES
from tutor_core.quality import word_forms

from ..db import cursor

MAX_ITEMS = 8
CHOICES = 4                       # the answer plus up to three other words from the learner's own list
_TOKEN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*:\s+")       # "Ana: " at the start of a line
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")
MIN_WORDS_IN_SENTENCE = 3


def flashcards(conn, user_id: int, language: str, limit: int) -> dict:
    """Shuffled words that have a meaning (a card with nothing on its back is no use)."""
    with cursor(conn) as cur:
        cur.execute("SELECT id, word, meaning FROM tutor.words WHERE user_id = %s AND language = %s "
                    "AND meaning IS NOT NULL AND btrim(meaning) <> '' ORDER BY random() LIMIT %s", (user_id, language, limit))
        items = cur.fetchall()
        cur.execute("SELECT count(*) AS n FROM tutor.words WHERE user_id = %s AND language = %s "
                    "AND meaning IS NOT NULL AND btrim(meaning) <> ''", (user_id, language))
        return {"items": items, "total": cur.fetchone()["n"]}


def can_cloze(language: str) -> bool:
    lang = LANGUAGES.get(language)
    return bool(lang and lang.tier == 1)          # Tier 2 languages have no word splitter here yet (design 3B)


def _vocabulary(conn, user_id: int, language: str) -> dict[str, str]:
    """single-word entries only: word -> meaning. A phrase cannot be matched to one blank."""
    with cursor(conn) as cur:
        cur.execute("SELECT word, meaning FROM tutor.words WHERE user_id = %s AND language = %s ORDER BY id", (user_id, language))
        return {r["word"].lower(): (r["meaning"] or "") for r in cur.fetchall() if len(_TOKEN.findall(r["word"])) == 1}


def _units(body: str):
    for line in body.split("\n"):
        for part in _SENTENCE.split(line):
            if part.strip():
                yield part


def make_cloze(body: str, language: str, vocabulary: dict[str, str], rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    english = language == "en"
    base_of = {w: w for w in vocabulary}
    if english:
        for w in vocabulary:
            for form in word_forms(w):
                base_of.setdefault(form, w)          # an exact entry always wins over a guessed inflection
    items, used = [], set()
    for unit in _units(body):
        label = _LABEL.match(unit)
        start = label.end() if label else 0
        tokens = [m for m in _TOKEN.finditer(unit) if m.start() >= start]
        if len(tokens) < MIN_WORDS_IN_SENTENCE:
            continue
        for m in tokens:
            base = base_of.get(m.group(0).lower())
            if base and base not in used:
                used.add(base)
                others = [w for w in vocabulary if w != base]
                picks = rng.sample(others, min(CHOICES - 1, len(others)))
                choices = [m.group(0)] + picks
                rng.shuffle(choices)
                items.append({"before": unit[:m.start()], "after": unit[m.end():], "answer": m.group(0),
                              "hint": vocabulary[base], "choices": choices})
                break
        if len(items) == MAX_ITEMS:
            break
    return items
