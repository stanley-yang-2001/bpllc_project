"""Cheap pass or fail checks that run before any model is asked to judge or repair a story (8 Nov 2026, the cascade plan).

A story that fails a gate is not graded by a model: it is dropped when another candidate passes, and a repair is told exactly which gate it
failed. Every check here is free (no model, no network). The gates:

    gated            empty, a failure message, a leaked plan or the wrong language (the score's own gate)
    length           more than 40% away from the target length
    too_few_words    fewer of the learner's words than the target asks for
    stuffed          more of the learner's words than the target + 3 or twice the target, whichever is more
    tacked_on_words  three or more sentences end on one of the learner's words stuck on after a comma ("Market is busy, thank you.")
    telegraphic      more than 30% of the sentences are three words or fewer (not for dialogues, and not for Chinese and Japanese)
    structural       a blank like [Your name], a repeated sentence, one word said over and over, list-like text
    too_many_errors  more than a quarter of the sentences hold a mistake the grammar rules (or the review hits passed in) found

If the score carries its own verdict (`passed`), a False there fails the story too ("score_rules").
"""
from __future__ import annotations

import re
from typing import Optional

from . import difficulty as _d
from .quality import score_story
from .quality.grammar import sentence_spans

LENGTH_SLACK = 0.40
TAIL_MIN = 3
FRAGMENT_SHARE, FRAGMENT_WORDS = 0.30, 3
ERROR_SHARE = 0.25
_TAIL = re.compile(r"[,;]\s*([^\W\d_]+(?:[ '’\-][^\W\d_]+)?)\s*(?=[.!?…](?:\s|$)|$)", re.M)
_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")


def own_limits(target: int) -> tuple[int, int]:
    """(the fewest, the most) of the learner's words a story should use."""
    return target, max(target + 3, 2 * target)


def tacked_on(text: str, words) -> int:
    listed = {w.casefold() for w in words if w and w.strip()}
    return sum(1 for m in _TAIL.finditer(text) if m.group(1).casefold() in listed)


def fragment_share(text: str) -> float:
    sizes = [len(_WORD.findall(text[a:b])) for a, b in sentence_spans(text)]
    sizes = [n for n in sizes if n]
    return sum(1 for n in sizes if n <= FRAGMENT_WORDS) / len(sizes) if sizes else 0.0


def check(text: str, language: str, words, difficulty: Optional[dict], kind: Optional[str], score: Optional[dict] = None) -> dict:
    """{"passed": bool, "failed": [names], "limits": {"own_min", "own_max", "length"}}. `score` is the result of score_story for this text,
    when the caller already has it."""
    words = list(words)
    result = score or score_story(text, language, words, difficulty, kind)
    if result.get("gated"):
        return {"passed": False, "failed": ["gated"], "limits": {}}
    t, m = result["targets"], result["measured"]
    low, high = own_limits(t["own_words"])
    failed = []
    if t["length"] and abs(m["length"] - t["length"]) / t["length"] > LENGTH_SLACK:
        failed.append("length")
    if m["own_words"] < min(low, len(words)):
        failed.append("too_few_words")
    if m["own_words"] > high:
        failed.append("stuffed")
    if tacked_on(text, words) >= TAIL_MIN:
        failed.append("tacked_on_words")
    if not _d.is_unspaced(language) and kind != "dialogue" and fragment_share(text) > FRAGMENT_SHARE:
        failed.append("telegraphic")
    if result.get("problems"):
        failed.append("structural")
    if m.get("sentences") and m.get("sentences_with_mistakes", 0) / m["sentences"] > ERROR_SHARE:
        failed.append("too_many_errors")
    for reason in ("unnatural", "markdown"):
        if reason in (result.get("failed") or []):
            failed.append(reason)
    if result.get("passed") is False:
        failed.append("score_rules")
    return {"passed": not failed, "failed": failed, "limits": {"own_min": low, "own_max": high, "length": t["length"]}}


def requirements(verdict: dict, language: str) -> list[str]:
    """Plain sentences a repair is given for the gates a story failed."""
    unit = "characters" if _d.is_unspaced(language) else "words"
    lim = verdict.get("limits") or {}
    text = {
        "length": f"Make the text about {lim.get('length')} {unit} long.",
        "too_few_words": f"Use at least {lim.get('own_min')} different words from the learner's list, each in a natural sentence.",
        "stuffed": f"Use at most {lim.get('own_max')} of the learner's words; the rest of the text should be ordinary everyday words.",
        "tacked_on_words": "Do not stick a word on after a comma at the end of a sentence (like \"The market is busy, thank you.\"): use each word inside "
                           "a sentence that makes sense.",
        "telegraphic": "Write full sentences with a subject and a verb, at least four words each, not short fragments.",
        "unnatural": "Rewrite it so it reads naturally, as a good writer would: events that follow one another, no filler words added to every line, no word stuck "
                     "on after a comma.",
        "markdown": "Write plain text only: no asterisks, no bold, no headings or other formatting marks.",
        "too_many_errors": "Correct the grammar of every sentence: articles, verb forms, agreement and prepositions.",
    }
    return [text[f] for f in verdict.get("failed", []) if f in text]
