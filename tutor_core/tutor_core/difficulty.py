"""Story difficulty (24 Oct 2026, docs/DIFFICULTY-TIERS-DESIGN.md): three measures, three presets, and the learner's own settings.

  1. LENGTH         the story's length in words (characters for Chinese and Japanese, which have no spaces)
  2. OWN WORDS      how many DIFFERENT words from the learner's list the story uses
  3. UNCOMMON SHARE the share of words that are neither in the language's everyday list nor the learner's own words
                    (all nine languages; Chinese, Japanese and Korean need the splitter, see splitter.py, else None)

A tier is a set of targets for the three. They go into the story prompt as a note at the top, and the finished story is measured
against them. The model follows them loosely (own-word counts and the uncommon share especially), so the report shows what was
measured next to what was asked for and a story that misses is shown as it is, never relabelled or silently regenerated."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import splitter
from .languages import LANGUAGES

TIERS = {
    "easy": {"length": 60, "own_words": 3, "uncommon_pct": 5},
    "medium": {"length": 110, "own_words": 5, "uncommon_pct": 10},
    "hard": {"length": 200, "own_words": 8, "uncommon_pct": 20},
}
TIER_NAMES = tuple(TIERS) + ("custom",)
LIMITS = {"length": (20, 400), "own_words": (1, 30), "uncommon_pct": (0, 50)}   # (min, max), inclusive
LENGTH_TOLERANCE = 0.35        # a story within 35% of the target length counts as meeting it
UNCOMMON_SLACK = 5             # and one with at most this many points more uncommon words than asked
CHARS_PER_WORD = 1.6           # Chinese and Japanese: a target of N words is about N * 1.6 characters
_UNSPACED = ("zh", "ja")
_DATA = Path(__file__).parent / "data"
_TOKEN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*[:：]\s*", re.M)    # "Ana:" or "アナ：" at the start of a line


def resolve(tier, length=None, own_words=None, uncommon_pct=None) -> Optional[dict]:
    """The targets for a request, as {"tier", "length", "own_words", "uncommon_pct"}, or None for "no difficulty asked".
    A preset takes no extra numbers. "custom" starts from the medium targets and takes the learner's own numbers.
    Raises ValueError (with a message fit to show) for anything else."""
    if tier is None or (isinstance(tier, str) and tier.strip().lower() in ("", "any")):
        if any(v is not None for v in (length, own_words, uncommon_pct)):
            raise ValueError("Choose Custom to set your own numbers.")
        return None
    name = tier.strip().lower() if isinstance(tier, str) else None
    if name not in TIER_NAMES:
        raise ValueError("Pick Easy, Medium, Hard or Custom.")
    given = {"length": length, "own_words": own_words, "uncommon_pct": uncommon_pct}
    if name != "custom":
        if any(v is not None for v in given.values()):
            raise ValueError("Choose Custom to set your own numbers.")
        return {"tier": name, **TIERS[name]}
    targets = dict(TIERS["medium"])
    for key, value in given.items():
        if value is None:
            continue
        lo, hi = LIMITS[key]
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise ValueError(f"{key.replace('_', ' ')} must be a whole number from {lo} to {hi}.")
        targets[key] = value
    return {"tier": "custom", **targets}


def _unit(language: str) -> str:
    return "characters" if language in _UNSPACED else "words"


def prompt_note(language_code: str, targets: dict) -> str:
    """The note placed at the top of the story prompt. It states numbers only; nothing the learner typed goes into it."""
    if language_code in _UNSPACED:
        size = f"about {round(targets['length'] * CHARS_PER_WORD)} characters"
    else:
        size = f"about {targets['length']} words"
    lines = [f"Difficulty (this overrides any length given below): write {size} in total, and do not stop early. A story that is much shorter than this is wrong.",
             f"Use at least {targets['own_words']} different words from the list (as many as the list allows).",
             "Every other word must be an everyday word that a beginner already knows."]
    if can_measure_uncommon(language_code):
        lines[-1] = (f"Every other word must be an everyday word that a beginner already knows; no more than about "
                     f"{targets['uncommon_pct']}% of all the words may be unusual ones.")
    return " ".join(lines)


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
        from .quality import word_forms
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
        from .quality import word_forms
        return sum(1 for w in words if tokens & set(word_forms(w)))
    return sum(1 for w in words if w in tokens)


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
        if t.surface not in everyday and t.base not in everyday:
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
    if language_code in _UNSPACED:
        length = sum(1 for ch in _LABEL.sub("", text) if ch.isalpha())
    else:
        length = len(_tokens(text))
    return {"length": length, "length_unit": _unit(language_code), "own_words": _own_found(text, language_code, vocab_words),
            "uncommon_pct": _uncommon_share(text, language_code, vocab_words)}


def evaluate(targets: dict, measured: dict, language_code: str, list_size: int) -> dict:
    """Did each measure meet its target? True / False, or None when the measure does not apply (no everyday list)."""
    want_len = targets["length"] * (CHARS_PER_WORD if language_code in _UNSPACED else 1)
    length_ok = abs(measured["length"] - want_len) <= LENGTH_TOLERANCE * want_len
    own_ok = measured["own_words"] >= min(targets["own_words"], max(list_size, 0))
    uncommon = measured["uncommon_pct"]
    uncommon_ok = None if uncommon is None else uncommon <= targets["uncommon_pct"] + UNCOMMON_SLACK
    return {"length": length_ok, "own_words": own_ok, "uncommon_pct": uncommon_ok}


def section(targets: dict, text: str, language_code: str, vocab_words) -> dict:
    """The report's difficulty section: what was asked for, what was measured, and whether each measure was met."""
    vocab_words = list(vocab_words or [])
    measured = measure(text, language_code, vocab_words)
    return {"requested": targets, "measured": measured, "met": evaluate(targets, measured, language_code, len(vocab_words)),
            "list_size": len(vocab_words)}
