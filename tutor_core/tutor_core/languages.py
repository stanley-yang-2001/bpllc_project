"""Supported languages. Stored and exchanged as ISO 639-1 codes, never as free text."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Language:
    code: str
    name: str            # English name
    native: str          # name in the language itself
    tier: int            # 1 = space-delimited (lemmas via simplemma); 2 = needs an optional tokenizer
    stories_enabled: bool  # on only after a measured batch reaches Step 10 criterion 5 (>= 90% in the requested language)


# Measured in Step 10 (docs/STEP-10-TEST-PLAN.md, tuning change #1): Spanish, French and Japanese were each
# 10/10 in the requested language (30/30 in all, structure 30/30), and 15/15 non-English turns through the Agent.
# German, Italian, Portuguese, Chinese and Korean have not been measured, so they stay off until a batch of their
# own reaches the bar. Change a flag only together with the measurement that justifies it.
_LANGS = [
    Language("en", "English", "English", 1, True),
    Language("es", "Spanish", "Español", 1, True),
    Language("fr", "French", "Français", 1, True),
    Language("de", "German", "Deutsch", 1, False),
    Language("it", "Italian", "Italiano", 1, False),
    Language("pt", "Portuguese", "Português", 1, False),
    Language("ja", "Japanese", "日本語", 2, True),
    Language("zh", "Chinese", "中文", 2, False),
    Language("ko", "Korean", "한국어", 2, False),
]
LANGUAGES: dict[str, Language] = {lang.code: lang for lang in _LANGS}

# Alternate spellings a learner or the Agent may use (casefolded). Mirrors story_tool._NATIVE_LANGUAGE_NAMES.
_ALIASES = {
    "にほんご": "ja", "nihongo": "ja",
    "汉语": "zh", "漢語": "zh", "普通话": "zh", "国语": "zh", "國語": "zh", "mandarin": "zh",
    "espanol": "es", "castellano": "es",
    "francais": "fr", "portugues": "pt",
    "ingles": "en", "inglés": "en", "anglais": "en", "englisch": "en", "英語": "en", "英语": "en",
}
_LOOKUP: dict[str, str] = {}
for _l in _LANGS:
    _LOOKUP[_l.code] = _l.code
    _LOOKUP[_l.name.casefold()] = _l.code
    _LOOKUP[_l.native.casefold()] = _l.code
_LOOKUP.update(_ALIASES)


def normalize_language(value: Optional[str]) -> Optional[str]:
    """'Spanish', ' español ', 'ES' -> 'es'. Unknown or empty -> None (never creates a new language)."""
    text = " ".join((value or "").split()).casefold()
    return _LOOKUP.get(text) if text else None


def get_language(code: str) -> Optional[Language]:
    return LANGUAGES.get(code)


def supported_names() -> str:
    return ", ".join(lang.name for lang in _LANGS)


def stories_enabled(code: str) -> bool:
    """Whether stories may be generated. STORY_ALLOW_UNMEASURED=1 bypasses the gate (measurement scripts)."""
    lang = LANGUAGES.get(code)
    if lang is None:
        return False
    return lang.stories_enabled or os.environ.get("STORY_ALLOW_UNMEASURED") == "1"
