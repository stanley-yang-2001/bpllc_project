"""
Story Generator Tool — consolidated, single-call version of the Step 8 pipeline, built to
be used as ONE tool by the top-level Language Agent (Step 9).

Why this is ONE component: when a component is used as a Tool by another Agent, Langflow only
returns that component's own output; it does not execute anything wired downstream of it on the
canvas. The old Step 8 pipeline was four separate components chained together (word loader, guard,
prompt builder, passage extractor), so exposing it as a tool would have leaked the hidden planning
summary straight to the learner. This module therefore does everything in one atomic operation. The
four Step 8 components were deleted on 18 October 2026; only the Word Loader stays, kept unwired on
the canvas for debugging (see tutor_core.tools.vocabulary_for_agent).

generate_story_for_learner() takes an injectable call_groq_fn so it's testable without a
real network call (see tests/test_story_tool.py); call_groq() itself is the real
implementation, using the same request pattern already proven working in scripts/smoke_test.py
(including the User-Agent header, without which Groq's Cloudflare protection blocks the
request with an HTTP 1010).

M3: the pipeline is tutor_core.story and the tool logic is tutor_core.tools.story_for_agent (tested in
api/tests/test_tutor_core_story.py and test_tutor_tools.py). The story is built from the CALLING LEARNER's words in the
chosen language only; `learner_id` and `active_language` are hidden inputs set by the API, and without a usable
learner the tool refuses (fail closed). The visible `language`, `story_type`, `topic` and `difficulty` arguments are what the Agent
fills in; the last three are optional and carry what the learner asked for in chat ("a dialogue", "a letter about my trip", "an easy story").
A type or topic the tool cannot use is cleaned or refused inside tutor_core.prompts, never passed into the prompt as it came.
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
        MessageTextInput(
            name="story_type",
            display_name="Story type",
            info="Optional. Only a kind of text the learner NAMED: dialogue, diary, letter, place, routine, anecdote, "
                 "or a short kind in plain words (for example 'poem'). A plain request for 'a story' names no kind: "
                 "leave this blank so the tutor chooses.",
            value="",
            tool_mode=True,
        ),
        MessageTextInput(
            name="topic",
            display_name="Topic",
            info="Optional. What the text should be about, in a few plain words (for example 'my trip to the market'). "
                 "Leave blank to let the tutor choose.",
            value="",
            tool_mode=True,
        ),
        MessageTextInput(
            name="difficulty",
            display_name="Difficulty",
            info="Optional. Only if the learner asked for an easy, medium or hard story: pass easy, medium or hard. "
                 "Leave blank otherwise.",
            value="",
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
        message = Message(text=story_for_agent(self.language, self.learner_id, self.active_language,
                                               self.story_type, self.topic, self.difficulty))
        self.status = message
        return message
