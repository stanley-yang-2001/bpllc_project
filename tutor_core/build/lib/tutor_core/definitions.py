"""Short meanings for a learner's words, written by the model (the learner can always edit them).

The words come from the learner's own list, which already passed tutor_core.words (letters, apostrophes, hyphens and spaces only,
one line), so they cannot carry instructions into this prompt. What comes back is treated as untrusted too: only lines for the
words that were asked about are used, each cut to the meaning rules (one line, at most 120 characters, no control characters).
"""
from __future__ import annotations

import re

from .words import MAX_MEANING_CHARS, WordError, validate_meaning

MAX_BATCH = 25
_LINE = re.compile(r"^\s*(?:[-*\d.)\s]*)(.+?)\s*[|→]\s*(.+?)\s*$")
_FENCE = re.compile(r"^`{3}.*$", re.M)


MEANING_MODES = ("native", "study", "both")      # in the learner's own language, in the language being studied, or both


def meaning_languages(mode: str, native: str, study: str) -> list[str]:
    """The language codes a meaning is written in for a mode. Both collapses to one when the learner's own language IS the study
    language, so nobody gets "water / water"."""
    if mode == "study":
        return [study]
    if mode == "both" and native != study:
        return [native, study]
    return [native]


def build_prompt(words: list[str], language_name: str, meaning_language_name: "str | list[str]") -> str:
    """`meaning_language_name` is one language name, or two (the meaning is written in both, joined by " / ")."""
    names = [meaning_language_name] if isinstance(meaning_language_name, str) else list(meaning_language_name)
    listed = "\n".join(words)
    if len(names) == 2:
        how = (f"write a short, plain meaning in {names[0]}, then ` / `, then the same meaning in {names[1]}: at most "
               f"{MAX_MEANING_CHARS // 3} characters for each language, one line")
    else:
        how = f"write a short, plain meaning in {names[0]}: at most {MAX_MEANING_CHARS // 2} characters, one line"
        if names[0] == language_name:
            how += f", in simple everyday {language_name} words a learner knows, without using the word itself"
    return (
        f"You are helping someone learn {language_name}. For each {language_name} word or phrase below, {how}, no examples, "
        "no quotation marks, no explanation of grammar.\n"
        "Answer with exactly one line per entry, in the same order, in this form:\n"
        "word | meaning\n"
        "Copy each word exactly as given. Write nothing else: no heading, no numbering, no notes.\n\n"
        f"Entries:\n{listed}\n"
    )


def parse(raw: str, words: list[str]) -> dict[str, str]:
    """{word as given: meaning} for the words the model answered usefully. Anything else is dropped, never guessed."""
    asked = {w.casefold(): w for w in words}
    out: dict[str, str] = {}
    for line in _FENCE.sub("", raw or "").splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        word = asked.get(m.group(1).strip().strip("*`\"'").casefold())
        if word is None or word in out:
            continue
        try:
            meaning = validate_meaning(m.group(2).strip().strip("*`\""))
        except WordError:
            meaning = None
        if meaning and meaning.casefold() != word.casefold():
            out[word] = meaning
    return out
