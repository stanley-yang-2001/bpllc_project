"""Variety: are the stories different from one another?"""
from __future__ import annotations

from .vocabulary import _TOKEN, _norm, CONTRACTIONS, GRAMMAR_WORDS, parse_vocabulary, word_forms
from collections import Counter
import itertools
import re

# --- variety: are the stories different from one another? ---------------------------------------
# Reading 48 generated stories showed 81% mentioned water and ~75% were somebody asking for or
# receiving something. A pass rate cannot see that, so variety gets its own numbers.

# Greetings and politeness words open nearly every beginner text; they are not "the repeated word".
SOCIAL_WORDS = {"hello", "hi", "goodbye", "bye", "please", "thank", "thanks", "you", "yes", "no",
                "sorry", "welcome"}
_OPENING_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*:\s+")


def _all_tokens(text):
    return {t.lower() for t in _TOKEN.findall(_norm(text))}


def _content_tokens(text):
    return {t for t in _all_tokens(text) if t not in GRAMMAR_WORDS and t not in CONTRACTIONS}


def variety_report(results, vocab="", english=True):
    """How different are these stories from each other? `results` are check_passage() results with
    a "text" (and optionally "story_type"), as saved by run_story_batch.py. Failed generations are
    left out. top_vocab_word needs the English vocabulary, so it is skipped when english=False."""
    kept = [r for r in results if r.get("text") and not r.get("failure")]
    n = len(kept)
    types = Counter(r["story_type"] for r in kept if r.get("story_type"))
    report = {"n": n, "types": dict(types), "distinct_types": len(types),
              "mean_overlap": None, "top_vocab_word": None, "top_opening": None}
    if n == 0:
        return report

    content = [_content_tokens(r["text"]) for r in kept]
    if n >= 2:
        overlaps = [len(a & b) / len(a | b) for a, b in itertools.combinations(content, 2) if a | b]
        report["mean_overlap"] = sum(overlaps) / len(overlaps) if overlaps else 0.0

    openings = Counter()
    for r in kept:
        first = next((ln for ln in r["text"].splitlines() if ln.strip()), "")
        words = _TOKEN.findall(_norm(_OPENING_LABEL.sub("", first)).lower())[:3]
        openings[" ".join(words)] += 1
    opening, count = openings.most_common(1)[0]
    report["top_opening"] = (opening, count / n)

    if english:
        everything = [_all_tokens(r["text"]) for r in kept]
        best = None
        for word in sorted(parse_vocabulary(vocab) - SOCIAL_WORDS):
            forms = word_forms(word)
            share = sum(1 for tokens in everything if forms & tokens) / n
            if best is None or share > best[1]:
                best = (word, share)
        report["top_vocab_word"] = best
    return report


def format_variety(report):
    if not report["n"]:
        return "Variety: no stories to compare."
    parts = [f"Variety over {report['n']} stories: {report['distinct_types']} distinct types {report['types']}"]
    if report["mean_overlap"] is not None:
        parts.append(f"mean overlap between stories {report['mean_overlap']:.2f}")
    if report["top_vocab_word"]:
        word, share = report["top_vocab_word"]
        parts.append(f"most repeated vocabulary word '{word}' in {share:.0%} of stories")
    if report["top_opening"]:
        opening, share = report["top_opening"]
        parts.append(f"most common opening '{opening}' in {share:.0%}")
    return "; ".join(parts)


def format_summary(s):
    lines = [
        f"Attempts: {s['total']}   Passed: {s['passes']} ({s['pass_rate']:.0%})   Failures (no story): {s['failures']}",
        f"Styles: {s['styles']}   Leaked plan: {s['leaks']}   Off-length: {s['length_off']}   Bad format: {s['format_bad']}",
    ]
    if s["mean_oov_per_passage"] is not None:
        lines.append(f"Mean out-of-vocabulary words per passage: {s['mean_oov_per_passage']:.2f}")
        lines.append(f"Most common out-of-vocabulary words: {s['top_oov']}")
    if s["language_checked"]:  # English passages are not language-checked, so they are not counted
        lines.append(f"Written in the requested language: {s['language_checked'] - s['language_bad']}/{s['language_checked']}"
                     f"   Language verdicts: { {k: v for k, v in s['language_verdicts'].items() if k != 'not_checked'} }")
    if s["mean_unit_words"] is not None:
        lines.append(f"Words per sentence/line: mean {s['mean_unit_words']:.1f}, longest {s['longest_unit_words']}")
    if s["latency_p50"] is not None:
        lines.append(f"Latency p50 / p90: {s['latency_p50']:.1f}s / {s['latency_p90']:.1f}s")
    return "\n".join(lines)


