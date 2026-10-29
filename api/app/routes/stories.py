from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from tutor_core import prompts

from ..db import connection
from ..deps import current_user, require_language
from ..errors import not_found
from ..schemas import GeneratedStoryOut, GenerateIn, SaveIn, StoryFull, StoryOptionsOut, StoryPage
from ..services import stories, story_generation
from ..services.ai_runner import AiRunner, OwnModels, ai_runner_for, own_models_for

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("/options", response_model=StoryOptionsOut)
def options(_: dict = Depends(current_user)):
    return {"types": list(prompts.ALL_STORY_TYPES), "topics": list(prompts.TOPICS)}


@router.post("/generate", response_model=GeneratedStoryOut)
def generate(body: GenerateIn, request: Request, user: dict = Depends(current_user), runner: AiRunner = Depends(ai_runner_for)):
    """Makes one story from THIS learner's words and checks it. Nothing is saved; the learner saves it from the page."""
    require_language(body.language)
    return story_generation.generate(request.app.state.pool, user["id"], body, runner)


@router.post("", status_code=201, response_model=StoryFull)
def save(body: SaveIn, request: Request, user: dict = Depends(current_user), own_models: OwnModels = Depends(own_models_for)):
    """Saves a story to the library (the report is made on the server)."""
    require_language(body.language)
    return story_generation.save(request.app.state.pool, user["id"], body, own_models)


@router.get("", response_model=StoryPage)
def list_stories(request: Request, language: str | None = None, limit: int = Query(20, ge=1, le=100),
                 offset: int = Query(0, ge=0), user: dict = Depends(current_user)):
    if language is not None:
        require_language(language)
    with connection(request.app.state.pool) as conn:
        return stories.list_for_user(conn, user["id"], language, limit, offset)


@router.get("/{story_id}", response_model=StoryFull)
def open_story(story_id: int, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        story = stories.get(conn, user["id"], story_id)
    if not story:
        raise not_found("That story isn't in your library.")
    return story


@router.delete("/{story_id}", status_code=204)
def delete_story(story_id: int, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        if not stories.delete(conn, user["id"], story_id):
            raise not_found("That story isn't in your library.")
    return Response(status_code=204)
