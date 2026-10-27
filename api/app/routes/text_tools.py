"""Readings and translations: the HTTP side only (the rules are in services/text_tools.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from tutor_core import pronunciation, translation

from ..deps import current_user, require_language
from ..services import text_tools
from ..services.ai_runner import AiRunner, ai_runner_for

router = APIRouter(tags=["text tools"])


class PronounceBody(BaseModel):
    language: str
    texts: list[str] = Field(min_length=1, max_length=pronunciation.MAX_LINES)


class ReadingItem(BaseModel):
    text: str
    reading: str | None


class PronounceOut(BaseModel):
    kind: str                 # ipa, pinyin, romaji or romanization
    approximate: bool         # true when the model wrote it (IPA): treat as a guide, not a dictionary
    items: list[ReadingItem]


class TranslateBody(BaseModel):
    language: str
    target_language: str
    texts: list[str] = Field(min_length=1, max_length=translation.MAX_LINES)
    words: bool = False       # a list of words (short meaning) rather than the lines of a story


class TranslationItem(BaseModel):
    text: str
    translation: str | None


class TranslateOut(BaseModel):
    target_language: str
    items: list[TranslationItem]


@router.post("/pronounce", response_model=PronounceOut)
def pronounce(body: PronounceBody, user: dict = Depends(current_user), runner: AiRunner = Depends(ai_runner_for)):
    require_language(body.language)
    return text_tools.pronounce(runner, user["id"], body.language, body.texts)


@router.post("/translate", response_model=TranslateOut)
def translate(body: TranslateBody, user: dict = Depends(current_user), runner: AiRunner = Depends(ai_runner_for)):
    require_language(body.language)
    return text_tools.translate(runner, user["id"], body.language, body.target_language, body.texts, body.words)
