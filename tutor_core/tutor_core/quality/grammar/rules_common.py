"""What every built-in rule works with: the tokens of a text, a way to build a hit, and the rules that hold in every language."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from .base import Hit, sentence_spans

TOKEN = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
UNSPACED = ("zh", "ja")
CASED = ("en", "es", "fr", "de", "it", "pt")


@dataclass(frozen=True)
class Tok:
    text: str
    low: str
    start: int
    end: int


@dataclass(frozen=True)
class Ctx:
    text: str
    language: str
    words: tuple
    tokens: tuple

    def adjacent(self, i: int) -> bool:
        """Tokens i and i+1 are neighbours on one line: only spaces between them (no comma, no line break)."""
        if i + 1 >= len(self.tokens):
            return False
        gap = self.text[self.tokens[i].end:self.tokens[i + 1].start]
        return bool(gap) and gap.strip(" \t ") == ""

    def prev(self, i: int):
        """The word before token i when it is its neighbour on the same line, else None (a comma or full stop in between counts)."""
        if i == 0:
            return None
        gap = self.text[self.tokens[i - 1].end:self.tokens[i].start]
        return self.tokens[i - 1].low if gap.strip(" \t ") == "" and gap else None


def make_ctx(text: str, language: str, words: Sequence[str] = ()) -> Ctx:
    toks = tuple(Tok(m.group(0), m.group(0).casefold().replace("’", "'"), m.start(), m.end()) for m in TOKEN.finditer(text))
    return Ctx(text, language, tuple(words), toks)


def hit(ctx: Ctx, rule: str, start: int, end: int, fix: str = "", certain: bool = False, note: str = "", kind: str = "grammar") -> Hit:
    return Hit("rules", f"{ctx.language}.{rule}", ctx.text[start:end], fix, kind, start, end, certain, note)


Rule = Callable[[Ctx], list]


# --- rules that hold in every language that puts spaces between words --------------------------------------------------------------

_ALLOWED_DOUBLE = frozenset({"bye", "no", "so", "very", "that", "had", "yes", "ja", "nein", "sehr", "muy", "muito", "très", "molto", "sí",
                             "sì", "sim", "oui", "non", "bene", "bien", "bem", "ha", "oh", "na", "tra", "bla", "pas", "si", "poco", "mucho"})


def doubled_word(ctx: Ctx) -> list:
    out = []
    for i in range(len(ctx.tokens) - 1):
        a, b = ctx.tokens[i], ctx.tokens[i + 1]
        if a.low == b.low and len(a.low) >= 2 and a.low not in _ALLOWED_DOUBLE and ctx.adjacent(i):
            out.append(hit(ctx, "doubled_word", a.start, b.end, a.text, True, "the same word twice in a row"))
    return out


_ABBREVIATIONS = frozenset({"sr", "sra", "srta", "dr", "dra", "etc", "ej", "vs", "st", "mr", "mrs", "ms", "núm", "pág", "av", "tel", "ud",
                            "uds", "min", "max", "approx", "fig", "cap", "art", "ca", "env", "cf", "mme", "mlle", "herr", "hr", "fr", "prof",
                            "dott", "sig", "sigg", "no", "ee", "uu", "jr", "sr", "inc", "ltd", "co", "p", "a", "m", "h"})
_LABEL_START = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*[:：]")


def sentence_capital(ctx: Ctx) -> list:
    """A sentence that begins with a small letter: the text's first, and any after a single full stop. A question or exclamation mark
    is not checked (French and Spanish dialogue tags follow it in small letters), nor is "..." or an abbreviation."""
    if ctx.language not in CASED:
        return []
    out, spans = [], sentence_spans(ctx.text)
    for k, (a, b) in enumerate(spans):
        seg = ctx.text[a:b]
        if _LABEL_START.match(seg):
            continue
        first = next((m for m in re.finditer(r"[^\W\d_]", seg)), None)
        if first is None or not first.group(0).islower():
            continue
        at = a + first.start()
        if k > 0:
            before = ctx.text[spans[k - 1][0]:spans[k - 1][1]].rstrip(" \"'”’»)]」』")
            if not before.endswith(".") or before.endswith("..") or before.endswith("…"):
                continue
            last = TOKEN.findall(before[:-1])
            if (last and last[-1].casefold() in _ABBREVIATIONS) or (before[:-1][-1:].isdigit()):
                continue
            if ctx.text[a:at].strip(" ¿¡«\"'“‘(—-–"):                    # something other than an opening mark came first
                continue
        word = TOKEN.match(ctx.text, at)
        if word is None:
            continue
        w = word.group(0)
        out.append(hit(ctx, "sentence_capital", at, at + len(w), w[0].upper() + w[1:], True, "a sentence starts with a capital letter"))
    return out


_LATIN_WORD = re.compile(r"(?<![A-Za-z])[a-z]{3,}(?![A-Za-z])")


def latin_in_cjk(ctx: Ctx) -> list:
    """A lower-case English (or other Latin-script) word inside Chinese, Japanese or Korean text: the model slipped out of the language."""
    if ctx.language not in ("zh", "ja", "ko"):
        return []
    out = []
    for line_start, line in _lines(ctx.text):
        label = re.match(r"^\s*[A-Za-z]+\s*[:：]", line)
        body_from = label.end() if label else 0
        for m in _LATIN_WORD.finditer(line, body_from):
            if m.group(0) in ("ok", "wifi", "app", "pdf"):
                continue
            out.append(hit(ctx, "latin_word", line_start + m.start(), line_start + m.end(), "", False, "a word from another language"))
    return out


def _lines(text: str):
    pos = 0
    for line in text.split("\n"):
        yield pos, line
        pos += len(line) + 1


COMMON: dict = {code: [doubled_word, sentence_capital] for code in CASED}
COMMON.update({"zh": [latin_in_cjk], "ja": [latin_in_cjk], "ko": [latin_in_cjk]})
