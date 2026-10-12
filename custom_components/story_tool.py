"""
Story Generator Tool — consolidated, single-call version of the Step 8 pipeline, built to
be used as ONE tool by the top-level Language Agent (Step 9).

Why this duplicates logic already in word_loader.py, story_guard.py, story_prompt_builder.py,
and final_passage_extractor.py: when a component is used as a Tool by another Agent,
Langflow only returns that component's own output — it does not execute anything wired
downstream of it on the canvas. The Step 8 pipeline is four separate components chained
together, so exposing the Agent alone as a tool would leak the hidden planning summary
straight to the learner, since the Final Passage Extractor (downstream) would never run as
part of the tool call. This module inlines everything into one atomic operation instead.

The standalone Step 8 components remain on the canvas for manual, visual debugging in the
Playground — this file is the production path the top-level Agent actually calls.

generate_story_for_learner() takes an injectable call_groq_fn so it's testable without a
real network call (see tests/test_story_tool.py); call_groq() itself is the real
implementation, using the same request pattern already proven working in scripts/smoke_test.py
(including the User-Agent header, without which Groq's Cloudflare protection blocks the
request with an HTTP 1010).

M3: the pipeline is tutor_core.story and the tool logic is tutor_core.tools.story_for_agent (tested in
api/tests/test_tutor_core_story.py and test_tutor_tools.py). The story is built from the CALLING LEARNER's words in the
chosen language only; `learner_id` and `active_language` are hidden inputs set by the API, and without a usable
learner the tool refuses (fail closed). The visible `language` argument is what the Agent fills in.
"""

from tutor_core.tools import story_for_agent
from langflow.custom import Component
from langflow.io import MessageTextInput, Output, StrInput
from langflow.schema.message import Message


class StoryGeneratorTool(Component):
    display_name = "Story Generator Tool"
    description = (
        "Generates a vocabulary-constrained story or dialogue for the learner, ready to "
        "use as a single tool for the top-level Language Agent. Handles vocabulary "
        "lookup, the empty-vocabulary guard, prompt building, the Groq call, and stripping "
        "the hidden planning summary — all in one atomic call."
    )
    icon = "BookOpenCheck"
    name = "StoryGeneratorTool"

    inputs = [
        MessageTextInput(
            name="language",
            display_name="Language",
            info="Name of the language for the story, e.g. 'Spanish', 'Chinese' ,'English' etc. Required.",
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
        Output(display_name="Story", name="story", method="run"),
    ]

    def run(self) -> Message:
        message = Message(text=story_for_agent(self.language, self.learner_id, self.active_language))
        self.status = message
        return message
