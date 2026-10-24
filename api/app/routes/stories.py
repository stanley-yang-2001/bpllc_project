from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, field_validator, model_validator
from tutor_core import difficulty, prompts, quality
from tutor_core.languages import LANGUAGES, stories_enabled
from tutor_core.story import generate_story
from tutor_core.vocab import load_words

from ..db import connection
from ..deps import current_user, require_language
from ..errors import AppError, not_found
from ..schemas import GeneratedStoryOut, StoryFull, StoryOptionsOut, StoryPage
from ..services import model_secrets, stories, user_models
from ..services.user_model import make_call_fn

router = APIRouter(prefix="/stories", tags=["stories"])
MIN_WORDS = 5
# Reserved from the token budget before Groq is called. A story prompt holds up to 150 words and the model answers with
# a short plan plus a story, so a typical call is well under this; it is a ceiling, not a measurement. Watch real use
# (docs/WEB-APP-DESIGN.md, M6) and lower it if the budget is being held back too much.
STORY_TOKENS = 2000
MAX_BODY = 8000          # characters; a generated story is a few hundred
MAX_STORIES = 500        # per learner
CLASSIC_TYPES = tuple(prompts.VALID_STYLES)      # narration and dialogue have no topic


def _own_model(state, conn, user_id: int):
    """The learner's saved model with its key decrypted, or None when it is not switched on or not set up."""
    s = state.settings
    if not s.model_key_secret or not user_models.enabled(conn, user_id):
        return None
    row = user_models.get(conn, user_id)
    if not row:
        return None
    return {"model": row["model"], "base_url": row["base_url"], "key": model_secrets.decrypt(s.model_key_secret, row["api_key_encrypted"])}


def _last_model_error(call) -> str:
    return getattr(call, "last_error", "") or "no answer."


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
def generate(body: GenerateIn, request: Request, user: dict = Depends(current_user)):
    """Makes one story from THIS learner's words and checks it. Nothing is saved; the learner saves it from the page."""
    require_language(body.language)
    lang = LANGUAGES[body.language]
    if not stories_enabled(body.language):
        raise AppError("language_unavailable", f"Stories in {lang.name} are not available yet.", 422)
    state = request.app.state
    with connection(state.pool) as conn:
        words = load_words(conn, user["id"], body.language)
    if len(words) < MIN_WORDS:
        raise AppError("not_enough_words", f"Add at least {MIN_WORDS} {lang.name} words to your list before making a story.", 422)
    llm, own = state.story_llm, None
    with connection(state.pool) as conn:
        own = _own_model(state, conn, user["id"])
    if own:
        # The learner's own model (decision 1 to 6 of docs/CUSTOM-MODEL-DESIGN.md): no shared token budget, a request limit instead,
        # and a failure is shown as it is with a way back to the shared model; never a silent fallback.
        if not state.model_limiter.allow(user["id"]):
            raise AppError("rate_limited", "You are making stories with your own model too quickly. Wait a minute.", 429, retry_after=60)
        llm = make_call_fn(own["model"], own["base_url"], own["key"], state.settings.allow_private_model_urls)
    with state.ai_gate.slot(user["id"], tokens=STORY_TOKENS if getattr(llm, "calls_ai", True) else 0):
        with connection(state.pool) as conn:
            result = generate_story(conn, user["id"], body.language, use_cache=False, story_type=body.story_type,
                                    topic=body.topic, difficulty=body.targets, call_groq_fn=llm)
    if not result.ok:
        if own:
            raise AppError("custom_model_failed", f"Your model ({own['model']}) didn't answer: {_last_model_error(llm)} "
                           "You can switch back to the shared model in Settings, under My model, by removing your model.", 502)
        raise AppError("ai_failed", "The story writer didn't answer. Please try again in a moment.", 502)
    report = quality.report(result.text, body.language, words, body.targets)      # the learner's WHOLE list, not the prompt's sample
    if own:
        report["model"] = {"custom": True, "name": own["model"]}
    return {"story": result.text, "language": body.language, "story_type": result.story_type, "topic": result.topic,
            "report": report, "words_total": result.words_total, "words_used": result.words_used}


class SaveIn(DifficultyIn):
    language: str
    body: str
    story_type: str | None = None
    topic: str | None = None

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
def save(body: SaveIn, request: Request, user: dict = Depends(current_user)):
    """Saves a story to the library. The report is made here, from the learner's own words; a report or a pass sent by the
    page is never read (it is not even a field)."""
    require_language(body.language)
    topic = None if body.story_type in CLASSIC_TYPES else body.topic
    with connection(request.app.state.pool) as conn:
        if stories.list_for_user(conn, user["id"], None, 1, 0)["total"] >= MAX_STORIES:
            raise AppError("library_full", f"Your library holds {MAX_STORIES} stories. Delete some to save more.", 422)
        words = load_words(conn, user["id"], body.language)
        report = quality.report(body.body, body.language, words, body.targets)
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
