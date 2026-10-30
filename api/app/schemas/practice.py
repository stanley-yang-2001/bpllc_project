"""Response and request models: practice material and remembered answers."""
from __future__ import annotations


from pydantic import BaseModel, Field


class FlashcardOut(BaseModel):
    id: int
    word: str
    meaning: str


class FlashcardSet(BaseModel):
    items: list[FlashcardOut]
    total: int


class PosCard(BaseModel):
    id: int
    word: str
    answer: str
    options: list[str]
    meaning: str | None = None


class PosSet(BaseModel):
    items: list[PosCard]
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
