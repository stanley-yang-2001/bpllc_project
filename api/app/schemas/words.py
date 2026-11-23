"""Response and request models: words, sets, uploads and starter packs."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PictureOut(BaseModel):
    """The picture of a word: an emoji, or the learner's own photo (kept as a JPEG of at most 512 pixels, and a small copy of at most 96)."""
    kind: Literal["emoji", "photo"]
    emoji: str | None = None           # the emoji itself, when the kind is "emoji"
    url: str | None = None             # the photo, when the kind is "photo"; the address changes when the photo does
    thumb_url: str | None = None       # the small copy, for lists


class EmojiIn(BaseModel):
    emoji: str = Field(max_length=64)


class WordOut(BaseModel):
    id: int
    language: str
    word: str
    meaning: str | None
    pos: str | None = None             # part of speech: a code from the language's own list (tutor_core.pos), or none
    set_id: int | None = None          # null: the General set
    created_at: datetime
    picture: PictureOut | None = None  # null: no picture


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


class PosCategories(BaseModel):
    language: str
    items: list[str]


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
