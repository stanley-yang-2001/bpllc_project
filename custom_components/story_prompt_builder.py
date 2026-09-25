"""
Story Prompt Builder — Story 5 (prompt half).

Builds the story-generation prompt from a language and word list, alternating between two
interchangeable formats:
  - "narration": a short first-person passage
  - "dialogue": a short two-person conversation

Both exist because the vocabulary list often includes conversational words (yes, no, hello,
goodbye) that have a natural home in dialogue but not in narration — forcing them into
narration produced stiff, unnatural sentences. When `style` isn't specified, one is picked
at random in code, so real usage naturally alternates between formats across requests. Both
templates also explicitly tell the model it doesn't need to force in every single vocabulary
word — only the ones that fit naturally.

This is the single source of truth for the prompt wording: build_story_prompt() is a plain,
testable function (see tests/test_story_prompt_builder.py), and the Component below just
calls it. Kept in one file — Langflow's component scanner inspects imports before fully
executing a file top-to-bottom, which made a previous two-file split (prompt_template.py +
this file) unreliable to load.
"""

import random
from typing import Optional

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, Output
from langflow.schema.message import Message

NARRATION_TEMPLATE = (
    "You are a language tutor generating a short, simple reading passage for a beginner.\n\n"
    "Guidelines:\n"
    "1. Write a short first-person narration in {language}.\n"
    "2. Naturally use several of these words where they fit: {words}. You don't need to "
    "include every single one — only use the ones that make sense in context.\n"
    "3. You may also use common everyday words needed to form natural, grammatical "
    "sentences — articles, pronouns, prepositions, conjunctions, and simple verbs (like "
    "is, have, want, like, go, see).\n"
    "4. Avoid introducing new, unrelated content words outside the list above.\n"
    "5. Keep sentences SHORT and SIMPLE — about 5 to 10 words each. Avoid conditionals "
    "(if/then), semicolons, and joining multiple ideas into one long sentence.\n"
    "6. Write like natural, everyday spoken language — not formal or literary narration.\n"
    "7. Write 3 to 4 short sentences total.\n"
    "8. Output ONLY the passage itself — no title, no explanation, no preamble.\n\n"
    "Style example (do NOT copy these words — just match this simple, natural tone):\n"
    '"Hello! I have a book. I want tea today. Thank you, my friend."\n\n'
    "Now write the passage."
)

DIALOGUE_TEMPLATE = (
    "You are a language tutor generating a short, simple reading passage for a beginner.\n\n"
    "Guidelines:\n"
    "1. Write a short dialogue (a conversation between two friends) in {language}.\n"
    "2. Naturally use several of these words where they fit the conversation: {words}. "
    "You don't need to include every single one — only use the ones that make sense in "
    "context.\n"
    "3. You may also use common everyday words needed to form natural, grammatical "
    "sentences — articles, pronouns, prepositions, conjunctions, and simple verbs (like "
    "is, have, want, like, go, see).\n"
    "4. Avoid introducing new, unrelated content words outside the list above.\n"
    "5. Keep each line SHORT and SIMPLE — about 3 to 8 words. Avoid conditionals "
    "(if/then), semicolons, and joining multiple ideas into one long sentence.\n"
    "6. Write like natural, everyday spoken conversation.\n"
    "7. Write 3 to 4 lines of dialogue total, alternating between the two friends.\n"
    "8. Format each line as: Name: line\n"
    "9. Output ONLY the dialogue itself — no title, no explanation, no preamble.\n\n"
    "Style example (do NOT copy these words — just match this simple, natural tone and "
    "format):\n"
    "Alex: Hello! I have a book.\n"
    "Sam: Thank you! Do you want tea?\n"
    "Alex: Yes, please.\n\n"
    "Now write the dialogue."
)

VALID_STYLES = {"narration": NARRATION_TEMPLATE, "dialogue": DIALOGUE_TEMPLATE}


def build_story_prompt(language: str, words: str, style: Optional[str] = None) -> str:
    """Render the story prompt for a given language, comma-separated word list, and style.

    `style` must be "narration" or "dialogue" if given; if omitted, one is chosen at random.
    Raises ValueError if language/words are empty, or style is anything other than the two
    valid options.
    """
    language = (language or "").strip()
    words = (words or "").strip()

    if not language:
        raise ValueError("language must be a non-empty string")
    if not words:
        raise ValueError("words must be a non-empty string")

    if not style or style == "random":
        style = random.choice(list(VALID_STYLES.keys()))
    if style not in VALID_STYLES:
        raise ValueError(f"style must be one of {list(VALID_STYLES.keys())}, got {style!r}")

    return VALID_STYLES[style].format(language=language, words=words)


class StoryPromptBuilder(Component):
    display_name = "Story Prompt Builder"
    description = (
        "Builds the story-generation prompt from a language and word list, alternating "
        "between narration and dialogue styles (random unless overridden)."
    )
    icon = "MessageSquare"
    name = "StoryPromptBuilder"

    inputs = [
        MessageTextInput(
            name="language",
            display_name="Language",
            info="The target language for the story.",
        ),
        MessageTextInput(
            name="words",
            display_name="Words",
            info="Comma-separated known vocabulary, from Word Loader.",
        ),
        DropdownInput(
            name="style",
            display_name="Style",
            options=["random", "narration", "dialogue"],
            value="random",
            info="Pick a fixed style to force it for testing, or leave as 'random' for "
            "normal use (alternates between the two on each request).",
        ),
    ]

    outputs = [
        Output(display_name="Prompt", name="prompt", method="run"),
    ]

    def run(self) -> Message:
        prompt_text = build_story_prompt(self.language, self.words, style=self.style)

        message = Message(text=prompt_text)
        self.status = message  # shows the rendered prompt in the node's UI preview
        return message