"""Use cases for readings (how a text is pronounced) and translations of a learner's own words or story lines. Both are shown to the
learner and never stored. Chinese, Japanese and Korean readings come from libraries (no model call); everything else is one model call."""
from __future__ import annotations

from tutor_core import pronunciation, translation
from tutor_core.languages import LANGUAGES

from ..errors import validation_error
from .ai_runner import AiRunner

PRONOUNCE_TOKENS = 2000
TRANSLATE_TOKENS = 2500


def _lines_of(prompt: str) -> list[tuple[str, str]]:
    body = prompt.split("Lines:\n", 1)[1].strip().splitlines()
    return [tuple(line.split(". ", 1)) for line in body]


def _stub_reading(prompt: str) -> str:
    return "\n".join(f"{n} | /stub reading/" for n, _ in _lines_of(prompt))


def _stub_translation(prompt: str) -> str:
    return "\n".join(f"{n} | (stub) {text}" for n, text in _lines_of(prompt))


def checked_lines(texts: list[str], clean, limit: int) -> list[str]:
    lines = clean(texts)
    if any(not x for x in lines):
        raise validation_error("Every line needs some text.")
    if any(len(x) > limit for x in lines):
        raise validation_error(f"A line can be at most {limit} characters.")
    return lines


def pronounce(runner: AiRunner, user_id: int, language: str, texts: list[str]) -> dict:
    kind = pronunciation.kind_for(language)
    lines = checked_lines(texts, pronunciation.clean_texts, pronunciation.MAX_LINE_CHARS)
    readings: dict[int, str] = {}
    if kind != "ipa":                                   # the libraries first: free, and the same every time
        for i, line in enumerate(lines):
            reading = pronunciation.romanize(line, language)
            if reading:
                readings[i] = reading
    missing = [i for i in range(len(lines)) if i not in readings]
    if missing:                                         # IPA, or a library that isn't installed: ask the model
        asked = [lines[i] for i in missing]
        prompt = pronunciation.build_prompt(asked, LANGUAGES[language].name, kind)
        raw = runner.run(user_id, prompt, tokens=PRONOUNCE_TOKENS, stub=_stub_reading,
                         failed_message="The tutor couldn't write the pronunciation. Please try again in a moment.")
        for n, text in pronunciation.parse(raw, len(asked)).items():
            readings[missing[n]] = text
    return {"kind": kind, "approximate": bool(missing), "items": [{"text": t, "reading": readings.get(i)} for i, t in enumerate(lines)]}


def translate(runner: AiRunner, user_id: int, language: str, target_language: str, texts: list[str], words: bool) -> dict:
    if target_language not in LANGUAGES:
        raise validation_error("Choose one of the site languages to translate into.")
    if target_language == language:
        raise validation_error("Choose a different language to translate into.")
    lines = checked_lines(texts, translation.clean_texts, translation.MAX_LINE_CHARS)
    prompt = translation.build_prompt(lines, LANGUAGES[language].name, LANGUAGES[target_language].name, words)
    raw = runner.run(user_id, prompt, tokens=TRANSLATE_TOKENS, stub=_stub_translation,
                     failed_message="The tutor couldn't translate this. Please try again in a moment.")
    done = translation.parse(raw, len(lines))
    return {"target_language": target_language, "items": [{"text": t, "translation": done.get(i)} for i, t in enumerate(lines)]}
