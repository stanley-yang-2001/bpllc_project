"""The numbered-lines format shared by the model jobs that work line by line (pronunciation, translation).

Lines go to the model as data under "Lines:", numbered from 1; the answer must come back as "number | text" lines. Reading the answer
is strict on purpose: only numbered lines in range are used, the first answer for a number wins, and control characters are
removed, so nothing the model adds (headings, notes, instructions) can reach the learner.
"""
from __future__ import annotations

import re

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_LINE = re.compile(r"^\s*(\d{1,3})\s*[|:.)\-]\s*(.+?)\s*$")
_FENCE = re.compile(r"^`{3}.*$", re.M)


def flatten(text) -> str:
    """One line: control characters become spaces and runs of whitespace collapse."""
    return " ".join(_CONTROL.sub(" ", str(text)).split())


def block(lines: list[str]) -> str:
    """The "Lines:" section of a prompt."""
    return "Lines:\n" + "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1)) + "\n"


def parse(raw: str, count: int, max_chars: int, tidy=flatten) -> dict[int, str]:
    """{line number (0-based): text} for the numbered lines the model answered. Others are dropped, never guessed."""
    out: dict[int, str] = {}
    for line in _FENCE.sub("", raw or "").splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        n = int(m.group(1)) - 1
        text = tidy(m.group(2)).strip("*`")
        if 0 <= n < count and n not in out and text and len(text) <= max_chars:
            out[n] = text
    return out
