"""Meanings written by the model for the learner's own words (the HTTP side only; the rules are in services/meanings.py). The learner
asks for it (a checkbox when adding a word, a button on the vocabulary page for every word that has none)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from tutor_core import definitions
from tutor_core.languages import LANGUAGES

from ..deps import current_user, require_language
from ..errors import validation_error
from ..services import meanings
from ..services.ai_runner import AiRunner, ai_runner_for

router = APIRouter(prefix="/words", tags=["words"])


class DefineBody(BaseModel):
    language: str
    ids: list[int] | None = Field(default=None, max_length=definitions.MAX_BATCH)   # these words; none = the next words with no meaning
    set: str | None = Field(default=None, max_length=12)                            # with no ids: all, general or one set
    meaning_language: str = "en"                                                    # the language the meanings are written in


@router.post("/define")
def define(body: DefineBody, request: Request, user: dict = Depends(current_user), runner: AiRunner = Depends(ai_runner_for)):
    """Writes meanings for up to 25 of the learner's words that have none and says how many are still without one."""
    require_language(body.language)
    if body.meaning_language not in LANGUAGES:
        raise validation_error("Choose one of the site languages for the meanings.")
    return meanings.write_missing(request.app.state.pool, runner, user["id"], body.language, body.ids, body.set, body.meaning_language)
