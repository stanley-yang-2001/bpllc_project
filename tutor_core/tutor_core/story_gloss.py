"""Where the learner's own words stand in a text (21 Nov 2026). No model call.

The reader underlines the learner's words in a story and shows the meaning on a tap. What is underlined must be what the story report counts as used,
so the rules are the ones of `difficulty.measuring._own_found` (a test compares the two on the same texts):

    English          a word and its regular forms (walk: walked, walking) and the score's seven irregular verbs (go, see, say, give, get, take, come);
                     "to eat" is the verb eat; a phrase is its words side by side. Other irregular forms (ate) are not counted by the score, nor underlined
    other spaced     the word as written (a form the score does not count is not underlined either)
    zh, ja, ko       the splitter's words (the written form or its dictionary form), a word the splitter cut in pieces by joining 2 to 4 neighbours;
                     with no splitter installed, the word anywhere in the text

What the score does not need and the reader does: the place of each word. Positions are into the text exactly as given (a lowercase copy can be
longer than the original, "ß" becomes "ss", so the text is never lowercased as a whole), each span is one word or one phrase, and two spans never
overlap: where "good" and "good morning" both fit, the longer one wins."""
from __future__ import annotations

import re
from typing import Iterable, NamedTuple

from . import splitter

_TOKEN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")                                                     # same as difficulty.measuring
_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*[:：]\s*", re.M)              # "Ana:" at the start of a line
_BREAK = re.compile(r"[.!?…\n]")             # a phrase does not run across the end of a sentence or a line
MAX_JOIN = 4


class Span(NamedTuple):
    start: int          # index of the first character
    end: int            # index after the last character
    word_id: int


def find(text: str, language: str, words: Iterable[tuple[int, str]]) -> list[Span]:
    """Every place a word of the learner's stands in `text`, in reading order, none overlapping. `words` are (id, word) pairs."""
    pairs = [(i, w.strip()) for i, w in words if w and w.strip()]
    if not text or not pairs:
        return []
    spans = _unspaced(text, language, pairs) if language in splitter.SPLIT_LANGUAGES else _spaced(text, language, pairs)
    return _without_overlap(spans)


def _without_overlap(spans: list[Span]) -> list[Span]:
    """Reading order; of two spans that share a character the one that starts first stays, and at the same start the longer one (then the lower id)."""
    out: list[Span] = []
    for s in sorted(spans, key=lambda s: (s.start, -(s.end - s.start), s.word_id)):
        if not out or s.start >= out[-1].end:
            out.append(s)
    return out


def _forms(code: str, part: str) -> set[str]:
    if code == "en":
        from .quality import word_forms
        return set(word_forms(part)) | {part}
    return {part}


def _spaced(text: str, code: str, pairs: list[tuple[int, str]]) -> list[Span]:
    single: dict[str, int] = {}
    phrases: list[tuple[int, list[set[str]]]] = []
    for wid, word in pairs:
        parts = word.casefold().split()
        if code == "en" and len(parts) == 2 and parts[0] == "to":       # "to eat" is the verb: eats, ate and eating count
            parts = parts[1:]
        if len(parts) == 1:
            for f in _forms(code, parts[0]):
                single.setdefault(f, wid)
        elif parts:
            phrases.append((wid, [_forms(code, p) for p in parts]))
    tokens = [(m.start(), m.end(), m.group(0).casefold()) for m in _TOKEN.finditer(text)]       # each token lowered alone: offsets stay true
    spans = [Span(s, e, single[t]) for s, e, t in tokens if t in single]
    for wid, options in phrases:
        n = len(options)
        for i in range(len(tokens) - n + 1):
            if all(tokens[i + j][2] in options[j] for j in range(n)) and not any(
                    _BREAK.search(text, tokens[i + j][1], tokens[i + j + 1][0]) for j in range(n - 1)):
                spans.append(Span(tokens[i][0], tokens[i + n - 1][1], wid))
    return spans


def _unspaced(text: str, code: str, pairs: list[tuple[int, str]]) -> list[Span]:
    wanted: dict[str, int] = {}
    for wid, word in pairs:
        wanted.setdefault(word.casefold(), wid)
    masked = _LABEL.sub(lambda m: " " * len(m.group(0)), text)           # a speaker label is not story text; same length, so offsets hold
    pieces = splitter.split(masked, code)
    if pieces is None:                                                  # no splitter installed: the word anywhere in the text
        return [Span(m.start(), m.end(), wid) for w, wid in wanted.items() for m in re.finditer(re.escape(w), masked, re.I)]
    where, pos = [], 0                                                  # the splitter returns words in order; find each one's place
    for p in pieces:
        i = masked.find(p.surface, pos)
        if i < 0:
            where.append(None)
            continue
        where.append((i, i + len(p.surface)))
        pos = i + len(p.surface)
    spans: list[Span] = []
    for k, p in enumerate(pieces):
        if where[k] is None:
            continue
        for form in {p.surface.casefold(), p.base.casefold()}:
            if form in wanted:
                spans.append(Span(where[k][0], where[k][1], wanted[form]))
        for n in range(2, MAX_JOIN + 1):                                # a word the splitter cut in pieces
            if k + n > len(pieces) or any(where[k + j] is None for j in range(n)):
                continue
            joined = "".join(q.surface for q in pieces[k:k + n]).casefold()
            if joined in wanted:
                spans.append(Span(where[k][0], where[k + n - 1][1], wanted[joined]))
    return spans
