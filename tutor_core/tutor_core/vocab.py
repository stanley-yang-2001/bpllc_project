"""Per-learner, per-language vocabulary on `tutor.words` (M3, commit 2 of 2: replaces the shared `words` table).

Every function takes the learner id and the language code explicitly and refuses anything malformed. Nothing here
falls back to a shared list: a missing or unknown learner is an error, never "everyone's words". The one rule for what
a word may look like is `tutor_core.words`, shared with the API and the CSV upload, because vocabulary is pasted
into the story prompt and a word containing a newline and instructions must never be stored.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import psycopg2.errors

from .languages import LANGUAGES
from .words import WordError, validate_meaning, validate_word

__all__ = ["AddResult", "VocabError", "WordError", "add_word", "load_words", "max_prompt_words", "sample_words"]

DEFAULT_MAX_PROMPT_WORDS = 150
NO_SUCH_LEARNER = "I don't know whose vocabulary this is."


class VocabError(Exception):
    """The request itself is unusable (unknown learner or language). The message is safe to show the learner."""


@dataclass(frozen=True)
class AddResult:
    word: str
    language: str
    added: bool            # False: it was already in this learner's list for that language


def _check(learner_id, language) -> None:
    if not isinstance(learner_id, int) or isinstance(learner_id, bool) or learner_id <= 0:
        raise VocabError(NO_SUCH_LEARNER)
    if not isinstance(language, str) or language not in LANGUAGES:
        raise VocabError("That language isn't supported.")


def add_word(conn, learner_id: int, language: str, word, meaning=None) -> AddResult:
    """Store one word for one learner. Raises WordError (the word is unusable) or VocabError (learner or language)."""
    _check(learner_id, language)
    text, note = validate_word(word, language), validate_meaning(meaning)
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tutor.words (user_id, language, word, meaning) VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (user_id, language, word) DO NOTHING", (learner_id, language, text, note))
            added = cur.rowcount == 1
            if added:       # so the Vocabulary page offers the language the learner just started using
                cur.execute("INSERT INTO tutor.user_languages (user_id, language) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (learner_id, language))
        conn.commit()
    except psycopg2.errors.ForeignKeyViolation:
        conn.rollback()
        raise VocabError(NO_SUCH_LEARNER)
    except Exception:
        conn.rollback()
        raise
    return AddResult(text, language, added)


def load_words(conn, learner_id: int, language: str) -> list[str]:
    """This learner's words in this language, oldest first. Never anyone else's, never another language's."""
    _check(learner_id, language)
    with conn.cursor() as cur:
        cur.execute("SELECT word FROM tutor.words WHERE user_id = %s AND language = %s ORDER BY id", (learner_id, language))
        words = [row[0] for row in cur.fetchall()]
    conn.commit()
    return words


def sample_words(words: list[str], limit, rng=None) -> list[str]:
    """At most `limit` words, in the learner's own order. A 5,000-word list would blow Groq's token budget (design 3C)."""
    if not limit or limit <= 0 or len(words) <= limit:
        return list(words)
    rng = rng or random
    return [words[i] for i in sorted(rng.sample(range(len(words)), limit))]


def max_prompt_words(env=None) -> int:
    import os
    env = os.environ if env is None else env
    try:
        value = int((env.get("MAX_PROMPT_WORDS") or "").strip())
    except ValueError:
        return DEFAULT_MAX_PROMPT_WORDS
    return value if value > 0 else DEFAULT_MAX_PROMPT_WORDS
