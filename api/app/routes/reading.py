"""The reader: the HTTP side only (the rules are in services/reading.py and tutor_core.story_gloss). No model is called."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..db import connection
from ..deps import current_user, require_language
from ..schemas import GlossIn, GlossOut
from ..services import reading

router = APIRouter(prefix="/reading", tags=["reading"])


@router.post("/gloss", response_model=GlossOut)
def gloss(body: GlossIn, request: Request, user: dict = Depends(current_user)):
    """Where the learner's own words of this language stand in a text, with their meanings, so the page can underline them."""
    require_language(body.language)
    with connection(request.app.state.pool) as conn:
        return reading.gloss(conn, user["id"], body.language, body.text)
