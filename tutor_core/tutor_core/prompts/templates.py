"""The two classic story templates (narration, dialogue), the delimiter and the empty-vocabulary message."""
from __future__ import annotations



DELIMITER = "===STORY==="

EMPTY_VOCABULARY_MESSAGE = (
    "You don't have any vocabulary yet! Tell me a word to add, and I'll remember it — "
    "once you've added a few, ask me for a story."
)

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
    "1. First person, aim for 5 to 6 short sentences (5-10 words each), each following "
    "logically from the last — no unrelated facts.\n"
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
    "1. Aim for 5 to 6 lines of back-and-forth conversation, each line a real, logical "
    "response to the one before — rewrite any line that doesn't answer the last.\n"
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

