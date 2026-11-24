"""How often a learner has met each word, a story focus built on it, and the word of the day.

"Met" is two things the app already stores: the answers the learner gave to the word in practice (the review log) and the saved stories the word appears in
(the 200 newest of that language). Nothing new is stored and nothing leaves the learner's own rows. Reading a story without saving it is not counted: it is not kept.

The focus ranks the learner's own words; it never adds a word. Whatever the focus, the writer gets only words from the learner's list."""
from __future__ import annotations

import hashlib
import math
from datetime import date

from tutor_core import rewards
from tutor_core.vocab import GENERAL, clean_set_ids

from ..db import cursor
from . import pictures

STORY_BODIES = 200            # the newest saved stories of the language that are searched for the words
FOCUS_WORDS = 20              # how many words a focused story is offered (the writer plans with a few of them)
MIN_FOCUS = 5                 # a story needs this many words: a focus that finds fewer is topped up with the words met least
DUE_SOON_HOURS = 24           # "due soon" counts a word that comes due within this long
FOCUSES = ("all", "least_met", "due", "new")


def _answers(cur, user_id: int, ids: list, before=None) -> dict:
    """{word id: (answers, last answered)} for the words that were ever answered. `before`: only answers earlier than this moment (the start of today)."""
    if not ids:
        return {}
    sql = "SELECT word_id, count(*) AS n, max(reviewed_at) AS last FROM tutor.review_log WHERE user_id = %s AND word_id = ANY(%s)"
    params = [user_id, ids]
    if before is not None:
        sql += " AND reviewed_at < %s"
        params.append(before)
    cur.execute(sql + " GROUP BY word_id", params)
    return {r["word_id"]: (r["n"], r["last"]) for r in cur.fetchall()}


def _stories(cur, user_id: int, language: str, words: list, before=None) -> dict:
    """{word, lower case: saved stories it appears in}."""
    sql = "SELECT body FROM tutor.stories WHERE user_id = %s AND language = %s"
    params = [user_id, language]
    if before is not None:
        sql += " AND created_at < %s"
        params.append(before)
    cur.execute(sql + " ORDER BY created_at DESC LIMIT %s", params + [STORY_BODIES])
    return rewards.story_counts(words, [r["body"] for r in cur.fetchall()])


def for_words(conn, user_id: int, language: str, rows: list) -> list:
    """Puts each word's exposure on its row: {answers, stories, met, last_answered}, in two queries for all of them."""
    if not rows:
        return rows
    with cursor(conn) as cur:
        answers = _answers(cur, user_id, [r["id"] for r in rows])
        stories = _stories(cur, user_id, language, [r["word"] for r in rows])
    for r in rows:
        n, last = answers.get(r["id"], (0, None))
        s = stories.get((r["word"] or "").strip().casefold(), 0)
        r["exposure"] = {"answers": n, "stories": s, "met": n + s, "last_answered": last}
    return rows


def _pool(cur, user_id: int, language: str, set_ids=None) -> list:
    """The learner's words (id, word) in the chosen sets, with when each is due (None: never practised)."""
    wanted = clean_set_ids(set_ids)
    sql = ("SELECT w.id, w.word, p.due_at FROM tutor.words w LEFT JOIN tutor.word_progress p ON p.word_id = w.id "
           "WHERE w.user_id = %s AND w.language = %s")
    params = [user_id, language]
    if wanted is not None:
        sql += " AND ((w.set_id IS NULL AND %s) OR w.set_id = ANY(%s))"
        params += [GENERAL in wanted, [i for i in wanted if i > 0]]
    cur.execute(sql + " ORDER BY w.id", params)
    return cur.fetchall()


def focus_words(conn, user_id: int, language: str, set_ids, focus: str, limit: int = FOCUS_WORDS) -> dict:
    """The words a story with this focus is offered: {"words": [...], "matched": how many really fit the focus (the rest top the list up to MIN_FOCUS)}.
    least_met: the words met least. due: words due now or within DUE_SOON_HOURS, the most overdue first. new: words never practised, newest first."""
    with cursor(conn) as cur:
        pool = _pool(cur, user_id, language, set_ids)
        if not pool:
            return {"words": [], "matched": 0}
        answers = _answers(cur, user_id, [r["id"] for r in pool])
        stories = _stories(cur, user_id, language, [r["word"] for r in pool])
        cur.execute("SELECT now() + make_interval(hours => %s) AS soon", (DUE_SOON_HOURS,))
        soon = cur.fetchone()["soon"]
    met = {r["id"]: answers.get(r["id"], (0, None))[0] + stories.get(r["word"].strip().casefold(), 0) for r in pool}
    least = sorted(pool, key=lambda r: (met[r["id"]], r["id"]))
    if focus == "due":
        fit = sorted((r for r in pool if r["due_at"] is not None and r["due_at"] <= soon), key=lambda r: (r["due_at"], r["id"]))
    elif focus == "new":
        fit = sorted((r for r in pool if r["due_at"] is None), key=lambda r: -r["id"])
    else:
        fit = least
    chosen = fit[:limit]
    matched = len(chosen)
    if len(chosen) < MIN_FOCUS:
        have = {r["id"] for r in chosen}
        chosen += [r for r in least if r["id"] not in have][:MIN_FOCUS - len(chosen)]
    return {"words": [r["word"] for r in chosen], "matched": matched}


def word_of_the_day(conn, user_id: int, language: str, today: date | None = None) -> dict:
    """One of the learner's own words for today, the same all day: drawn from the quarter of the words met least (at least 5) as they stood at the start of the
    UTC day, so practising the word does not change today's pick. {"date", "word"}; the word is None when the learner has none in this language."""
    from . import progress
    with cursor(conn) as cur:
        cur.execute(f"SELECT {progress._TODAY} AS today, date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS start")
        row = cur.fetchone()
        day, start = today or row["today"], row["start"]
        pool = _pool(cur, user_id, language)
        if not pool:
            return {"date": day, "word": None}
        answers = _answers(cur, user_id, [r["id"] for r in pool], before=start)
        stories = _stories(cur, user_id, language, [r["word"] for r in pool], before=start)
    met = {r["id"]: answers.get(r["id"], (0, None))[0] + stories.get(r["word"].strip().casefold(), 0) for r in pool}
    ranked = sorted(pool, key=lambda r: (met[r["id"]], r["id"]))
    candidates = ranked[:max(MIN_FOCUS, math.ceil(len(ranked) / 4))]
    digest = hashlib.sha256(f"{user_id}:{language}:{day.isoformat()}".encode()).digest()
    pick = candidates[int.from_bytes(digest[:8], "big") % len(candidates)]
    with cursor(conn) as cur:
        cur.execute("SELECT id, language, word, meaning, pos, set_id, created_at FROM tutor.words WHERE id = %s AND user_id = %s", (pick["id"], user_id))
        word = cur.fetchone()
    for_words(conn, user_id, language, [word])
    pictures.attach(conn, [word])
    return {"date": day, "word": word}
