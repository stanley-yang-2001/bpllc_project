"""
Empty-vocabulary guard — Story 5.

Decides whether there's enough vocabulary to generate a story, or whether the learner should
be asked to add words first. Mirrors the check wired in Langflow's UI using the built-in
If-Else (Conditional Router) component: input_text = Word Loader's output, match_text = "",
operator = "equals" -> true_result routes to EMPTY_VOCABULARY_MESSAGE, false_result routes
into the Prompt Template.
"""

EMPTY_VOCABULARY_MESSAGE = (
    "You don't have any vocabulary yet! Tell me a word to add, and I'll remember it — "
    "once you've added a few, ask me for a story."
)


def should_generate_story(words: str) -> bool:
    """Return True if there's enough vocabulary to generate a story, False otherwise."""
    return bool((words or "").strip())