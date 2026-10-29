"""Meanings written by the model for the learner's own words (the HTTP side only; the rules are in services/meanings.py). The learner
asks for it (a checkbox when adding a word, a button on the vocabulary page for every word that has none)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from tutor_core import definitions
from tutor_core.languages import LANGUAGES

from ..deps import current_user, require_language
from ..errors import validation_error
from ..db import connection
from ..services import meanings, preferences
from ..services.ai_runner import AiRunner, ai_runner_for

router = APIRouter(prefix="/words", tags=["words"])


class DefineBody(BaseModel):
    language: str
    ids: list[int] | None = Field(default=None, max_length=definitions.MAX_BATCH)   # these words; none = the next words with no meaning
    set: str | None = Field(default=None, max_length=12)                            # with no ids: all, general or one set
    meaning_mode: Literal["native", "study", "both"] | None = None                  # none = the account's saved choice
    meaning_language: str | None = None                                             # one exact site language; wins over the mode


@router.post("/define")
def define(body: DefineBody, request: Request, user: dict = Depends(current_user), runner: AiRunner = Depends(ai_runner_for)):
    """Writes meanings for up to 25 of the learner's words that have none and says how many are still without one."""
    require_language(body.language)
    if body.meaning_language is not None and body.meaning_language not in LANGUAGES:
        raise validation_error("Choose one of the site languages for the meanings.")
    return meanings.write_missing(request.app.state.pool, runner, user["id"], body.language, body.ids, body.set, _languages(request, user, body))


def _languages(request: Request, user: dict, body: DefineBody) -> list[str]:
    """Where the meanings are written: an exact language if one was asked for, else the mode sent, else the mode saved on the account
    (the learner's own language until they choose otherwise)."""
    if body.meaning_language is not None:
        return [body.meaning_language]
    mode = body.meaning_mode
    if mode is None:
        with connection(request.app.state.pool) as conn:
            saved = preferences.get(conn, user["id"])
        mode = (saved or {}).get("meaning_mode") or "native"
    native = user.get("native_language")
    return definitions.meaning_languages(mode, native if native in LANGUAGES else "en", body.language)
