"""The note placed at the top of the story prompt."""
from __future__ import annotations

from .measuring import can_measure_uncommon
from .presets import CHARS_PER_WORD, ask_size, is_unspaced


def prompt_note(language_code: str, targets: dict) -> str:
    """The note placed at the top of the story prompt. It states numbers only; nothing the learner typed goes into it."""
    asked = ask_size(language_code, targets["length"])
    if is_unspaced(language_code):
        size = f"about {round(asked * CHARS_PER_WORD)} characters"
    else:
        size = f"about {asked} words"
    lines = [f"Difficulty (this overrides any length given below): write {size} in total, and do not stop early. A story that is much shorter than this is wrong.",
             f"Use at least {targets['own_words']} different words from the list (as many as the list allows).",
             "Every other word must be an everyday word that a beginner already knows."]
    if can_measure_uncommon(language_code):
        lines[-1] = (f"Every other word must be an everyday word that a beginner already knows; no more than about "
                     f"{targets['uncommon_pct']}% of all the words may be unusual ones.")
    return " ".join(lines)
