"""One word-normalising and validating rule for every entry point (API, CSV upload, Add Word tool).

Validation doubles as a prompt-injection guard: vocabulary is pasted into the story prompt, so a
'word' containing a newline and instructions must never be stored.
"""
from __future__ import annotations

import unicodedata

# Same edge punctuation the existing Add Word component strips (an Agent may wrap words in quotes).
EDGE_CHARS = " \t\r\n.,!?;:\"'\u201c\u201d\u2018\u2019\u00ab\u00bb()[]{}\u2026" \
             "\u3002\uff01\uff1f\u3001\uff0c\uff1b\uff1a\u300c\u300d\u300e\u300f\uff08\uff09"

MAX_WORD_CHARS = 40
MAX_WORD_PARTS = 5
MAX_MEANING_CHARS = 120
CASE_SENSITIVE_LANGUAGES = {"de"}   # German nouns are capitalised
_ALLOWED_PUNCT = {"'", "\u2019", "-", " "}


class WordError(ValueError):
    """The word cannot be stored; the message is safe to show to the learner."""


def normalize_word(word, language: str = "en") -> str:
    text = unicodedata.normalize("NFC", word or "")
    text = " ".join(text.split()).strip(EDGE_CHARS)
    text = " ".join(text.split())
    return text if language in CASE_SENSITIVE_LANGUAGES else text.lower()


def validate_word(word, language: str = "en") -> str:
    """Return the canonical word or raise WordError."""
    text = normalize_word(word, language)
    if not text:
        raise WordError("Word is empty.")
    if len(text) > MAX_WORD_CHARS:
        raise WordError(f"Word is longer than {MAX_WORD_CHARS} characters.")
    if len(text.split(" ")) > MAX_WORD_PARTS:
        raise WordError(f"Use at most {MAX_WORD_PARTS} words per entry.")
    for ch in text:
        cat = unicodedata.category(ch)
        if not (cat[0] in ("L", "M") or ch in _ALLOWED_PUNCT):
            raise WordError("Words may contain only letters, apostrophes, hyphens and spaces.")
    return text


def validate_meaning(meaning) -> str | None:
    """Optional note in the learner's native language. Single line, no control characters."""
    text = " ".join((meaning or "").split())
    if not text:
        return None
    if len(text) > MAX_MEANING_CHARS:
        raise WordError(f"Meaning is longer than {MAX_MEANING_CHARS} characters.")
    if any(unicodedata.category(ch)[0] == "C" for ch in text):
        raise WordError("Meaning contains control characters.")
    return text
