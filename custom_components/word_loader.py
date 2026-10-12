"""
Word Loader — Story 4.

Reads ONE learner's words in the active language and returns them as a single comma-separated string. Kept on the
canvas for debugging only (it is not wired to the Agent). The learner and language arrive as hidden inputs set by the
API; with no usable learner it refuses and reads nothing (fail closed). The logic is tutor_core.tools.vocabulary_for_agent.


"""

from tutor_core.tools import vocabulary_for_agent
from langflow.custom import Component
from langflow.io import Output, StrInput
from langflow.schema.message import Message


class WordLoader(Component):
    display_name = "Word Loader"
    description = (
        "Reads one learner's vocabulary in the active language and returns it as a comma-separated string. "
        "For debugging; not wired to the Agent."
    )
    icon = "BookOpen"
    name = "WordLoader"

    inputs = [
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
        Output(display_name="Words", name="words", method="run"),
    ]

    def run(self) -> Message:
        message = Message(text=vocabulary_for_agent(self.learner_id, self.active_language))
        self.status = message  # shows the returned value in the node's UI preview
        return message
