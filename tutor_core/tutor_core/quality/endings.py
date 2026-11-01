"""Does a passage end where a sentence ends, and not on a word that cannot end one?"""
from __future__ import annotations

from .vocabulary import _TOKEN, _norm
import re

_CLOSERS = "\"'\u201d\u2019\u00bb\u300d\u300f)\uff09]*_ \t"
_TERMINALS = ".!?\u2026\u3002\uff01\uff1f\u061f\u0964"


_COMMAS = re.compile(r"[,\uff0c\u3001]")
_CJK_LINE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def _is_signature(line: str) -> bool:
    """A letter ends with its signature, which is not a sentence: a bare name ("Pierre", "李华") or a closing and a name ("Cheers, Pierre",
    "Con cariño, Ana", "再见，李华"). Never a speaker line ("Ben: Adi") and never a cut-off phrase: a bare name is one capitalised word, or at
    most four characters without spaces in Chinese, Japanese and Korean."""
    line = line.strip()
    if not line or line[-1] in _TERMINALS or ":" in line or "\uff1a" in line:
        return False
    unspaced = bool(_CJK_LINE.search(line))
    parts = _COMMAS.split(line)
    if len(parts) == 1:
        return len(line) <= 4 and " " not in line if unspaced else len(line.split()) == 1 and line[0].isupper()
    closing, name = parts[0].strip(), parts[-1].strip()
    if len(parts) != 2 or not closing or not name:
        return False
    if unspaced:
        return len(closing) <= 8 and len(name) <= 6 and " " not in name
    return len(closing.split()) <= 4 and len(name.split()) <= 3 and name[0].isupper()


def ends_complete(text: str) -> bool:
    """Does the passage end like a finished sentence? A story cut off by the model's answer limit ends mid-word ("...따뜻하게 잠"),
    which the length and word checks do not see (25 Oct, Korean Hard). A letter's signature on its own last line is allowed when the
    line before it is a finished sentence (31 Oct, a Chinese letter ended "再见，李华")."""
    stripped = (text or "").rstrip().rstrip(_CLOSERS)
    if bool(stripped) and stripped[-1] in _TERMINALS:
        return True
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return len(lines) >= 2 and _is_signature(lines[-1]) and ends_complete("\n".join(lines[:-1]))


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


