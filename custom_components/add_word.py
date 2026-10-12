"""
Add Word — Story 3.

Agent-callable tool: adds one word to the CALLING LEARNER's vocabulary in the active language (tutor.words).
The learner and language arrive as hidden inputs set by the API (see tutor_core/tools.py); with no usable learner
the tool refuses and touches no data (fail closed).

The logic is tutor_core.tools.add_word_for_agent, tested in api/tests/test_tutor_tools.py; this file is only the
Langflow wrapper.

To use as a tool: after adding this component to the canvas, enable "Tool Mode" on it, then
attach it to an Agent node's Tools input. The LLM fills in `word` based on the chat message.
"""

from tutor_core.tools import add_word_for_agent
from langflow.custom import Component
from langflow.io import MessageTextInput, Output, StrInput


class AddWord(Component):
    display_name = "Add Word"
    description = (
        "Adds a single new word to the vocabulary table. Enable Tool Mode and attach to an "
        "Agent so it can be called from chat."
    )
    icon = "Plus"
    name = "AddWord"

    inputs = [
        MessageTextInput(
            name="word",
            display_name="Word",
            info="The word to add to the learner's known vocabulary.",
            tool_mode=True,
        ),
        StrInput(
            name="learner_id",
            display_name="Learner ID (hidden)",
            info="Set per request by the API through tweaks, as a STRING. The Agent never sees this field. Never name it user_id: "
                 "Langflow reserves that name on every component.",
            value="",
            advanced=True,
            tool_mode=False,
        ),
        StrInput(
            name="active_language",
            display_name="Active language (hidden)",
            info="Set per request by the API through tweaks: the learner's selected language, as an ISO code.",
            value="",
            advanced=True,
            tool_mode=False,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run"),
    ]

    def run(self) -> str:
        return add_word_for_agent(self.word, self.learner_id, self.active_language)
