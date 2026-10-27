from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field, BaseModel, field_validator, model_validator
from tutor_core import difficulty, prompts, quality
from tutor_core.languages import LANGUAGES, stories_enabled
from tutor_core.story import generate_story
from tutor_core.vocab import load_words

from ..db import connection
from ..deps import current_user, require_language
from ..errors import AppError, not_found
from ..schemas import GeneratedStoryOut, StoryFull, StoryOptionsOut, StoryPage
from ..services import stories
from ..services.ai_runner import AiRunner, OwnModels, ai_runner_for, own_models_for

router = APIRouter(prefix="/stories", tags=["stories"])
MIN_WORDS = 5
# Reserved from the token budget before Groq is called. A story prompt holds up to 150 words and the model answers with
# a short plan plus a story, so a typical call is well under this; it is a ceiling, not a measurement. Watch real use
# (docs/WEB-APP-DESIGN.md, M6) and lower it if the budget is being held back too much.
STORY_TOKENS = 2000
MAX_BODY = 8000          # characters; a generated story is a few hundred
MAX_STORIES = 500        # per learner
CLASSIC_TYPES = tuple(prompts.VALID_STYLES)      # narration and dialogue have no topic


class DifficultyIn(BaseModel):
    """The learner's difficulty choice: nothing (any), a preset, or custom with their own numbers (tutor_core.difficulty)."""
    difficulty: str | None = None
    length: int | None = None
    own_words: int | None = None
    uncommon_pct: int | None = None

    @model_validator(mode="after")
    def _difficulty(self):
        self.targets           # raises ValueError (shown to the learner as a 422) for anything not allowed
        return self

    @property
    def targets(self):
        return difficulty.resolve(self.difficulty, self.length, self.own_words, self.uncommon_pct)


class GenerateIn(DifficultyIn):
    language: str
    set_ids: list[int] | None = Field(default=None, max_length=100)     # the sets to use (0 = General); none = all of the learner's words
    story_type: str | None = None
    topic: str | None = None

    @field_validator("story_type")
    @classmethod
    def _type(cls, value):
        """A built-in type, an alias ("conversation"), or the learner's own short label ("a poem"). The result is the
        canonical built-in name or the cleaned label; text that cannot be used never gets as far as the prompt."""
        if value is None:
            return None
        resolved = prompts.resolve_story_type(value)
        if resolved is None:
            raise ValueError("Pick one of the listed kinds, or write a short one of your own: up to 40 characters and 6 words, "
                             "with letters, numbers, spaces, apostrophes and hyphens only.")
        return resolved

    @field_validator("topic")
    @classmethod
    def _topic(cls, value):
        """A topic from the list, or the learner's own short one ("my grandma's kitchen"): the same rule and limits as a
        custom kind. Text that cannot be used never gets as far as the prompt, where it is quoted as a subject."""
        if value is None:
            return None
        resolved = prompts.clean_topic(value)
        if resolved is None:
            raise ValueError("Pick a topic from the list, or write a short one of your own: up to 40 characters and 6 words, "
                             "with letters, numbers, spaces, apostrophes and hyphens only.")
        return resolved


@router.get("/options", response_model=StoryOptionsOut)
def options(_: dict = Depends(current_user)):
    return {"types": list(prompts.ALL_STORY_TYPES), "topics": list(prompts.TOPICS)}


@router.post("/generate", response_model=GeneratedStoryOut)
def generate(body: GenerateIn, request: Request, user: dict = Depends(current_user), runner: AiRunner = Depends(ai_runner_for)):
    """Makes one story from THIS learner's words and checks it. Nothing is saved; the learner saves it from the page."""
    require_language(body.language)
    lang = LANGUAGES[body.language]
    if not stories_enabled(body.language):
        raise AppError("language_unavailable", f"Stories in {lang.name} are not available yet.", 422)
    if body.set_ids is not None and any(i < 0 for i in body.set_ids):
        raise AppError("validation_error", "Choose the sets from your list.", 422)
    state = request.app.state
    with connection(state.pool) as conn:
        words = load_words(conn, user["id"], body.language, body.set_ids)
    if len(words) < MIN_WORDS:
        chosen = "" if body.set_ids is None else " in the sets you chose"
        raise AppError("not_enough_words", f"Add at least {MIN_WORDS} {lang.name} words{chosen} before making a story.", 422)
    chosen = runner.choose(user["id"])        # the learner's own model if they set one up (no shared token budget, a request limit), else the shared one
    with runner.slot(user["id"], chosen, STORY_TOKENS):
        with connection(state.pool) as conn:
            result = generate_story(conn, user["id"], body.language, use_cache=False, story_type=body.story_type,
                                    topic=body.topic, difficulty=body.targets, set_ids=body.set_ids, call_groq_fn=chosen.call)
    if not result.ok:       # a failure of the learner's own model is shown as it is, with a way back to the shared one; never a silent fallback
        raise runner.failure(chosen, "The story writer didn't answer. Please try again in a moment.",
                             own_hint="You can switch back to the shared model in Settings, under My model, by removing your model.")
    report = quality.report(result.text, body.language, words, body.targets)      # the learner's WHOLE list, not the prompt's sample
    if chosen.own_model:
        report["model"] = {"custom": True, "name": chosen.own_model}
    return {"story": result.text, "language": body.language, "story_type": result.story_type, "topic": result.topic,
            "report": report, "words_total": result.words_total, "words_used": result.words_used}


class SaveIn(DifficultyIn):
    language: str
    body: str
    story_type: str | None = None
    topic: str | None = None
    model: str | None = Field(default=None, max_length=120)      # the model name the page showed; used only if it is the learner's own, see save()

    @field_validator("body")
    @classmethod
    def _body(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("The story is empty.")
        if len(value) > MAX_BODY:
            raise ValueError(f"Keep stories under {MAX_BODY} characters.")
        return value

    _type = field_validator("story_type")(GenerateIn._type.__func__)
    _topic = field_validator("topic")(GenerateIn._topic.__func__)


@router.post("", status_code=201, response_model=StoryFull)
def save(body: SaveIn, request: Request, user: dict = Depends(current_user), own_models: OwnModels = Depends(own_models_for)):
    """Saves a story to the library. The report is made here, from the learner's own words; a report or a pass sent by the
    page is never read (it is not even a field)."""
    require_language(body.language)
    topic = None if body.story_type in CLASSIC_TYPES else body.topic
    with connection(request.app.state.pool) as conn:
        if stories.list_for_user(conn, user["id"], None, 1, 0)["total"] >= MAX_STORIES:
            raise AppError("library_full", f"Your library holds {MAX_STORIES} stories. Delete some to save more.", 422)
        words = load_words(conn, user["id"], body.language)
        report = quality.report(body.body, body.language, words, body.targets)
        own = own_models.find(user["id"], conn) if body.model else None
        if own and own["model"] == body.model:
            report["model"] = {"custom": True, "name": own["model"]}      # remembered with the story; a name that is not the learner's own is ignored
        return stories.create(conn, user["id"], body.language, body.story_type, topic, body.body, report)


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
