"""Write from an outline (20 Nov 2026). OFF unless StoryOptions.outline is set; the one-call pipeline stays the default.

The idea, from the learner's side of the project: first decide what the story is (a summary of 4 or 5 events, with the learner's words given to the events they belong to), then
write the text. Two ways to write it, so that a test can tell them apart:

    "whole"  one outline call, then one call writes the whole text from the outline (2 calls). The text is still one piece of connected prose; the outline only fixes what happens
             and where each word goes.
    "beats"  one outline call, then one call per event, each writing the next 1 or 2 sentences after the text so far (6 calls for 5 events): the sentence-by-sentence version.

What is known before the test: the writer v2 block (`writer_v2`) already asks the model to decide a scene before it writes and that one prompt took the passed stories from 8 to 19 of 27
(round 6), so the outline's extra value is only the part the model did not do silently. The risk of "beats" is the one the reviewers already complain about most (choppy, list-like
text: 45% to 62% of the naturalness remarks): a sentence written alone, one call at a time, has no pressure to join with its neighbours, and starts like the last one.
An outline that cannot be read (fewer than 3 events), a failed outline call or a failed beat gives back None, and the caller goes on with the normal one-call pipeline; a failed
extra step never costs the learner a story.
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, Optional

from .prompts.extract import extract_final_passage
from .prompts.templates import DELIMITER

MIN_BEATS, MAX_BEATS = 3, 6
_BEGIN = "Begin:"
_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s*(.+?)\s*$")


def outline_prompt(language_name: str, kind: str, topic: Optional[str], words: Iterable, length: int, level: Optional[str] = None) -> str:
    subject = f"about {topic}" if topic else "about an everyday situation"
    return (
        f"Plan a short {kind} in {language_name} {subject}, for a beginner learning {language_name}. Do not write the text yet: write only its outline, in English.\n\n"
        f"The text will be about {length} words. Write 4 or 5 numbered lines. Each line is one event, in order, where each event leads to the next, and ends with the learner's words that "
        f"belong to that event, in this form:\n1. <what happens> | words: <word>, <word>\n\n"
        f"The learner's words: {', '.join(words)}\n"
        "Use a word only in the event where it fits; you may leave out a word that does not fit anywhere. Do not add anything but the numbered lines."
        + (f"\n{level}" if level else "")
    )


def parse_outline(raw: str) -> list:
    """The numbered lines of an outline answer, as text; [] when there are fewer than MIN_BEATS."""
    beats = []
    for line in (raw or "").splitlines():
        m = _LINE.match(line)
        if m and len(m.group(1)) > 8:
            beats.append(m.group(1))
    return beats[:MAX_BEATS] if len(beats) >= MIN_BEATS else []


def get_outline(call: Callable, language_name: str, kind: str, topic: Optional[str], words: Iterable, length: int, level: Optional[str] = None) -> list:
    try:
        return parse_outline(call(outline_prompt(language_name, kind, topic, list(words), length, level)))
    except Exception:  # noqa: BLE001 - a failed outline must not fail the story
        return []


def _context(prompt: str) -> str:
    i = prompt.rfind(_BEGIN)
    return (prompt[:i] if i >= 0 else prompt).rstrip()


def with_outline(prompt: str, beats: list) -> str:
    """The base prompt with the outline before its final instruction: write the events in order as connected prose, not one sentence an event."""
    lines = "\n".join(f"{i}. {b}" for i, b in enumerate(beats, 1))
    block = ("Follow this outline: the events in this order, with each listed word where its event is. Join the events into connected text (an event can take one or several sentences, "
             f"and two small events can share a sentence); do not write one sentence per line and do not copy the outline's wording.\n{lines}")
    i = prompt.rfind(_BEGIN)
    return prompt.rstrip() + "\n\n" + block if i < 0 else prompt[:i] + block + "\n\n" + prompt[i:]


def beat_prompt(prompt: str, beats: list, done: str, k: int, dialogue: bool, length: int) -> str:
    n = len(beats)
    outline = "\n".join(f"{i}. {b}" for i, b in enumerate(beats, 1))
    share = max(8, round(length / n))
    unit = "one or two lines of the dialogue, each starting with the speaker's name and a colon" if dialogue else "one or two sentences"
    start = ("Nothing is written yet." if not done else f"Text so far:\n{done}")
    last = " This is the last event: end the text on a finished sentence." if k == n else ""
    return (f"{_context(prompt)}\n\nThe text is written in steps, from this outline:\n{outline}\n\n{start}\n\n"
            f"Now write only event {k} of {n}: {unit}, about {share} words, that continue the text so far naturally (start differently from the previous sentence; join it with a connector or a time phrase when that reads better; "
            f"do not repeat anything already written; use the words listed for event {k} if they fit).{last}\n"
            f"Answer with the line {DELIMITER} alone, then the new text only.")


def write_beats(call: Callable, prompt: str, beats: list, dialogue: bool, length: int) -> Optional[str]:
    done = ""
    for k in range(1, len(beats) + 1):
        try:
            part = extract_final_passage(call(beat_prompt(prompt, beats, done, k, dialogue, length)))
        except Exception:  # noqa: BLE001
            return None
        if not part.strip():
            return None
        done = (done + ("\n" if dialogue else " ") + part.strip()).strip()
    return done
