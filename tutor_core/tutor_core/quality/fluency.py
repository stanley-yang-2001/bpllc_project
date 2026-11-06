"""Does a passage read like natural text? Code checks for the signs of broken grammar that need no language model:

  * telegraphic: many very short sentences, as if the model listed words (6 Nov plan, step 4: reject above 20%);
  * the same sentence written twice;
  * almost every sentence opening with the same words.

Dialogue is not checked for short lines: "Yes." and "Hello!" are natural answers. Chinese and Japanese are counted in characters, the
other languages in words. The checks are deliberately blunt: they only name a problem the model can then be told about exactly.
"""
from __future__ import annotations

import re

from .passage import _read_shape
from .vocabulary import _TOKEN

MIN_SENTENCES = 4            # fewer sentences than this: nothing to judge
SHORT_WORDS = 4              # a sentence of fewer words than this is short (spaced languages)
SHORT_CHARS = 3              # ... fewer characters than this (Chinese, Japanese)
SHORT_SHARE = 0.20           # more than this share of short sentences is telegraphic
SAME_OPENING_SHARE = 0.60    # more than this share of the sentences opening alike (at least 5 sentences)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def _size(sentence: str, unspaced: bool) -> int:
    return len(_CJK.findall(sentence)) if unspaced else len(_TOKEN.findall(sentence))


def fluency_problems(text: str, unspaced: bool = False) -> list[str]:
    """Plain sentences that name each problem found, in words a repair prompt can use. Empty when nothing is wrong."""
    shape = _read_shape(text)
    units = [u.strip() for u in shape.unit_texts if u.strip()]
    if len(units) < MIN_SENTENCES:
        return []
    problems = []
    if shape.style != "dialogue":
        short = [u for u in units if _size(u, unspaced) < (SHORT_CHARS if unspaced else SHORT_WORDS)]
        if len(short) / len(units) > SHORT_SHARE:
            problems.append(f"{len(short)} of {len(units)} sentences are only a few words long; write complete, natural sentences "
                            "with a subject and a verb, not lists of words")
    seen, twice = set(), []
    for u in units:
        if _size(u, unspaced) < (SHORT_CHARS if unspaced else SHORT_WORDS):
            continue                       # a short line said twice ("Goodbye, friend.") is natural, not a fault
        key = re.sub(r"\W+", " ", u.casefold()).strip()
        if key in seen and key not in twice:
            twice.append(key)
        seen.add(key)
    if twice:
        problems.append("the same sentence is written more than once (for example: " + twice[0][:60] + ")")
    if len(units) >= 5 and not unspaced:
        openings = [" ".join(_TOKEN.findall(u.casefold())[:2]) for u in units]
        top = max(set(openings), key=openings.count)
        if top and openings.count(top) / len(units) > SAME_OPENING_SHARE:
            problems.append(f"most sentences begin with the same words (\"{top}\"); vary how the sentences begin")
    return problems
