"""Scoring one passage: structure, vocabulary, language and length against the rules the story prompt states."""
from __future__ import annotations

from .endings import ends_complete
from .language import language_check
from .vocabulary import _LABEL, _SENTENCE_SPLIT, _TOKEN, _allowed_words, _is_known, _norm, _vocab_forms, parse_vocabulary
from collections import Counter
from dataclasses import dataclass
import re

FAILURE_MARKERS = (
    "having trouble generating a story",
    "don't have any vocabulary yet",
)

LEAK_PATTERN = re.compile(r"===\s*story\s*===|^\s*(character|characters|want|event|resolution)\s*:", re.I | re.M)


def _is_label(line):
    """A speaker label: 'Name:' or 'Name :' with 1-2 words, none starting with a lower-case letter.
    ('Marc dit : ...' inside a narration is not a label; names in scripts without case still are.)"""
    match = _LABEL.match(line)
    return bool(match) and all(not word[0].islower() for word in match.group(1).split())


def _failure_result(reason):
    return {
        "failure": True, "failure_reason": reason, "passed": False, "style": None, "units": 0,
        "length_ok": False, "format_ok": False, "leaked_plan": False, "vocab_checked": False,
        "oov_words": None, "oov_count": 0, "word_count": 0, "oov_rate": 0.0, "names": [],
        "longest_unit_words": 0, "mean_unit_words": 0.0, "language_check": None,
    }



@dataclass(frozen=True)
class Shape:
    """What the passage looks like before any rule judges it: lines, speakers, sentences."""
    style: str                       # "dialogue" or "narration"
    lines: list
    body_segments: list              # the text with speaker labels removed
    label_names: set
    unit_texts: list                 # the lines of a dialogue, or the sentences of a narration
    leaked: bool
    format_ok: bool                  # every line has a speaker (dialogue) or none has (narration), and the last sentence is finished

    @property
    def units(self) -> int:
        return len(self.unit_texts) if self.style != "dialogue" else len(self.lines)


def _read_shape(text):
    leaked = bool(LEAK_PATTERN.search(text))
    lines = [ln for ln in text.splitlines() if ln.strip()]
    labelled = [_is_label(ln) for ln in lines]
    if labelled and labelled[0] and not any(labelled[1:]) and len(lines) > 1:
        labelled[0] = False       # one heading like "Montag Morgen:" above a narration is not a speaker (22 Oct, German diary)
    style = "dialogue" if sum(labelled) * 2 >= len(lines) and any(labelled) else "narration"
    format_ok = (all(labelled) if style == "dialogue" else not any(labelled)) and ends_complete(text)

    body_segments = []  # text with speaker labels removed
    label_names = set()
    for ln, is_label in zip(lines, labelled):
        if is_label:
            label, _, rest = ln.partition(":")
            label_names.update(t.lower() for t in _TOKEN.findall(label))
            body_segments.append(rest.strip())
        else:
            body_segments.append(ln.strip())
    if style == "dialogue":
        unit_texts = body_segments
    else:
        unit_texts = [s for s in _SENTENCE_SPLIT.split(text) if re.search(r"[^\W\d_]", s)]
    return Shape(style, lines, body_segments, label_names, unit_texts, leaked, format_ok)


# --- the rules: each takes what it needs and returns its part of the report ------------------------------------------------------

def _length_rule(shape, length_range):
    """units inside the range the prompt asks for, and how long the sentences or lines are."""
    unit_lengths = [len(_TOKEN.findall(u)) for u in shape.unit_texts] or [0]
    return {"units": shape.units, "length_ok": length_range[0] <= shape.units <= length_range[1],
            "longest_unit_words": max(unit_lengths), "mean_unit_words": sum(unit_lengths) / len(unit_lengths)}


