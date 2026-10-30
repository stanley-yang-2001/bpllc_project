"""Parts of speech for a learner's words: each language has its own list of categories, because the languages do not divide words
the same way (Japanese has two kinds of adjective, Chinese has measure words, the Romance languages and German have articles and
English has determiners, Korean adjectives are descriptive verbs). A word is stored with one code from its language's list, or none.

The model is asked to label words from the learner's own list; what comes back is untrusted, so only a code from the language's own
list, for a word that was asked about, is used. A phrase of several words is labelled "phrase"."""
from __future__ import annotations

import re

from .definitions import MAX_BATCH  # a batch of labels is the same size as a batch of meanings

_ROMANCE_DE = ("noun", "verb", "adjective", "adverb", "pronoun", "article", "preposition", "conjunction", "interjection", "phrase")
CATEGORIES: dict[str, tuple[str, ...]] = {
    "en": ("noun", "verb", "adjective", "adverb", "pronoun", "determiner", "preposition", "conjunction", "interjection", "phrase"),
    "es": _ROMANCE_DE, "fr": _ROMANCE_DE, "it": _ROMANCE_DE, "pt": _ROMANCE_DE, "de": _ROMANCE_DE,
    "ja": ("noun", "verb", "adjective_i", "adjective_na", "adverb", "pronoun", "particle", "measure_word", "conjunction", "interjection", "phrase"),
    "zh": ("noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction", "particle", "measure_word", "interjection", "phrase"),
    "ko": ("noun", "verb", "adjective", "adverb", "pronoun", "particle", "measure_word", "conjunction", "interjection", "phrase"),
}
ALL_CODES = tuple(sorted({c for cats in CATEGORIES.values() for c in cats}))

# What the model is told each code means, in English, with the language's own wrinkle where there is one.
_MEANING = {
    "noun": "noun (a person, place, thing or idea)", "verb": "verb (an action or state)", "adjective": "adjective (describes a noun)",
    "adverb": "adverb", "pronoun": "pronoun", "determiner": "determiner (the, a, this, my, some ...)", "article": "article",
    "preposition": "preposition", "conjunction": "conjunction", "interjection": "interjection (hello, wow ...)",
    "phrase": "phrase (an entry of more than one word)", "particle": "particle", "measure_word": "measure word / counter",
    "adjective_i": "i-adjective (ends in い, conjugates like 高い)", "adjective_na": "na-adjective (takes な, like 静か)",
}
_NOTE = {
    "ko": "Korean describing words (예쁘다, 크다) are 'adjective'.",
    "zh": "Chinese adjectives (好, 大) are 'adjective'; a counter such as 个 or 本 is 'measure_word'.",
    "ja": "Japanese has two kinds of adjective: 'adjective_i' and 'adjective_na'. Counters such as 個 or 本 are 'measure_word'.",
}
_LINE = re.compile(r"^\s*(?:[-*\d.)\s]*)(.+?)\s*[|→]\s*([A-Za-z_ -]+?)\s*$")
_FENCE = re.compile(r"^`{3}.*$", re.M)


def categories(language: str) -> tuple[str, ...]:
    return CATEGORIES.get(language, ())


def valid(language: str, code) -> bool:
    return code in CATEGORIES.get(language, ())


def build_prompt(words: list[str], language: str, language_name: str) -> str:
    cats = CATEGORIES[language]
    listed = "\n".join(f"{c}: {_MEANING[c]}" for c in cats)
    note = (_NOTE.get(language, "") + " ").lstrip()
    return (
        f"You are helping someone learn {language_name}. For each {language_name} word or phrase below, give its part of speech "
        f"as it is used most commonly, choosing exactly one code from this list:\n{listed}\n{note}"
        "Answer with exactly one line per entry, in the same order, in this form:\n"
        "word | code\n"
        "Copy each word exactly as given and use the code exactly as written. Write nothing else: no heading, no numbering, no notes.\n\n"
        "Entries:\n" + "\n".join(words) + "\n"
    )


def parse(raw: str, words: list[str], language: str) -> dict[str, str]:
    """{word as given: code} for the words the model answered with a code from this language's list. Anything else is dropped."""
    asked = {w.casefold(): w for w in words}
    out: dict[str, str] = {}
    for line in _FENCE.sub("", raw or "").splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        word = asked.get(m.group(1).strip().strip("*`\"'").casefold())
        code = m.group(2).strip().casefold().replace(" ", "_").replace("-", "_")
        if word is not None and word not in out and valid(language, code):
            out[word] = code
    return out
