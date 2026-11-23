"""The reader: which of the learner's words stand in a text, and what they mean. The matching is tutor_core.story_gloss (the same rules as the
story score); this module reads the learner's words and puts the positions in the form the page uses."""
from __future__ import annotations

from tutor_core import story_gloss

from ..db import cursor
from . import pictures


def utf16_positions(text: str) -> list[int] | None:
    """For each index of the text (counted in characters), the index a JavaScript string gives it (UTF-16 units; a character outside the basic
    plane, such as an emoji, takes two). None when there is no such character, which is nearly always: the two counts are then the same."""
    if all(ord(c) <= 0xFFFF for c in text):
        return None
    out, units = [], 0
    for c in text:
        out.append(units)
        units += 2 if ord(c) > 0xFFFF else 1
    out.append(units)
    return out


def gloss(conn, user_id: int, language: str, text: str) -> dict:
    """{"spans": [{"start", "end", "word_id"}], "words": [{"id", "word", "meaning", "pos", "picture"}]} for the learner's words of this language in `text`."""
    with cursor(conn) as cur:
        cur.execute("SELECT id, word, meaning, pos FROM words WHERE user_id = %s AND language = %s ORDER BY id", (user_id, language))
        rows = cur.fetchall()
    found = story_gloss.find(text, language, ((r["id"], r["word"]) for r in rows))
    at = utf16_positions(text)
    spans = [{"start": at[s.start] if at else s.start, "end": at[s.end] if at else s.end, "word_id": s.word_id} for s in found]
    used = {s.word_id for s in found}
    words = [{"id": r["id"], "word": r["word"], "meaning": r["meaning"], "pos": r["pos"]} for r in rows if r["id"] in used]
    return {"spans": spans, "words": pictures.attach(conn, words)}
