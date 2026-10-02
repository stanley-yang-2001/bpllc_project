"""
Final Passage Extractor — strips the hidden planning summary from the model's raw output.

The story prompt asks the model to silently plan (Character/Want/Event/Resolution), write
a short internal summary, then a ===STORY=== delimiter, then the actual passage/dialogue.
This module deterministically keeps only what's after that delimiter — not trusting the
model to simply "not show" the planning, since smaller open-source models aren't reliably
obedient about that instruction on their own.

extract_final_passage() is the plain, testable function (see
tests/test_final_passage_extractor.py); FinalPassageExtractor is the Langflow wrapper that
just calls it. Kept in one file, same reasoning as story_prompt_builder.py: Langflow's
component scanner inspects imports before fully executing a file top-to-bottom, so a
cross-file import between our own custom components isn't reliable here.
"""

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

DELIMITER = "===STORY==="


def extract_final_passage(raw_text, delimiter: str = DELIMITER) -> str:
    """Return only the text after the first occurrence of `delimiter`.

    Falls back to the full (stripped) text if the delimiter isn't found — so the app still
    works even if the model forgets to include it. None or empty input returns "".
    """
    if not raw_text:
        return ""

    if delimiter in raw_text:
        _, _, after = raw_text.partition(delimiter)
        return after.strip()

    return raw_text.strip()


class FinalPassageExtractor(Component):
    display_name = "Final Passage Extractor"
    description = (
        "Strips the hidden planning summary from the story-generation agent's raw output, "
        "keeping only the text after the ===STORY=== delimiter."
    )
    icon = "Scissors"
    name = "FinalPassageExtractor"

    inputs = [
        MessageTextInput(
            name="raw_text",
            display_name="Raw Agent Output",
            info="The story-generation agent's raw response, including its hidden planning.",
        ),
    ]

    outputs = [
        Output(display_name="Final Passage", name="final_passage", method="run"),
    ]

    def run(self) -> Message:
        result = extract_final_passage(self.raw_text)
        message = Message(text=result)
        self.status = message  # shows the cleaned passage in the node's UI preview
        return message