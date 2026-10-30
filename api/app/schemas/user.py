"""Response and request models: the learner's account and preferences."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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
