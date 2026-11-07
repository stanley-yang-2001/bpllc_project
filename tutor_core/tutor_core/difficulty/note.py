"""The note placed at the top of the story prompt."""
from __future__ import annotations

import os

from .measuring import can_measure_uncommon
from .presets import CHARS_PER_WORD, ask_size, is_unspaced


RANGE_SHARE = 0.15       # the range is the target plus or minus 15%
LEVELS = {              # 7 Nov: what the tier means in sentences, so "easy" is not left to the model to guess
    "easy": "Level A1 to A2: short, simple sentences of about 5 to 8 words, mostly the present tense, no idioms, one idea per sentence.",
    "medium": "Level A2 to B1: sentences of about 8 to 12 words, simple connectors (and, but, because, then), past and future allowed.",
    "hard": "Level B1 to B2: sentences of about 10 to 16 words, varied connectors, subordinate clauses allowed, a wider range of everyday words.",
}


SENTENCE_WORDS = {"easy": 6, "medium": 10, "hard": 13}       # the middle of each level's sentence length, used for the sentence count


def range_prompt_on() -> bool:
    """STORY_RANGE_PROMPT=1 (off by default): a word range instead of "about N", and the tier's level in words."""
    return os.environ.get("STORY_RANGE_PROMPT") == "1"


def size_range(asked: int):
    return max(1, round(asked * (1 - RANGE_SHARE))), round(asked * (1 + RANGE_SHARE))


def prompt_note(language_code: str, targets: dict) -> str:
    """The note placed at the top of the story prompt. It states numbers only; nothing the learner typed goes into it."""
    asked = ask_size(language_code, targets["length"])
    if is_unspaced(language_code):
        size = f"about {round(asked * CHARS_PER_WORD)} characters"
    else:
        size = f"about {asked} words"
    if range_prompt_on():
        lo, hi = size_range(asked)
        unit = "characters" if is_unspaced(language_code) else "words"
        if is_unspaced(language_code):
            lo, hi = round(lo * CHARS_PER_WORD), round(hi * CHARS_PER_WORD)
        lines = [f"Difficulty (this overrides any length given below): write between {lo} and {hi} {unit} in total, and do not stop early. "
                 "A story outside this range is wrong.",
                 f"Use at least {targets['own_words']} different words from the list (as many as the list allows).",
                 LEVELS.get(targets.get("tier") if targets.get("tier") in LEVELS else "medium"),
                 "Every other word must be an everyday word that a beginner already knows."]
        if can_measure_uncommon(language_code):
            lines[-1] = (f"Every other word must be an everyday word that a beginner already knows; no more than about "
                         f"{targets['uncommon_pct']}% of all the words may be unusual ones.")
        return " ".join(lines)
    lines = [f"Difficulty (this overrides any length given below): write {size} in total, and do not stop early. A story that is much shorter than this is wrong.",
             f"Use at least {targets['own_words']} different words from the list (as many as the list allows).",
             "Every other word must be an everyday word that a beginner already knows."]
    if can_measure_uncommon(language_code):
        lines[-1] = (f"Every other word must be an everyday word that a beginner already knows; no more than about "
                     f"{targets['uncommon_pct']}% of all the words may be unusual ones.")
    return " ".join(lines)
