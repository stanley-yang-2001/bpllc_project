"""The example bank (step 5 of the story quality plan, 6 Nov 2026): the two best-scoring stories for each language, kept in
`tutor.story_examples` (migration 0016), and the rule for updating them.

    offer(...)     a new story: kept only if it scores higher than the lower of the two saved ones (the old text and its score are
                   replaced together), or if the language has fewer than two; a story with score 0 (the gate in quality/score.py) never
                   gets in. A tie keeps the older story.
    examples(...)  the saved stories of one language, best first.
    counts(...)    how many are saved per language, so a refresh can see which languages still need stories.

Only the refresh script writes (as the database owner); the story tool's role may only read. The bank is built from seed and
starter-pack words, never from a learner's own words or topics (the owner's decision of 6 Nov 2026: a learner's text must not reach
other learners' prompts).
"""
from __future__ import annotations

import json
from typing import Optional

SLOTS = 2
GOOD_ENOUGH = 85.0            # below this a saved story is marked provisional: kept only until a better one arrives
REJECTED, ADDED, REPLACED, KEPT = "rejected", "added", "replaced", "kept"


def offer(conn, language: str, text: str, scored: dict, *, story_type: Optional[str] = None, topic: Optional[str] = None,
          two_pass: bool = False) -> str:
    """One candidate against the saved stories of its language. `scored` is the dict from quality.score_story."""
    score = float(scored.get("score") or 0)
    if scored.get("gated") or score <= 0 or not (text or "").strip():
        return REJECTED
    values = (text, score, json.dumps(scored.get("parts") or {}), int(scored.get("version") or 1), story_type, topic, bool(two_pass), score < GOOD_ENOUGH)
    with conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("story_examples:" + language,))        # two refreshes never race
        cur.execute("SELECT slot, score, score_version FROM tutor.story_examples WHERE language = %s ORDER BY score, slot", (language,))
        rows = cur.fetchall()
        if len(rows) < SLOTS:
            free = next(s for s in range(1, SLOTS + 1) if s not in {r[0] for r in rows})
            cur.execute("""INSERT INTO tutor.story_examples (language, slot, text, score, sub_scores, score_version, story_type, topic, two_pass, provisional)
                           VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)""", (language, free) + values)
            return ADDED
        version = int(scored.get("version") or 1)
        stale = [r for r in rows if int(r[2] or 1) < version]          # saved under an older score: its number cannot be compared, so it yields first
        lowest_slot, lowest = (stale or rows)[0][:2]
        if not stale and score <= float(lowest):
            return KEPT
        cur.execute("""UPDATE tutor.story_examples SET text=%s, score=%s, sub_scores=%s::jsonb, score_version=%s, story_type=%s, topic=%s,
                       two_pass=%s, provisional=%s, updated_at=now() WHERE language=%s AND slot=%s""", values + (language, lowest_slot))
        return REPLACED


def examples(conn, language: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("""SELECT slot, text, score, sub_scores, story_type, topic, two_pass, provisional, updated_at
                       FROM tutor.story_examples WHERE language = %s ORDER BY score DESC, slot""", (language,))
        cols = ("slot", "text", "score", "sub_scores", "story_type", "topic", "two_pass", "provisional", "updated_at")
        out = [dict(zip(cols, r)) for r in cur.fetchall()]
    for row in out:
        row["score"] = float(row["score"])
    conn.rollback() if getattr(conn, "autocommit", False) is False else None       # a read leaves no transaction open
    return out


def counts(conn, languages) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT language, count(*) FROM tutor.story_examples GROUP BY language")
        have = dict(cur.fetchall())
    conn.rollback() if getattr(conn, "autocommit", False) is False else None
    return {lang: int(have.get(lang, 0)) for lang in languages}


def best_for_prompt(conn, language: str) -> Optional[str]:
    """The text to show as the example for one language: the best saved story, or None (nothing saved, or the table cannot be read)."""
    try:
        rows = examples(conn, language)
    except Exception:           # the table is missing (old database) or not readable: no example, the story is written as before
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    return rows[0]["text"] if rows else None