def _find_names(shape, names, vocab_forms, allowed):
    """Character names: speaker labels, the names the caller gave, capitalised words in the middle of a sentence that are neither
    vocabulary nor grammar ("I am Sam"), and a capitalised word that appears at least twice, never in lower case ("Sam wakes up. Sam
    looks out."; sentence-initial "Soon," twice would also be taken for one: a rare, harmless under-count)."""
    known_names = set(shape.label_names) | {n.lower() for n in names}
    for segment in shape.body_segments:
        for sentence in _SENTENCE_SPLIT.split(segment):
            tokens = _TOKEN.findall(sentence)
            for token in tokens[1:]:
                low = token.lower()
                if token[0].isupper() and token != "I" and not _is_known(low, vocab_forms, allowed):
                    known_names.add(low)
    cap_counts, lower_seen = Counter(), set()
    for segment in shape.body_segments:
        for sentence in _SENTENCE_SPLIT.split(segment):
            for token in _TOKEN.findall(sentence):
                if token[0].isupper() and token != "I":
                    cap_counts[token.lower()] += 1
                else:
                    lower_seen.add(token.lower())
    for low, count in cap_counts.items():
        if count >= 2 and low not in lower_seen and not _is_known(low, vocab_forms, allowed):
            known_names.add(low)
    return known_names


def _vocabulary_rule(shape, vocab, strict_verbs, extra_allowed, names, everyday):
    """Words outside the learner's list (not names, grammar words, or everyday words of the language)."""
    allowed = _allowed_words(strict_verbs, extra_allowed)
    vocab_forms = _vocab_forms(parse_vocabulary(vocab))
    known_names = _find_names(shape, names, vocab_forms, allowed)
    word_count = 0
    oov_occurrences = []
    for segment in shape.body_segments:
        for token in _TOKEN.findall(segment):
            low = token.lower()
            if low in known_names:
                continue
            word_count += 1
            if not _is_known(low, vocab_forms, allowed) and not (everyday and everyday(low)):
                oov_occurrences.append(low)
    return {"oov_words": list(dict.fromkeys(oov_occurrences)), "oov_count": len(oov_occurrences), "word_count": word_count,
            "oov_rate": len(oov_occurrences) / word_count if word_count else 0.0, "names": sorted(known_names)}


def check_passage(text, vocab, check_vocab=True, max_oov=0, length_range=(4, 10),
                  strict_verbs=False, extra_allowed=(), names=(), max_unit_words=None, language=None,
                  vocab_in_target=False, everyday=None):
    """Score one passage. Returns a dict; `passed` is the overall verdict: no leaked plan, the right shape, length, vocabulary,
    sentence length and language. Each rule above makes its part of the report; this joins them.

    max_oov: words outside the vocabulary tolerated (0 = strict; the batch runner defaults to 2
    so ordinary everyday words such as "eat" or "drink" don't fail a story).
    max_unit_words: optional cap on the words in any one sentence/line (beginner readability);
    the longest and mean lengths are always reported either way.
    vocab_in_target: `vocab` is written in `language` (a learner's own per-language list). Its words must then NOT count as
    English markers in the language check: German "Haus, Brot, Freund" are not English. Without this, a correct German
    story was called "mixed" (22 Oct 2026 batch: 14 of 15).
    everyday: optional function word -> bool; an everyday word of the language outside the learner's list is not a stray
    (24 Oct 2026: the learner should not have to add "friend" or "work" to their vocabulary to keep a story from failing).
    language: the language the story was requested in. For anything other than English the
    passage must actually be written in it (see language_check); None skips that check."""
    text = _norm(text).strip()
    if not text:
        return _failure_result("empty")
    lowered = text.lower()
    for marker in FAILURE_MARKERS:
        if marker in lowered:
            return _failure_result("fallback or guard message")

    shape = _read_shape(text)
    length = _length_rule(shape, length_range)
    result = {
        "failure": False, "failure_reason": None, "style": shape.style, "units": length["units"],
        "length_ok": length["length_ok"], "format_ok": shape.format_ok, "leaked_plan": shape.leaked,
        "vocab_checked": bool(check_vocab), "oov_words": None, "oov_count": 0,
        "word_count": 0, "oov_rate": 0.0, "names": [],
        "longest_unit_words": length["longest_unit_words"], "mean_unit_words": length["mean_unit_words"],
    }
    if check_vocab:
        result.update(_vocabulary_rule(shape, vocab, strict_verbs, extra_allowed, names, everyday))

    vocab_ok = (not check_vocab) or result["oov_count"] <= max_oov
    unit_ok = max_unit_words is None or result["longest_unit_words"] <= max_unit_words
    language_ok = True
    if language:
        result["language_check"] = language_check(text, language, "" if vocab_in_target else vocab)
        language_ok = result["language_check"]["ok"]
    else:
        result["language_check"] = None
    result["passed"] = (not shape.leaked) and length["length_ok"] and shape.format_ok and vocab_ok and unit_ok and language_ok
    return result
