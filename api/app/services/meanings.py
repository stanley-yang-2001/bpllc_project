"""Use case: the model writes meanings for words that have none. A meaning the learner wrote is never replaced."""
from __future__ import annotations

from tutor_core import definitions
from tutor_core.languages import LANGUAGES

from ..db import connection
from . import vocab
from .ai_runner import AiRunner

DEFINE_TOKENS = 1500           # reserved from the shared per-minute budget for one batch of up to 25 words


def _stub(prompt: str) -> str:
    lines = prompt.split("Entries:\n", 1)[1].strip().splitlines()
    return "\n".join(f"{w} | (stub) meaning of {w}" for w in lines)


def write_missing(pool, runner: AiRunner, user_id: int, language: str, ids: list[int] | None, set_filter: str | None,
                  meaning_languages: list[str]) -> dict:
    """One batch (at most 25 words) and how many words are still without a meaning, so the page can ask again until it is 0."""
    with connection(pool) as conn:
        todo = vocab.words_without_meaning(conn, user_id, language, ids, set_filter, definitions.MAX_BATCH)
    if not todo["items"]:
        return {"defined": 0, "failed": 0, "remaining": todo["remaining"]}
    words = [w["word"] for w in todo["items"]]
    prompt = definitions.build_prompt(words, LANGUAGES[language].name, [LANGUAGES[c].name for c in meaning_languages])
    raw = runner.run(user_id, prompt, tokens=DEFINE_TOKENS, stub=_stub,
                     failed_message="The tutor couldn't write the meanings. Please try again in a moment.")
    meanings = definitions.parse(raw, words)
    with connection(pool) as conn:
        defined = vocab.fill_meanings(conn, user_id, [(w["id"], meanings[w["word"]]) for w in todo["items"] if w["word"] in meanings])
        remaining = vocab.words_without_meaning(conn, user_id, language, ids, set_filter, 1)["remaining"]
    return {"defined": defined, "failed": len(words) - defined, "remaining": remaining}
