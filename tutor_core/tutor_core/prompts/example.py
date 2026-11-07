"""An example story inside the prompt (6 Nov 2026, step 5 of the quality plan). OFF unless STORY_EXAMPLES=1.

The wording matters more than the idea. The example is there to show how good the sentences are, and a model told only "here is an
example" tends to copy its topic, names, length and format. So the wording is plain, not vague:

  * it says what the example is for (the quality of the language: natural, correct sentences),
  * it says what NOT to take from it (topic, characters, sentences, words, length, format),
  * it says the requirements above win,
  * it comes after the requirements, right before the final instruction, and is quoted as text.

A vaguer wording ("use it as a reference") leaves the model to guess which parts matter, and it then either copies or ignores it
unevenly. The comparison page shows what a particular wording does.
"""
from __future__ import annotations

from .builder import _BEGIN

_FRAME = (
    "Example of the quality we want (use it only to see how natural and correct the sentences are; do not copy its topic, characters, "
    "sentences or words, and do not take its length or format from it. The requirements above decide what to write):\n"
    "<<<\n{example}\n>>>\n\n"
)


def with_example(prompt: str, example: str) -> str:
    """The prompt with the example quoted before its last instruction (the line that starts with "Begin:"); unchanged when there is none."""
    example = (example or "").strip()
    i = prompt.rfind(_BEGIN)
    if not example or i < 0:
        return prompt
    return prompt[:i] + _FRAME.format(example=example) + prompt[i:]
