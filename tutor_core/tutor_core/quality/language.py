"""Is the passage actually written in the requested language?"""
from __future__ import annotations

from .vocabulary import _TOKEN, _norm, GRAMMAR_WORDS, parse_vocabulary, word_forms
import re

# --- is the passage actually written in the requested language? --------------------------------
# Found in the first automated run: a "Spanish" story written in English, a "Japanese" story in
# English, French with English words left in. Checking structure alone passed all of them.

_SCRIPT_RANGES = {
    "kana": "\u3040-\u30ff", "cjk": "\u3400-\u4dbf\u4e00-\u9fff", "hangul": "\uac00-\ud7af\u1100-\u11ff",
    "cyrillic": "\u0400-\u04ff", "arabic": "\u0600-\u06ff", "devanagari": "\u0900-\u097f",
    "greek": "\u0370-\u03ff", "thai": "\u0e00-\u0e7f", "hebrew": "\u0590-\u05ff",
}
_LANGUAGE_SCRIPTS = {}
for _names, _scripts in (
    (("japanese", "nihongo", "\u65e5\u672c\u8a9e"), ("kana", "cjk")),
    (("chinese", "mandarin", "cantonese", "\u4e2d\u6587", "\u6c49\u8bed", "\u6f22\u8a9e", "\u666e\u901a\u8bdd"), ("cjk",)),
    (("korean", "\ud55c\uad6d\uc5b4"), ("hangul",)),
    (("russian", "ukrainian", "bulgarian", "\u0440\u0443\u0441\u0441\u043a\u0438\u0439"), ("cyrillic",)),
    (("arabic", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"), ("arabic",)),
    (("hindi", "\u0939\u093f\u0928\u094d\u0926\u0940"), ("devanagari",)),
    (("greek", "\u03b5\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac"), ("greek",)),
    (("thai", "\u0e44\u0e17\u0e22"), ("thai",)),
    (("hebrew", "\u05e2\u05d1\u05e8\u05d9\u05ea"), ("hebrew",)),
):
    for _n in _names:
        _LANGUAGE_SCRIPTS[_n] = _scripts

# Short English words that are also ordinary words in Spanish/French/Italian/Portuguese/German
# ("no", "a", "me", "on"...) must not make a Romance-language story look English.
_AMBIGUOUS_WITH_ENGLISH = {"a", "as", "me", "no", "on", "do", "in", "an", "he", "so", "all", "here",
                           "is", "be", "was", "had", "son", "des", "the", "per"}
_ENGLISH_MARKERS = GRAMMAR_WORDS - _AMBIGUOUS_WITH_ENGLISH

ENGLISH_VERDICT_RATIO = 0.5  # at least this share of English words: the story is in English
MIXED_VERDICT_RATIO = 0.2    # at least this share: English words left in a story in another language
SCRIPT_MIN_RATIO = 0.5       # at least this share of letters must be in the language's own script


SHORT_TEXT_TOKENS = 25


def _short_text_verdict(tokens, language_name):
    """A short text has too few English marker words to trip the ratio, so plain English could pass as Spanish (known gap, 25 Oct).
    With the everyday lists: count words that are everyday in English but not in the requested language, and the other way round.
    Returns "english" or "mixed", or None when the text looks like the requested language (or the lists cannot say)."""
    from .. import difficulty as _d
    from ..languages import LANGUAGES
    code = next((c for c, lang in LANGUAGES.items() if lang.name.lower() == language_name), None)
    if code is None or code == "en" or not _d.has_everyday_list(code) or not _d.has_everyday_list("en"):
        return None
    en, target = _d._everyday("en"), _d._everyday(code)
    english_only = sum(1 for t in tokens if t in en and t not in target)
    target_only = sum(1 for t in tokens if t in target and t not in en)
    if english_only <= target_only or english_only < 3:
        return None
    return "english" if target_only == 0 else "mixed"


def language_check(text, language, vocab=""):
    """Is `text` plausibly written in `language`? English is never checked here.

    Non-Latin languages (Japanese, Chinese, Korean, Russian, ...): most letters must be in the
    language's own script. Other languages: the share of English words (grammar words plus the
    learner's English vocabulary) must be low; a story in English, or with English words left in
    ("je veux water"), fails. A heuristic, not a language detector: ok/verdict only."""
    name = _norm(language).strip().lower()
    base = {"ok": True, "verdict": "not_checked", "english_ratio": None, "script_ratio": None}
    if not name or name in ("english", "en", "ingles", "inglés", "anglais", "englisch"):
        return base

    letters = [ch for ch in _norm(text) if ch.isalpha()]
    scripts = _LANGUAGE_SCRIPTS.get(name)
    if scripts:
        pattern = re.compile("[" + "".join(_SCRIPT_RANGES[sc] for sc in scripts) + "]")
        ratio = (sum(1 for ch in letters if pattern.match(ch)) / len(letters)) if letters else 0.0
        ok = ratio >= SCRIPT_MIN_RATIO
        return {"ok": ok, "verdict": "ok" if ok else "wrong_script", "english_ratio": None, "script_ratio": ratio}

    markers = _ENGLISH_MARKERS | (parse_vocabulary(vocab) - _AMBIGUOUS_WITH_ENGLISH)
    markers |= {f for w in parse_vocabulary(vocab) for f in word_forms(w)} - _AMBIGUOUS_WITH_ENGLISH
    tokens = [t.lower() for t in _TOKEN.findall(_norm(text))]
    if not tokens:
        return {"ok": False, "verdict": "no_text", "english_ratio": 0.0, "script_ratio": None}
    ratio = sum(1 for t in tokens if t in markers) / len(tokens)
    if len(tokens) < SHORT_TEXT_TOKENS:
        short = _short_text_verdict(tokens, name)
        if short:
            return {"ok": False, "verdict": short, "english_ratio": ratio, "script_ratio": None}
    if ratio >= ENGLISH_VERDICT_RATIO:
        verdict = "english"
    elif ratio >= MIXED_VERDICT_RATIO:
        verdict = "mixed"
    else:
        verdict = "ok"
    return {"ok": verdict == "ok", "verdict": verdict, "english_ratio": ratio, "script_ratio": None}


