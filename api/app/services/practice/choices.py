"""Multiple choice: the word and meanings to pick from, or the meaning and words to pick from."""
from __future__ import annotations

import random

from ...db import cursor
from ...errors import validation_error
from .. import pictures, progress, word_sets

from .limits import CHOICES


def choice_cards(conn, user_id: int, language: str, limit: int, direction: str = "meaning", set_filter=None, rng=random,
                 due: bool = False) -> dict:
    """Multiple choice from the learner's own words that have a meaning. direction "meaning": the word is shown and the options are
    meanings; direction "word": the meaning is shown and the options are words. Each card has up to CHOICES different options
    (the answer and other entries of the learner's own list); fewer than two entries in the set means nothing to choose between.
    With due=True the questions are the words that are due (then never-practised ones); the other options still come from the whole set."""
    if direction not in ("meaning", "word", "picture"):
        raise validation_error("Choose meaning, word or picture.")
    picture = direction == "picture"          # the picture of a word is shown and the options are words; no meaning is needed
    extra, params = word_sets.filter_clause(set_filter)
    with cursor(conn) as cur:
        cur.execute("SELECT id, word, meaning FROM tutor.words WHERE user_id = %s AND language = %s "
                    + ("" if picture else "AND meaning IS NOT NULL AND btrim(meaning) <> ''") + extra, [user_id, language, *params])
        rows = cur.fetchall()
        asked = progress.due_rows(cur, user_id, language, *word_sets.filter_clause(set_filter, "w.set_id"), need_meaning=not picture) if due else None
    pics = pictures.by_word(conn, [r["id"] for r in rows]) if picture else {}
    if picture:
        if asked is not None:
            asked = [r for r in asked if r["id"] in pics]
        else:
            asked = [r for r in rows if r["id"] in pics]
    if len(rows) < 2:
        return {"items": [], "total": len(asked if asked is not None else rows)}
    if asked is None:
        rng.shuffle(rows)
        asked = rows
    elif picture and not due:
        rng.shuffle(asked)
    items = []
    for row in asked[:limit]:
        if picture:                       # the picture is the question; the meaning (if any) is only for a screen reader, which cannot see it
            prompt, answer = (row["meaning"] or "").strip(), row["word"]
        else:
            prompt, answer = (row["word"], row["meaning"]) if direction == "meaning" else (row["meaning"], row["word"])
        pool = [(r["meaning"] if direction == "meaning" else r["word"]) for r in rows if r["id"] != row["id"]]
        others = []
        for text in rng.sample(pool, len(pool)):
            if text.strip().casefold() != answer.strip().casefold() and text not in others:
                others.append(text)
            if len(others) == CHOICES - 1:
                break
        options = [answer] + others
        rng.shuffle(options)
        items.append({"id": row["id"], "prompt": prompt, "answer": answer, "choices": options, "direction": direction,
                      **({"picture": pics[row["id"]]} if picture else {})})
    return {"items": items, "total": len(asked)}
