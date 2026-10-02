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
    "You are a creative writer crafting a short, simple reading passage for a "
    "language-learning beginner in {language}.\n\n"
    "First, silently plan (do not show this):\n"
    "- Character: a simple name.\n"
    "- Want: something they want, have, or need — tied to a vocabulary word if possible.\n"
    "- Event: a question, request, or small problem needing a response, following "
    "logically from Want.\n"
    "- Resolution: how it's resolved — vary the shape (agreement, farewell, thanks, or a "
    "plan like \"tomorrow, I will...\"), not just yes/no. This is where yes/no/please/thank "
    "you fit as real reactions, not random insertions.\n"
    "Write a 1-2 sentence summary of these four parts, then the line ===STORY=== alone, "
    "then the passage.\n\n"
    "Passage rules:\n"
    "1. First person, aim for 5 to 6 short sentences (5-10 words each), each following logically "
    "from the last — no unrelated facts.\n"
    "2. Use words that truly fit from: {words}. You don't need to include every one — "
    "only use ones that make sense, never forcing a word that breaks the logical flow. "
    "You may inflect a word's form (verb tense, plural, etc.) as needed for grammar, "
    "keeping the same root word.\n"
    "3. You may add basic grammar words (articles, pronouns, prepositions, conjunctions) "
    "and simple verbs (is, have, want, like, go, see) — but no new content words outside "
    "the list.\n"
    "4. No conditionals, semicolons, or multi-idea sentences. Natural spoken tone, not "
    "formal narration.\n"
    "5. Output ONLY the ===STORY=== line and the passage — no title, no explanation, no "
    "planning notes.\n\n"
    "Tone example only (your own topic must come from your own planned Event, not this "
    "example):\n"
    '"Hello! I am hungry today. I see a small shop with fresh bread. I say thank you and '
    'eat happily."\n\n'
    "Begin: planning, then delimiter, then passage."
)

DIALOGUE_TEMPLATE = (
    "You are a creative writer crafting a short, simple dialogue for a language-learning "
    "beginner in {language}.\n\n"
    "First, silently plan (do not show this):\n"
    "- Characters: two simple, real names.\n"
    "- Want: something one friend wants, has, or needs — tied to a vocabulary word if "
    "possible.\n"
    "- Event: a question, request, or small problem needing a response, following "
    "logically from Want.\n"
    "- Resolution: how the other friend responds — vary the shape (agreement, farewell, "
    "thanks, or a plan like \"tomorrow, we will...\"), not just yes/no. This is where "
    "yes/no/please/thank you fit as real reactions, not random insertions.\n"
    "Write a 1-2 sentence summary of these four parts, then the line ===STORY=== alone, "
    "then the dialogue.\n\n"
    "Dialogue rules:\n"
    "1. Aim for 5 to 6 lines of back-and-forth conversation, each line a real, logical response "
    "to the one before — rewrite any line that doesn't answer the last.\n"
    "2. Use words that truly fit from: {words}. You don't need to include every one — "
    "only use ones that make sense, never forcing a word that breaks the logical flow. "
    "You may inflect a word's form (verb tense, plural, etc.) as needed for grammar, "
    "keeping the same root word.\n"
    "3. You may add basic grammar words (articles, pronouns, prepositions, conjunctions) "
    "and simple verbs (is, have, want, like, go, see) — but no new content words outside "
    "the list.\n"
    "4. Keep each line short (3-8 words). No conditionals, semicolons, or multi-idea "
    "lines.\n"
    "5. Format each line as: Name: line\n"
    "6. Output ONLY the ===STORY=== line and the dialogue — no title, no explanation, no "
    "planning notes.\n\n"
    "Tone example only (your own topic must come from your own planned Event, not this "
    "example):\n"
    "Mia: Hello! Do you have any bread?\n"
    "Leo: Yes, I have some. Do you want it?\n"
    "Mia: Yes, please! Thank you so much.\n\n"
    "Begin: planning, then delimiter, then dialogue."
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