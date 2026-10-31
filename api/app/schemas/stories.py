"""Response and request models: making, saving and listing stories."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator
from tutor_core import difficulty, prompts


class DifficultyTargets(BaseModel):
    length: int
    own_words: int
    uncommon_pct: int


class DifficultyLimits(BaseModel):
    """Each limit is [smallest, largest], both allowed."""
    length: list[int]
    own_words: list[int]
    uncommon_pct: list[int]


class DifficultyOptions(BaseModel):
    presets: dict[str, DifficultyTargets]        # easy, medium, hard: the numbers a preset asks for
    limits: DifficultyLimits                     # what a learner's own numbers may be


class StoryOptionsOut(BaseModel):
    types: list[str]
    topics: list[str]
    difficulty: DifficultyOptions


class GeneratedStoryOut(BaseModel):
    story: str
    language: str
    story_type: str | None
    topic: str | None
    report: dict
    words_total: int
    words_used: int


class StoryCard(BaseModel):
    id: int
    language: str
    story_type: str | None
    topic: str | None
    body: str
    passed: bool
    created_at: datetime
    difficulty: str | None = None      # easy / medium / hard / custom, or None when no tier was asked for


class StoryFull(StoryCard):
    report: dict


class StoryPage(BaseModel):
    items: list[StoryCard]
    total: int
    limit: int
    offset: int


# --- what the learner sends to make and save a story
MAX_STORY_BODY = 8000          # characters; a generated story is a few hundred


class DifficultyIn(BaseModel):
    """The learner's difficulty choice: nothing (any), a preset, or custom with their own numbers (tutor_core.difficulty)."""
    difficulty: str | None = None
    length: int | None = None
    own_words: int | None = None
    uncommon_pct: int | None = None

    @model_validator(mode="after")
    def _difficulty(self):
        self.targets           # raises ValueError (shown to the learner as a 422) for anything not allowed
        return self

    @property
    def targets(self):
        return difficulty.resolve(self.difficulty, self.length, self.own_words, self.uncommon_pct)


class GenerateIn(DifficultyIn):
    language: str
    set_ids: list[int] | None = Field(default=None, max_length=100)     # the sets to use (0 = General); none = all of the learner's words
    story_type: str | None = None
    topic: str | None = None

    @field_validator("story_type")
    @classmethod
    def _type(cls, value):
        """A built-in type, an alias ("conversation"), or the learner's own short label ("a poem"). The result is the
        canonical built-in name or the cleaned label; text that cannot be used never gets as far as the prompt."""
        if value is None:
            return None
        resolved = prompts.resolve_story_type(value)
        if resolved is None:
            raise ValueError("Pick one of the listed kinds, or write a short one of your own: up to 40 characters and 6 words, "
                             "with letters, numbers, spaces, apostrophes and hyphens only.")
        return resolved

    @field_validator("topic")
    @classmethod
    def _topic(cls, value):
        """A topic from the list, or the learner's own short one ("my grandma's kitchen"): the same rule and limits as a
        custom kind. Text that cannot be used never gets as far as the prompt, where it is quoted as a subject."""
        if value is None:
            return None
        resolved = prompts.clean_topic(value)
        if resolved is None:
            raise ValueError("Pick a topic from the list, or write a short one of your own: up to 40 characters and 6 words, "
                             "with letters, numbers, spaces, apostrophes and hyphens only.")
        return resolved


class SaveIn(DifficultyIn):
    language: str
    body: str
    story_type: str | None = None
    topic: str | None = None
    model: str | None = Field(default=None, max_length=120)      # the model name the page showed; used only if it is the learner's own, see save()

    @field_validator("body")
    @classmethod
    def _body(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("The story is empty.")
        if len(value) > MAX_STORY_BODY:
            raise ValueError(f"Keep stories under {MAX_STORY_BODY} characters.")
        return value

    _type = field_validator("story_type")(GenerateIn._type.__func__)
    _topic = field_validator("topic")(GenerateIn._topic.__func__)
