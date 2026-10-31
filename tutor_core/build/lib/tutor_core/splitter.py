"""Splitting Chinese, Japanese and Korean text into words (24 Oct 2026).

These languages have no spaces between words, so the story measures (own words used, share of uncommon words) need a splitter:
Chinese: rjieba; Japanese: janome (with its bundled dictionary); Korean: kiwipiepy (a morphological analyser: it also separates
the particles and endings that stick to Korean words). All three are optional installs (`pip install tutor_core[cjk]`); without
one, `split` returns None for that language and the caller falls back to the plain character matching used before.

A token is (surface, base, content): the text as written, its dictionary form (for Japanese verbs and Korean stems), and whether
it is a content word (not a particle, ending, punctuation, number or Latin letters)."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import NamedTuple, Optional

SPLIT_LANGUAGES = ("zh", "ja", "ko")
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


class Token(NamedTuple):
    surface: str
    base: str
    content: bool


@lru_cache(maxsize=None)
def _zh():
    try:
        import rjieba
        return rjieba
    except Exception:
        return None


@lru_cache(maxsize=None)
def _ja():
    try:
        from janome.tokenizer import Tokenizer
        return Tokenizer()
    except Exception:
        return None


@lru_cache(maxsize=None)
def _ko():
    try:
        from kiwipiepy import Kiwi
        return Kiwi()
    except Exception:
        return None


def available(code: str) -> bool:
    return {"zh": _zh, "ja": _ja, "ko": _ko}.get(code, lambda: None)() is not None


def split(text: str, code: str) -> Optional[list]:
    """The tokens of `text`, or None when no splitter is installed for this language."""
    if code == "zh" and _zh():
        return [Token(w, w, bool(_CJK.search(w))) for w in _zh().cut(text) if w.strip()]
    if code == "ja" and _ja():
        out = []
        for t in _ja().tokenize(text):
            pos = t.part_of_speech.split(",")[0]
            base = t.surface if t.base_form in ("*", "") else t.base_form
            out.append(Token(t.surface, base, pos in ("名詞", "動詞", "形容詞", "副詞", "連体詞", "感動詞", "接頭詞") and bool(_CJK.search(t.surface))))
        return out
    if code == "ko" and _ko():
        out = []
        for t in _ko().tokenize(text):
            tag = t.tag
            content = tag[:1] in ("N", "V", "M") or tag in ("XR", "IC")
            base = t.form + "다" if tag.startswith("V") else t.form
            out.append(Token(t.form, base, content and bool(_CJK.search(t.form))))
        return out
    return None
