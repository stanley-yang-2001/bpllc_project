from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..db import connection
from ..deps import current_user, require_language
from ..errors import AppError, not_found
from ..schemas import AnswersIn, ChoiceSet, ClozeSet, DictationSet, FlashcardSet, HardWords, PosSet, ProgressOut, ReviewResults, ReviewsIn, StudyStats
from ..services import practice, progress, stories, study_stats
from tutor_core.languages import LANGUAGES

router = APIRouter(prefix="/practice", tags=["practice"])
MAX_ITEMS = practice.MAX_ITEMS


SET_QUERY = Query(None, max_length=200, description="all, general, a set id, or a comma list of them (3,7,general)")


@router.get("/flashcards", response_model=FlashcardSet)
def flashcards(request: Request, language: str, limit: int | None = Query(None, ge=1, le=2000), set: str | None = SET_QUERY,
               due: bool = False, scope: str | None = Query(None, max_length=8), ids: str | None = Query(None, max_length=1500),
               user: dict = Depends(current_user)):
    """The cards of the chosen sets with no size limit (limit is optional). scope=all: every word, shuffled; scope=due (or due=true):
    what the schedule asks for now; scope=ids&ids=1,2,3: exactly those words. Each card carries what every answer would schedule."""
    require_language(language)
    try:
        word_ids = [int(i) for i in ids.split(",")] if ids else None
    except ValueError:
        raise AppError("validation_error", "ids must be word numbers separated by commas.", 422)
    with connection(request.app.state.pool) as conn:
        return practice.flashcards(conn, user["id"], language, limit, set, due, scope, word_ids)


@router.get("/choices", response_model=ChoiceSet)
def choices(request: Request, language: str, limit: int = Query(10, ge=1, le=50), direction: str = Query("meaning", max_length=10),
            set: str | None = SET_QUERY, due: bool = False, user: dict = Depends(current_user)):
    """Multiple-choice cards from this learner's own words that have a meaning (made on the spot, no AI)."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return practice.choice_cards(conn, user["id"], language, limit, direction, set, due=due)


@router.get("/dictation", response_model=DictationSet)
def dictation(request: Request, language: str, limit: int = Query(10, ge=1, le=50), set: str | None = SET_QUERY,
              due: bool = False, user: dict = Depends(current_user)):
    """Words to hear and type. The browser reads them aloud, so the server only picks them (any word, a meaning is not needed)."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return practice.dictation(conn, user["id"], language, limit, set, due)


@router.get("/pos", response_model=PosSet)
def pos_practice(request: Request, language: str, limit: int = Query(10, ge=1, le=50), set: str | None = SET_QUERY,
                 due: bool = False, user: dict = Depends(current_user)):
    """Which part of speech is this word? From the learner's own labelled words (made on the spot, no AI)."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return practice.pos_cards(conn, user["id"], language, limit, set, due)


@router.post("/answers", status_code=204)
def record_answers(body: AnswersIn, request: Request, user: dict = Depends(current_user)):
    """Right/wrong answers from the modes without grade buttons: right counts as Good, wrong as Again (with how long it took)."""
    with connection(request.app.state.pool) as conn:
        progress.record_reviews(conn, user["id"], [progress.Review(a.word_id, 3 if a.correct else 1, think_ms=a.think_ms, mode=a.mode, direction=a.direction)
                                                   for a in body.answers])


@router.post("/reviews", response_model=ReviewResults)
def record_reviews(body: ReviewsIn, request: Request, user: dict = Depends(current_user)):
    """Graded flashcard answers (1 again, 2 hard, 3 good, 4 easy) with how long the learner took. Returns when each word is due again."""
    with connection(request.app.state.pool) as conn:
        results = progress.record_reviews(conn, user["id"], [progress.Review(r.word_id, r.grade, r.think_ms, r.rate_ms, r.mode, r.direction)
                                                              for r in body.reviews])
    return {"results": results}


@router.get("/stats", response_model=StudyStats)
def stats(request: Request, language: str, set: str | None = SET_QUERY, user: dict = Depends(current_user)):
    """How the chosen words stand and how the last 30 days of answers went (retention, time taken, forecast)."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return study_stats.stats(conn, user["id"], language, set)


@router.get("/hardest", response_model=HardWords)
def hardest(request: Request, language: str, set: str | None = SET_QUERY, limit: int = Query(10, ge=1, le=50), user: dict = Depends(current_user)):
    """The words this learner finds hardest, from their own answers (misses, time taken, lapses)."""
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return study_stats.hardest(conn, user["id"], language, set, limit)


@router.get("/progress", response_model=ProgressOut)
def get_progress(request: Request, language: str, set: str | None = SET_QUERY, user: dict = Depends(current_user)):
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return progress.summary(conn, user["id"], language, set)


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
        items = practice.make_cloze(story["body"], language, practice.vocabulary_of(conn, user["id"], language),
                                    ids=practice.word_ids_of(conn, user["id"], language))
    if not items:
        raise AppError("no_blanks", "This story has no words from your list to practise. Try another story.", 422)
    return {"story_id": story_id, "language": language, "items": items}
