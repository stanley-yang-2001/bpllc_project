"""Response and request models: site information, health and chat answers."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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
