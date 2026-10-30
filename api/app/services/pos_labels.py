"""Use case: the model labels words with their part of speech. A label the learner chose is never replaced."""
from __future__ import annotations

from tutor_core import pos
from tutor_core.languages import LANGUAGES

from ..db import connection
from . import vocab
from .ai_runner import AiRunner

LABEL_TOKENS = 1200            # reserved from the shared per-minute budget for one batch of up to 25 words


def _stub(prompt: str) -> str:
    lines = prompt.split("Entries:\n", 1)[1].strip().splitlines()
    return "\n".join(f"{w} | {'phrase' if ' ' in w else 'noun'}" for w in lines)


def label_missing(pool, runner: AiRunner, user_id: int, language: str, ids: list[int] | None, set_filter: str | None) -> dict:
    """One batch (at most 25 words) and how many words are still unlabelled, so the page can ask again until it is 0."""
    with connection(pool) as conn:
        todo = vocab.words_without_pos(conn, user_id, language, ids, set_filter, pos.MAX_BATCH)
    if not todo["items"]:
        return {"defined": 0, "failed": 0, "remaining": todo["remaining"]}
    words = [w["word"] for w in todo["items"]]
    raw = runner.run(user_id, pos.build_prompt(words, language, LANGUAGES[language].name), tokens=LABEL_TOKENS, stub=_stub,
                     failed_message="The tutor couldn't label the words. Please try again in a moment.")
    labels = pos.parse(raw, words, language)
    with connection(pool) as conn:
        done = vocab.fill_pos(conn, user_id, [(w["id"], labels[w["word"]]) for w in todo["items"] if w["word"] in labels])
        remaining = vocab.words_without_pos(conn, user_id, language, ids, set_filter, 1)["remaining"]
    return {"defined": done, "failed": len(words) - done, "remaining": remaining}
