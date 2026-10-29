from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..db import connection
from ..deps import current_user, require_language
from ..errors import AppError, not_found
from ..schemas import AnswersIn, ChoiceSet, ClozeSet, FlashcardSet, ProgressOut
from ..services import practice, progress, stories
from tutor_core.languages import LANGUAGES

router = APIRouter(prefix="/practice", tags=["practice"])
MAX_ITEMS = practice.MAX_ITEMS


@router.get("/flashcards", response_model=FlashcardSet)
def flashcards(request: Request, language: str, limit: int = Query(20, ge=1, le=50), set: str | None = Query(None, max_length=12),
               due: bool = False, user: dict = Depends(current_user)):
    """due=true: only the words that are due now, then words never practised."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return practice.flashcards(conn, user["id"], language, limit, set, due)


@router.get("/choices", response_model=ChoiceSet)
def choices(request: Request, language: str, limit: int = Query(10, ge=1, le=50), direction: str = Query("meaning", max_length=10),
            set: str | None = Query(None, max_length=12), due: bool = False, user: dict = Depends(current_user)):
    """Multiple-choice cards from this learner's own words that have a meaning (made on the spot, no AI)."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return practice.choice_cards(conn, user["id"], language, limit, direction, set, due=due)


@router.post("/answers", status_code=204)
def record_answers(body: AnswersIn, request: Request, user: dict = Depends(current_user)):
    """Remember which words the learner got right or wrong, so the due ones come back (spaced repetition)."""
    with connection(request.app.state.pool) as conn:
        progress.record(conn, user["id"], [(a.word_id, a.correct) for a in body.answers])


@router.get("/progress", response_model=ProgressOut)
def get_progress(request: Request, language: str, user: dict = Depends(current_user)):
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return progress.summary(conn, user["id"], language)


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
        items = practice.make_cloze(story["body"], language, practice._vocabulary(conn, user["id"], language),
                                    ids=practice._word_ids(conn, user["id"], language))
    if not items:
        raise AppError("no_blanks", "This story has no words from your list to practise. Try another story.", 422)
    return {"story_id": story_id, "language": language, "items": items}
