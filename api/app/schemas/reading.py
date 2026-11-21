"""Request and response models for the reader: which of the learner's words stand in a text."""
from __future__ import annotations

from pydantic import BaseModel, Field

MAX_TEXT = 8000           # characters: the same limit as a saved story (schemas.stories.MAX_STORY_BODY)


class GlossIn(BaseModel):
    language: str
    text: str = Field(max_length=MAX_TEXT)


class GlossSpan(BaseModel):
    start: int            # index of the first character, counted the way a JavaScript string counts (UTF-16 units), so the page can slice with it
    end: int              # index after the last character
    word_id: int


class GlossWord(BaseModel):
    id: int
    word: str
    meaning: str | None
    pos: str | None = None


class GlossOut(BaseModel):
    spans: list[GlossSpan]
    words: list[GlossWord]          # each word of the learner's that stands in the text, once
