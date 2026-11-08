"""One shape for grammar findings, whoever finds them (7 Nov 2026, score version 3).

The story score used to see only what its fluency checks could see: a wrong article or a wrong verb ending was invisible. Three sources
can now report mistakes, from cheap and narrow to costly and broad, and all of them report a `Hit`:

    rules.py         built-in rules: no network, no model, a few mistakes that can be spotted with almost no false alarms
    languagetool.py  an optional LanguageTool server you run yourself: many more rules in 7 of the 9 languages
    audit.py         an optional model review that quotes each mistake and its fix; every quote is checked against the text

`affected_sentences` turns hits into the number the score uses: the share of sentences with no mistake in them.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Protocol, Sequence

KINDS = ("grammar", "spelling", "meaning", "style")
KIND_WEIGHT = {"grammar": 1.0, "spelling": 0.5, "meaning": 1.0, "style": 0.0}       # a style remark is shown but never costs points


@dataclass(frozen=True)
class Hit:
    source: str                  # "rules", "languagetool" or "audit"
    rule: str                    # short id, e.g. "es.contraction"
    wrong: str                   # the words as written in the text
    fix: str = ""                # what they should be ("" when the source gives none)
    kind: str = "grammar"
    start: int = -1              # offsets of `wrong` in the text; -1 when unknown
    end: int = -1
    certain: bool = False        # the fix is safe to apply without asking a model (a contraction, a doubled word)
    note: str = ""

    @property
    def weight(self) -> float:
        return KIND_WEIGHT.get(self.kind, 1.0)

    def as_dict(self) -> dict:
        return asdict(self)


class Checker(Protocol):
    name: str

    def check(self, text: str, language: str, words: Sequence[str] = ()) -> list[Hit]: ...


_END = ".!?。！？…"
_CLOSERS = "\"'”’»)]」』"


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of every sentence: it ends after . ! ? 。！？ … (and any closing quote), or at a line break. A full stop inside a
    number or between two letters ("3.5", "e.g.x") does not end one; neither does one before a lower-case letter ("Sr. Pérez" does)."""
    spans, start, i, n = [], None, 0, len(text)
    while i < n:
        ch = text[i]
        if start is None:
            if ch.strip() and ch not in "-–—•*":
                start = i
            i += 1
            continue
        if ch == "\n":
            spans.append((start, i))
            start = None
        elif ch in _END:
            j = i + 1
            while j < n and (text[j] in _END or text[j] in _CLOSERS):
                j += 1
            latin_end = ch in ".!?"
            if not latin_end or j >= n or text[j].isspace():
                prev_digit = i > 0 and text[i - 1].isdigit() and ch == "."
                if not prev_digit:
                    spans.append((start, j))
                    start, i = None, j
                    continue
        i += 1
    if start is not None and text[start:].strip():
        spans.append((start, n))
    return [(a, b) for a, b in spans if re.search(r"\w", text[a:b])]


def locate(text: str, hit: Hit) -> Hit:
    """The hit with its offsets filled in (searching for `wrong`, case-insensitively), or unchanged when it cannot be found."""
    if hit.start >= 0 or not hit.wrong:
        return hit
    at = text.casefold().find(hit.wrong.casefold())
    if at < 0:
        return hit
    return Hit(hit.source, hit.rule, hit.wrong, hit.fix, hit.kind, at, at + len(hit.wrong), hit.certain, hit.note)


def affected_sentences(text: str, hits: Sequence[Hit]) -> tuple[int, float]:
    """(number of sentences, how many of them a mistake touches): a sentence counts once however many mistakes it holds, and
    mistakes that cost less than a full point (spelling) count part of one."""
    spans = sentence_spans(text) or [(0, len(text))]
    cost = [0.0] * len(spans)
    for hit in hits:
        hit = locate(text, hit)
        if hit.start < 0:
            continue
        for k, (a, b) in enumerate(spans):
            if a <= hit.start < b or (hit.start < a and hit.end > a):
                cost[k] += hit.weight
                break
    return len(spans), sum(min(1.0, c) for c in cost)


def merge(*groups: Sequence[Hit]) -> list[Hit]:
    """All hits, without the same words reported twice (two sources naming one mistake count once; the first source wins)."""
    out: list[Hit] = []
    for group in groups:
        for hit in group:
            if not any(_overlap(hit, seen) for seen in out):
                out.append(hit)
    return out


def _overlap(a: Hit, b: Hit) -> bool:
    if a.start >= 0 and b.start >= 0:
        return a.start < b.end and b.start < a.end
    return a.wrong.casefold() == b.wrong.casefold()


def apply_certain(text: str, hits: Sequence[Hit]) -> str:
    """The text with every certain fix applied (right to left, so offsets stay valid). Nothing else is touched."""
    fixed = text
    for hit in sorted((locate(text, h) for h in hits if h.certain and h.fix), key=lambda h: -h.start):
        if hit.start >= 0 and fixed[hit.start:hit.end] == text[hit.start:hit.end]:
            fixed = fixed[:hit.start] + hit.fix + fixed[hit.end:]
    return fixed
