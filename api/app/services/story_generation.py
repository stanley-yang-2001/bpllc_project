"""Making and saving a story: the use case behind routes/stories.py, with no HTTP in it (the route checks the request and answers)."""
from __future__ import annotations

from tutor_core import prompts, quality
from tutor_core.languages import LANGUAGES, stories_enabled
from tutor_core.story import generate_story
from tutor_core.vocab import load_words

from ..db import connection
from ..errors import AppError
from ..schemas import GenerateIn, SaveIn
from . import stories
from .ai_runner import AiRunner, OwnModels

MIN_WORDS = 5
# Reserved from the token budget before Groq is called. A story prompt holds up to 150 words and the model answers with
# a short plan plus a story, so a typical call is well under this; it is a ceiling, not a measurement. Watch real use
# (docs/WEB-APP-DESIGN.md, M6) and lower it if the budget is being held back too much.
STORY_TOKENS = 2000
MAX_STORIES = 500        # per learner
CLASSIC_TYPES = tuple(prompts.VALID_STYLES)      # narration and dialogue have no topic


def generate(pool, user_id: int, body: GenerateIn, runner: AiRunner) -> dict:
    """Makes one story from THIS learner's words and checks it. Nothing is saved; the learner saves it from the page."""
    lang = LANGUAGES[body.language]
    if not stories_enabled(body.language):
        raise AppError("language_unavailable", f"Stories in {lang.name} are not available yet.", 422)
    if body.set_ids is not None and any(i < 0 for i in body.set_ids):
        raise AppError("validation_error", "Choose the sets from your list.", 422)
    with connection(pool) as conn:
        words = load_words(conn, user_id, body.language, body.set_ids)
    if len(words) < MIN_WORDS:
        chosen = "" if body.set_ids is None else " in the sets you chose"
        raise AppError("not_enough_words", f"Add at least {MIN_WORDS} {lang.name} words{chosen} before making a story.", 422)
    chosen = runner.choose(user_id)        # the learner's own model if they set one up (no shared token budget, a request limit), else the shared one
    with runner.slot(user_id, chosen, STORY_TOKENS):
        with connection(pool) as conn:
            result = generate_story(conn, user_id, body.language, use_cache=False, story_type=body.story_type,
                                    topic=body.topic, difficulty=body.targets, set_ids=body.set_ids, call_groq_fn=chosen.call)
    if not result.ok:       # a failure of the learner's own model is shown as it is, with a way back to the shared one; never a silent fallback
        raise runner.failure(chosen, "The story writer didn't answer. Please try again in a moment.",
                             own_hint="You can switch back to the shared model in Settings, under My model, by removing your model.")
    report = quality.report(result.text, body.language, words, body.targets)      # the learner's WHOLE list, not the prompt's sample
    if chosen.own_model:
        report["model"] = {"custom": True, "name": chosen.own_model}
    return {"story": result.text, "language": body.language, "story_type": result.story_type, "topic": result.topic,
            "report": report, "words_total": result.words_total, "words_used": result.words_used}


def save(pool, user_id: int, body: SaveIn, own_models: OwnModels) -> dict:
    """Saves a story to the library. The report is made here, from the learner's own words; a report or a pass sent by the
    page is never read (it is not even a field)."""
    topic = None if body.story_type in CLASSIC_TYPES else body.topic
    with connection(pool) as conn:
        if stories.list_for_user(conn, user_id, None, 1, 0)["total"] >= MAX_STORIES:
            raise AppError("library_full", f"Your library holds {MAX_STORIES} stories. Delete some to save more.", 422)
        words = load_words(conn, user_id, body.language)
        report = quality.report(body.body, body.language, words, body.targets)
        own = own_models.find(user_id, conn) if body.model else None
        if own and own["model"] == body.model:
            report["model"] = {"custom": True, "name": own["model"]}      # remembered with the story; a name that is not the learner's own is ignored
        return stories.create(conn, user_id, body.language, body.story_type, topic, body.body, report)
