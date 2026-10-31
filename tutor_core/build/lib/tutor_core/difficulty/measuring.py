"""Measuring a finished story: its length, how many of the learner's own words it uses, and the share of uncommon words."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .. import splitter
from .presets import _unit, is_unspaced

_DATA = Path(__file__).parent.parent / "data"
_TOKEN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*[:：]\s*", re.M)    # "Ana:" or "アナ：" at the start of a line


@lru_cache(maxsize=None)
def _everyday(code: str) -> frozenset:
    path = _DATA / f"everyday_{code}.txt"
    return frozenset(path.read_text(encoding="utf-8").split()) if path.exists() else frozenset()


def has_everyday_list(code: str) -> bool:
    return bool(_everyday(code))


def can_measure_uncommon(code: str) -> bool:
    """The share of uncommon words needs the everyday list and, for Chinese, Japanese and Korean, a splitter."""
    if not has_everyday_list(code):
        return False
    return splitter.available(code) if code in splitter.SPLIT_LANGUAGES else True


def _lemma(word: str, code: str) -> str:
    """The dictionary form, when the optional simplemma package is installed (the API image has it): "llegué" is "llegar", so a
    verb form the list does not spell out still counts as the everyday word it is. Without it, the word is unchanged."""
    if code in splitter.SPLIT_LANGUAGES:
        return word
    try:
        import simplemma
        return simplemma.lemmatize(word, lang=code).casefold()
    except Exception:
        return word


def is_everyday(word: str, code: str) -> bool:
    """Is this word (or its dictionary form) among the language's everyday words? Used for the share of uncommon words and so
    that an everyday word outside the learner's list is not counted as a stray."""
    everyday = _everyday(code)
    low = word.casefold()
    if low in everyday or _lemma(low, code) in everyday:
        return True
    pieces = [p for p in re.split(r"['\u2019]", low) if len(p) > 1]
    return bool((pieces and all(p in everyday for p in pieces)) or low.replace("-", "") in everyday or all(p in everyday for p in low.split("-")))


def _tokens(text: str):
    return [m for m in _TOKEN.finditer(_LABEL.sub("", text))]


def _own_set(vocab_words, code: str) -> set:
    own = {w.casefold() for w in vocab_words if w and w.strip()}
    if code == "en":
        from ..quality import word_forms
        own = own | {f for w in list(own) for f in word_forms(w)}
    return own


def _own_found(text: str, code: str, vocab_words) -> int:
    folded = text.casefold()
    words = {w.casefold() for w in vocab_words if w and w.strip()}
    if code in splitter.SPLIT_LANGUAGES:
        tokens = splitter.split(_LABEL.sub("", folded), code)
        if tokens is not None:
            forms = {t.surface for t in tokens} | {t.base for t in tokens}
            joined = [t.surface for t in tokens]
            found = 0
            for w in words:
                # a token (or its dictionary form) is the word; a word the splitter cut in pieces is found by joining neighbours
                if w in forms or any("".join(joined[i:i + n]) == w for n in (2, 3, 4) for i in range(len(joined) - n + 1)):
                    found += 1
            return found
        return sum(1 for w in words if w in folded)          # no splitter installed: look for the word anywhere in the text
    tokens = {m.group(0).casefold() for m in _TOKEN.finditer(folded)}
    if code == "en":
        from ..quality import word_forms
        return sum(1 for w in words if tokens & set(word_forms(w)))
    return sum(1 for w in words if w in tokens)


def _covered(piece: str, everyday: frozenset) -> bool:
    """Can this chunk be cut into everyday words? The splitter keeps some phrases whole (喝牛奶, 回家路上, 很清); each part of
    them is an everyday word, so the chunk is not an unusual word. Chunks over eight characters are not tried."""
    n = len(piece)
    if n > 8:
        return False
    ok = [True] + [False] * n
    for end in range(1, n + 1):
        ok[end] = any(ok[start] and piece[start:end] in everyday for start in range(max(0, end - 4), end))
    return ok[n]


def _uncommon_split(text: str, code: str, own: set) -> Optional[float]:
    tokens = splitter.split(_LABEL.sub("", text), code)
    if tokens is None:
        return None
    everyday = _everyday(code)
    checked = uncommon = 0
    for t in tokens:
        if not t.content or t.surface.casefold() in own or t.base.casefold() in own:
            continue
        checked += 1
        if t.surface not in everyday and t.base not in everyday and not _covered(t.surface, everyday):
            uncommon += 1
    return round(100.0 * uncommon / checked, 1) if checked else 0.0


def _uncommon_share(text: str, code: str, vocab_words) -> Optional[float]:
    if not has_everyday_list(code):
        return None
    own = _own_set(vocab_words, code)
    if code in splitter.SPLIT_LANGUAGES:
        return _uncommon_split(text, code, own)
    checked = uncommon = 0
    sentence_start = True
    stripped = _LABEL.sub("", text)
    pos = 0
    for m in _TOKEN.finditer(stripped):
        between = stripped[pos:m.start()]
        if re.search(r"[.!?\u2026]\s*$|\n", between) or pos == 0:
            sentence_start = True
        pos = m.end()
        word = m.group(0)
        if word[0].isupper() and not sentence_start:       # a name in the middle of a sentence
            sentence_start = False
            continue
        sentence_start = False
        if word.casefold() in own:
            continue
        checked += 1
        if not is_everyday(word, code):
            uncommon += 1
    return round(100.0 * uncommon / checked, 1) if checked else 0.0


def measure(text: str, language_code: str, vocab_words) -> dict:
    """What the finished story measures: {"length", "length_unit", "own_words", "uncommon_pct" (None when it cannot be measured)}."""
    text = (text or "").strip()
    if is_unspaced(language_code):
        length = sum(1 for ch in _LABEL.sub("", text) if ch.isalpha())
    else:
        length = len(_tokens(text))
    return {"length": length, "length_unit": _unit(language_code), "own_words": _own_found(text, language_code, vocab_words),
            "uncommon_pct": _uncommon_share(text, language_code, vocab_words)}
