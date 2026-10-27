"""The report Story Studio shows, and the batch scoring that uses the same rules."""
from __future__ import annotations

from .endings import has_dangling_sentence
from .language import language_check
from .passage import _is_label, check_passage
from .vocabulary import _TOKEN, _norm
from collections import Counter
import math

# --- the report Story Studio shows (M6, commit 2 of 2) -----------------------------------------------------

RULES_VERSION = 4            # bump when the pass rule changes, so a saved report stays interpretable
MAX_STRAYS_ENGLISH = 5       # tuning change #2: raised from 2
READ_WORDS_PER_SECOND = 2    # a slow beginner pace
_OUTSIDE_LIST_CAP = 30       # informational mode lists at most this many words


def _read_seconds(text, unspaced):
    body = " ".join(ln.partition(":")[2] if _is_label(ln) else ln for ln in text.splitlines())
    if unspaced:                                    # Japanese, Chinese, Korean: no spaces, so estimate from letters
        words = sum(1 for ch in body if ch.isalpha()) / 2
    else:
        words = len(_TOKEN.findall(body))
    return max(1, math.ceil(words / READ_WORDS_PER_SECOND))


def report(text, language, vocab_words, difficulty=None):
    """The quality report for one passage: a plain, JSON-ready dict (design section 8).

    `language` is an ISO code from tutor_core.languages; `vocab_words` is the learner's FULL list in that language (the
    prompt only sees a sample, but the learner knows all of it). Which checks run depends on the language, and the
    report says which: strict (English: at most MAX_STRAYS_ENGLISH words outside the list), informational (other
    space-delimited languages: listed, never scored, because no grammar-word list exists for them yet) or unavailable
    (Tier 2). Pass = language ok and structure ok and no leaked plan and, in strict mode only, few enough strays.

    The language check is run WITHOUT the learner's list: language_check treats that list as English marker words, which
    is right for an English vocabulary and wrong for a Spanish learner's Spanish words (design 17A item 6)."""
    from ..languages import LANGUAGES

    lang = LANGUAGES.get(language)
    if lang is None:
        raise ValueError(f"unknown language code: {language!r}")
    from .. import difficulty as _d
    mode = "strict" if language == "en" else ("informational" if lang.tier == 1 else "unavailable")
    if mode == "informational" and not difficulty and _d.has_everyday_list(language):
        mode = "scored"           # rules version 4: with the everyday list, words outside the learner's list can be counted fairly
    if difficulty and mode == "strict":
        # A tier asks for everyday words beyond the learner's list, so the strict stray-word count would fail every such story
        # (24 Oct: "friend", "work", "thanks" counted). The tier's own unusual-word share replaces it; strays are listed only.
        mode = "informational"
    text = _norm(text).strip()
    vocab = ", ".join(vocab_words or [])

    # check_passage's own `passed` is not used: the pass rule is applied below, per mode.
    # With a difficulty tier the length is the tier's business (reported below), so the sentence-count rule is not applied.
    everyday = (lambda w: _d.is_everyday(w, language)) if _d.has_everyday_list(language) and lang.tier == 1 else None
    scored = check_passage(text, vocab, check_vocab=(mode != "unavailable"), max_oov=10 ** 9, everyday=everyday,
                           **({"length_range": (1, 10 ** 6)} if difficulty else {}))
    failure = scored["failure"]
    scored["format_ok"] = scored["format_ok"] and not has_dangling_sentence(text, language)       # rules version 4
    structure_ok = (not failure) and (not scored["leaked_plan"]) and scored["length_ok"] and scored["format_ok"]

    if failure:
        lang_part = {"requested": language, "ok": None, "verdict": "not_checked"}
    else:
        verdict = language_check(text, lang.name, "")
        lang_part = {"requested": language, "ok": verdict["ok"], "verdict": verdict["verdict"]}

    outside = None
    count = 0
    if mode != "unavailable" and not failure:
        outside = scored["oov_words"] if mode in ("strict", "scored") else scored["oov_words"][:_OUTSIDE_LIST_CAP]
        count = scored["oov_count"]
    limit = None
    vocab_ok = None
    if mode == "strict":
        limit = MAX_STRAYS_ENGLISH
        vocab_ok = (not failure) and count <= limit
    elif mode == "scored":
        # about one unusual word in ten, never fewer than the English limit (English: 5 in a 50-word story)
        limit = None if failure else max(MAX_STRAYS_ENGLISH, -(-scored["word_count"] // 10))
        vocab_ok = (not failure) and count <= limit

    section = None
    if difficulty and not failure:
        from .. import difficulty as _difficulty
        section = _difficulty.section(difficulty, text, language, vocab_words)
    # A tier is a promise: a story that misses its length, own-word count or unusual-word share needs a look (rules version 3).
    tier_ok = section is None or all(v is not False for v in section["met"].values())
    passed = (structure_ok and lang_part["ok"] is not False and (mode not in ("strict", "scored") or vocab_ok is True) and tier_ok)
    out = {
        "rules_version": RULES_VERSION,
        "status": "pass" if passed else "fail",
        "language": lang_part,
        "structure": {"ok": structure_ok, "style": scored["style"], "units": scored["units"],
                      "length_ok": scored["length_ok"], "format_ok": scored["format_ok"],
                      "leaked_plan": scored["leaked_plan"]},
        "vocabulary": {"mode": mode, "ok": vocab_ok, "outside": outside, "outside_count": count,
                       "limit": limit},
        "read_seconds": _read_seconds(text, unspaced=(lang.tier == 2)) if text else 1,
    }
    if section is not None:
        out["difficulty"] = section
    return out


def rescore_results(data, max_oov=0, strict_verbs=False, max_unit_words=None):
    """Re-score a saved batch (the JSON written by run_story_batch.py) under different rules,
    without generating anything new. Returns {language: [result, ...]}."""
    rescored = {}
    for language, items in data["results"].items():
        # Newer files keep one list per language, written in that language; older files had one English list for all.
        per_language = (data.get("vocabularies") or {}).get(language)
        vocab = per_language if per_language is not None else data.get("vocabulary", "")
        in_target = per_language is not None and language.strip().lower() != "english"
        rescored[language] = []
        for item in items:
            r = check_passage(
                item.get("text", ""), vocab, check_vocab=(language.strip().lower() == "english"),
                max_oov=max_oov, strict_verbs=strict_verbs, max_unit_words=max_unit_words,
                language=language, vocab_in_target=in_target,
            )
            r.update(language=language, latency=item.get("latency"),
                     style_requested=item.get("style_requested"), text=item.get("text"),
                     story_type=item.get("story_type"), topic=item.get("topic"))
            rescored[language].append(r)
    return rescored


def summarize(results):
    """Aggregate a list of check_passage() results (optionally with a 'latency' key)."""
    total = len(results)
    failures = sum(1 for r in results if r["failure"])
    scored = [r for r in results if not r["failure"]]
    passes = sum(1 for r in results if r["passed"])
    vocab_scored = [r for r in scored if r["oov_words"] is not None]
    latencies = sorted(r["latency"] for r in results if r.get("latency") is not None)

    def percentile(p):
        if not latencies:
            return None
        return latencies[min(len(latencies) - 1, math.ceil(p * len(latencies)) - 1)]

    return {
        "total": total,
        "failures": failures,
        "passes": passes,
        "pass_rate": passes / total if total else 0.0,
        "mean_oov_per_passage": (sum(r["oov_count"] for r in vocab_scored) / len(vocab_scored)) if vocab_scored else None,
        "top_oov": Counter(w for r in vocab_scored for w in r["oov_words"]).most_common(10),
        "styles": dict(Counter(r["style"] for r in scored)),
        "leaks": sum(1 for r in scored if r["leaked_plan"]),
        "length_off": sum(1 for r in scored if not r["length_ok"]),
        "format_bad": sum(1 for r in scored if not r["format_ok"]),
        "latency_p50": percentile(0.5),
        "latency_p90": percentile(0.9),
        "language_bad": sum(1 for r in scored if r.get("language_check") and not r["language_check"]["ok"]),
        "language_verdicts": dict(Counter(r["language_check"]["verdict"] for r in scored if r.get("language_check"))),
        "language_checked": sum(1 for r in scored if r.get("language_check") and r["language_check"]["verdict"] != "not_checked"),
        "mean_unit_words": (sum(r["mean_unit_words"] for r in scored) / len(scored)) if scored else None,
        "longest_unit_words": max((r["longest_unit_words"] for r in scored), default=None),
    }


