"""Response models. They make the OpenAPI schema (and the generated TypeScript types) describe real shapes."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    native_language: str
    languages: list[str]


class WordOut(BaseModel):
    id: int
    language: str
    word: str
    meaning: str | None
    created_at: datetime


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
