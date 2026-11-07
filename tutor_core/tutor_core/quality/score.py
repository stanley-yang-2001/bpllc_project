"""A 0 to 100 score for how well one story follows the requirements it was written under (6 Nov 2026, example bank).

Six requirements, each scored 0 to 100 and weighted the same, so the story score is their mean:

    1 length            within 10% of the target = 100, 50% off or more = 0, a straight line between
    2 your words        how many of the learner's words appear, against the target count (capped at 100)
    3 uncommon words    the share of unusual words: at or below the target = 100, 20 points above it = 0
    4 sentence length   the mean sentence is 6 to 12 words (8 to 24 characters in Chinese and Japanese); 15 points off per word outside,
                        and 15 more if any sentence is over 20 words (40 characters)
    5 grammar, fluency  100 minus 34 for each problem the code can see (list-like text, a repeated sentence, same openings)
    6 language, format  25 each: in the requested language; ends on a finished sentence; no leaked plan; format fits the kind

A story that is empty, a failure message, in the wrong language or that leaks the plan gets 0 whatever else it does (the gate): such a
story must never be kept as an example. A requirement that cannot be measured (no everyday-word list for the language) is left out and
the rest share the weight; the result says `partial`.

Grammar is only as good as the code can see: a wrong verb ending is invisible here. The optional model rating of grammar is not part
of this module.
"""
from __future__ import annotations

import re

from .endings import ends_complete, has_dangling_sentence
from .fluency import fluency_problems
from .language import language_check
from .passage import FAILURE_MARKERS, LEAK_PATTERN, _is_label, _read_shape
from .vocabulary import _TOKEN, _norm

SCORE_VERSION = 1
NAMES = ("length", "own_words", "uncommon", "sentence_length", "grammar", "language_format")
DEFAULT_LENGTH = {"dialogue": 50, "narration": 50}      # words, when no tier or length was asked; the other kinds: 80
DEFAULT_OWN, DEFAULT_UNCOMMON = 3, 10
LENGTH_FULL, LENGTH_ZERO = 0.10, 0.50
UNCOMMON_ZERO_POINTS = 20
SENTENCE_MEAN = {False: (6, 12), True: (8, 24)}           # per unit: words, or characters for Chinese and Japanese
SENTENCE_LONGEST = {False: 20, True: 40}
PER_WORD_OFF, LONGEST_PENALTY, PER_PROBLEM = 15, 15, 34


def _line(value, full, zero):
    """100 at `full`, 0 at `zero`, straight between (either direction); clamped."""
    if full == zero:
        return 100.0
    t = (value - full) / (zero - full)
    return max(0.0, min(100.0, 100.0 * (1 - t)))


def _gate(text, language):
    low = text.casefold()
    if not text.strip():
        return "empty"
    if any(m in low for m in FAILURE_MARKERS):
        return "failure_message"
    if LEAK_PATTERN.search(text):
        return "leaked_plan"
    if language != "en":
        from ..languages import LANGUAGES
        verdict = language_check(text, LANGUAGES[language].name, "")
        if verdict["ok"] is False:
            return "wrong_language"
    return None


def _target_length(language, difficulty, kind):
    from .. import difficulty as _d
    words = int(difficulty["length"]) if difficulty and difficulty.get("length") else DEFAULT_LENGTH.get(kind, 80)
    return round(words * _d.CHARS_PER_WORD) if language in _d.UNSPACED else words


def _unit_sizes(shape, unspaced):
    if unspaced:
        return [sum(1 for ch in u if ch.isalpha()) for u in shape.unit_texts if u.strip()]
    return [len(_TOKEN.findall(u)) for u in shape.unit_texts if u.strip()]


def _format_ok(shape, kind):
    labelled = [_is_label(ln) for ln in shape.lines]
    if shape.style == "dialogue":
        return all(labelled) and kind != "narration"
    heading = len(labelled) > 1 and labelled[0] and not any(labelled[1:])
    return (not any(labelled) or heading) and kind != "dialogue"


def score_story(text: str, language: str, words, difficulty=None, kind=None) -> dict:
    """{"score": 0 to 100, "parts": {name: 0 to 100 or None}, "gated": reason or None, "partial": bool, "targets": {...}, "measured": {...}}"""
    from .. import difficulty as _d
    text = _norm(text or "").strip()
    gated = _gate(text, language)
    if gated:
        return {"score": 0.0, "parts": {n: None for n in NAMES}, "gated": gated, "partial": False, "targets": {}, "measured": {},
                "version": SCORE_VERSION}
    unspaced = _d.is_unspaced(language)
    m = _d.measure(text, language, words)
    t_len = _target_length(language, difficulty, kind)
    t_own = min(int(difficulty["own_words"]) if difficulty and difficulty.get("own_words") else DEFAULT_OWN, max(1, len(list(words))))
    t_unc = float(difficulty["uncommon_pct"]) if difficulty and difficulty.get("uncommon_pct") is not None else float(DEFAULT_UNCOMMON)
    shape = _read_shape(text)
    parts = {}
    parts["length"] = _line(abs(m["length"] - t_len) / t_len, LENGTH_FULL, LENGTH_ZERO)
    parts["own_words"] = min(100.0, 100.0 * m["own_words"] / t_own)
    parts["uncommon"] = None if m["uncommon_pct"] is None else _line(m["uncommon_pct"], t_unc, t_unc + UNCOMMON_ZERO_POINTS)

    sizes = _unit_sizes(shape, unspaced) or [0]
    mean = sum(sizes) / len(sizes)
    low, high = SENTENCE_MEAN[unspaced]
    off = max(0.0, low - mean, mean - high)
    sentence = 100.0 - (PER_WORD_OFF / (2 if unspaced else 1)) * off - (LONGEST_PENALTY if max(sizes) > SENTENCE_LONGEST[unspaced] else 0)
    parts["sentence_length"] = max(0.0, sentence)
    problems = fluency_problems(text, unspaced)
    parts["grammar"] = max(0.0, 100.0 - PER_PROBLEM * len(problems))
    checks = [True, ends_complete(text) and not has_dangling_sentence(text, language), True, _format_ok(shape, kind)]
    parts["language_format"] = 25.0 * sum(checks)
    scored = {n: v for n, v in parts.items() if v is not None}
    return {"score": round(sum(scored.values()) / len(scored), 1), "parts": {n: (None if v is None else round(v, 1)) for n, v in parts.items()},
            "gated": None, "partial": len(scored) < len(NAMES), "problems": problems, "version": SCORE_VERSION,
            "targets": {"length": t_len, "own_words": t_own, "uncommon_pct": t_unc},
            "measured": {"length": m["length"], "own_words": m["own_words"], "uncommon_pct": m["uncommon_pct"], "mean_sentence": round(mean, 1)}}
