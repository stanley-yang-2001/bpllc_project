"""Does a passage end where a sentence ends, and not on a word that cannot end one?"""
from __future__ import annotations

from .vocabulary import _TOKEN, _norm
import re

_CLOSERS = "\"'\u201d\u2019\u00bb\u300d\u300f)\uff09]*_ \t"
_TERMINALS = ".!?\u2026\u3002\uff01\uff1f\u061f\u0964"


def ends_complete(text: str) -> bool:
    """Does the passage end like a finished sentence? A story cut off by the model's answer limit ends mid-word ("...따뜻하게 잠"),
    which the length and word checks do not see (25 Oct, Korean Hard)."""
    stripped = (text or "").rstrip().rstrip(_CLOSERS)
    return bool(stripped) and stripped[-1] in _TERMINALS


_DANGLING = {   # words that cannot end a sentence: the model stopped after one ("tranquilo y.", "dans le.", 25 Oct)
    "en": {"the", "a", "an", "and", "of", "with"},
    "es": {"y", "de", "del", "el", "la", "los", "las", "un", "una", "en", "con", "que", "o", "al", "por", "para"},
    "fr": {"le", "la", "les", "de", "du", "des", "un", "une", "et", "dans", "que", "avec", "pour", "sur", "au", "aux"},
    "de": {"und", "ein", "eine", "der", "den", "dem", "im", "oder"},
    "it": {"il", "lo", "la", "gli", "le", "un", "una", "e", "di", "del", "della", "che", "con", "per", "in"},
    "pt": {"o", "a", "os", "as", "um", "uma", "e", "de", "do", "da", "em", "com", "que", "para", "por"},
}


def has_dangling_sentence(text: str, code: str) -> bool:
    """Does any sentence end on an article, preposition or conjunction? Only for languages with spaces and such a list."""
    words = _DANGLING.get(code)
    if not words:
        return False
    for sentence in re.split(r"[.!?\u2026]+", _norm(text)):
        tokens = _TOKEN.findall(sentence)
        if tokens and tokens[-1].lower() in words and len(tokens) > 1:
            return True
    return False


