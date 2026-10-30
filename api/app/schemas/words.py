"""Response and request models: words, sets, uploads and starter packs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WordOut(BaseModel):
    id: int
    language: str
    word: str
    meaning: str | None
    pos: str | None = None             # part of speech: a code from the language's own list (tutor_core.pos), or none
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
