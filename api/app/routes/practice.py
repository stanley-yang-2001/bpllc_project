from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..db import connection
from ..deps import current_user, require_language
from ..errors import AppError, not_found
from ..schemas import ChoiceSet, ClozeSet, FlashcardSet
from ..services import practice, stories
from tutor_core.languages import LANGUAGES

router = APIRouter(prefix="/practice", tags=["practice"])
MAX_ITEMS = practice.MAX_ITEMS


@router.get("/flashcards", response_model=FlashcardSet)
def flashcards(request: Request, language: str, limit: int = Query(20, ge=1, le=50), set: str | None = Query(None, max_length=12),
               user: dict = Depends(current_user)):
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return practice.flashcards(conn, user["id"], language, limit, set)


@router.get("/choices", response_model=ChoiceSet)
def choices(request: Request, language: str, limit: int = Query(10, ge=1, le=50), direction: str = Query("meaning", max_length=10),
            set: str | None = Query(None, max_length=12), user: dict = Depends(current_user)):
    """Multiple-choice cards from this learner's own words that have a meaning (nothing stored, no AI)."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return practice.choice_cards(conn, user["id"], language, limit, direction, set)


@router.get("/cloze", response_model=ClozeSet)
def cloze(request: Request, story_id: int, user: dict = Depends(current_user)):
    """Fill-in-the-blank items from one of THIS learner's saved stories, blanking only words from their own list."""
    with connection(request.app.state.pool) as conn:
        story = stories.get(conn, user["id"], story_id)
        if not story:
            raise not_found("That story isn't in your library.")
        language = story["language"]
        if not practice.can_cloze(language):
            raise AppError("language_unavailable", f"Fill-in-the-blank isn't available for {LANGUAGES[language].name} yet.", 422)
        items = practice.make_cloze(story["body"], language, practice._vocabulary(conn, user["id"], language))
    if not items:
        raise AppError("no_blanks", "This story has no words from your list to practise. Try another story.", 422)
    return {"story_id": story_id, "language": language, "items": items}
