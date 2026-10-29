"""Response models. They make the OpenAPI schema (and the generated TypeScript types) describe real shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from tutor_core import difficulty, prompts


class CustomColors(BaseModel):
    """The five parts of a custom theme (design 3G), each a #rrggbb colour."""
    page: str
    cards: str
    text: str
    borders: str
    accent: str


class PreferencesOut(BaseModel):
    active_language: str | None
    ui_follows_study_language: bool
    chat_in_study_language: bool
    meaning_mode: Literal["native", "study", "both"]
    theme: str
    custom_colors: CustomColors | None


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    native_language: str
    languages: list[str]
    preferences: PreferencesOut | None = None      # null until the learner saves one (then the app uses defaults)


class WordOut(BaseModel):
    id: int
    language: str
    word: str
    meaning: str | None
    set_id: int | None = None          # null: the General set
    created_at: datetime


class SetOut(BaseModel):
    id: int
    language: str
    name: str
    count: int


class SetList(BaseModel):
    items: list[SetOut]
    general_count: int
    total_count: int


class WordPage(BaseModel):
    items: list[WordOut]
    total: int
    limit: int
    offset: int


class DeleteResult(BaseModel):
    deleted: int


class InvalidRow(BaseModel):
    row: int
    reason: str


class UploadResult(BaseModel):
    added: int
    duplicates: int
    invalid_count: int
    invalid: list[InvalidRow]


class LanguageOut(BaseModel):
    code: str
    name: str
    native: str
    tier: int
    stories_enabled: bool


class MetaOut(BaseModel):
    policy_version: str
    privacy_contact: str | None
    policy_languages: list[str]          # languages with an approved, current policy copy; English first


class PolicyOut(BaseModel):
    language: str                        # the copy that is being served
    version: str
    fallback: bool                       # true when English stands in for the language asked for
    doc: dict[str, Any]                  # the copy itself: data, never HTML (design 3I)


class StatusOut(BaseModel):
    status: str


class ServiceCheck(BaseModel):
    ok: bool | None = None
    status: str | None = None
    detail: str | None = None


class HealthOut(BaseModel):
    postgres: ServiceCheck
    langflow: ServiceCheck
    groq: ServiceCheck
    ai_mode: str


class ToolCallOut(BaseModel):
    name: str
    args: dict
    output: str
    failed: bool = False


class ChatOut(BaseModel):
    reply: str
    tool_calls: list[ToolCallOut]
    session_id: str


class StoryOptionsOut(BaseModel):
    types: list[str]
    topics: list[str]


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


class FlashcardOut(BaseModel):
    id: int
    word: str
    meaning: str


class FlashcardSet(BaseModel):
    items: list[FlashcardOut]
    total: int


class DictationOut(BaseModel):
    id: int
    word: str
    meaning: str | None = None


class DictationSet(BaseModel):
    items: list[DictationOut]
    total: int


class ChoiceOut(BaseModel):
    id: int
    prompt: str
    answer: str
    choices: list[str]
    direction: str


class ChoiceSet(BaseModel):
    items: list[ChoiceOut]
    total: int


class StarterPackOut(BaseModel):
    id: str                     # basics, food, people or numbers
    total: int
    remaining: int              # words of the pack the learner does not have yet


class StarterPackList(BaseModel):
    items: list[StarterPackOut]
    gloss_available: bool       # true when the pack words would come with a ready-made English meaning for this learner


class StarterAdded(BaseModel):
    added: int
    duplicates: int
    with_meaning: bool          # false: the words have no meaning yet; the tutor can write them in the learner's chosen language


class AnswerIn(BaseModel):
    word_id: int
    correct: bool


class AnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(max_length=50)


class ProgressOut(BaseModel):
    language: str
    new: int                    # words with a meaning never practised yet
    learning: int               # practised, not yet in box 4
    known: int                  # box 4 or 5
    due: int                    # practised and due now (new words are not counted here)
    streak: int                 # days in a row, UTC days
    practised_today: bool


class ClozeItem(BaseModel):
    before: str
    after: str
    answer: str
    hint: str
    choices: list[str]
    word_id: int | None = None          # the learner's word this blank is for, so the answer can be remembered


class ClozeSet(BaseModel):
    story_id: int
    language: str
    items: list[ClozeItem]


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
