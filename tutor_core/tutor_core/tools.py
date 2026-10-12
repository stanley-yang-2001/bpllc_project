"""What the Langflow tools do with their inputs (M3, commit 2 of 2). The components are thin wrappers over these functions.

FAIL CLOSED (design 3D). The API sets two hidden inputs per request through Langflow tweaks: `learner_id` (a string) and
`active_language`. The model never sees them and cannot change them. If `learner_id` is missing or malformed, a tool
returns a plain message and touches no data; it never falls back to a shared list. The single exception is a developer
convenience: when TUTOR_DEV_USER_ID is set in the Langflow container's environment, a request that sends NO learner id
at all acts as that developer account (so the Playground and the routing runner work). A learner id that is sent but
malformed is always refused, dev variable or not. The production compose file does not set the variable.

Learner-facing text never carries connection details: unexpected errors are logged and reduced to their type.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from . import db, vocab
from .languages import LANGUAGES, normalize_language
from .story import FAILURE_FALLBACK_MESSAGE, generate_story
from .words import WordError

log = logging.getLogger("tutor_core.tools")

DEV_USER_ENV = "TUTOR_DEV_USER_ID"
DEV_LANGUAGE_ENV = "TUTOR_DEV_LANGUAGE"

NO_LEARNER_ADD = "Couldn't add word: I don't know whose vocabulary this is."
NO_LANGUAGE_ADD = "Couldn't add word: I don't know which language this vocabulary is for."
NO_LEARNER_STORY = "I can't write a story right now: I don't know whose vocabulary to use."
NO_LANGUAGE_STORY = "I can't write a story right now: I don't know which language to use."
NO_LEARNER_LIST = "I don't know whose vocabulary this is, so I can't show it."

_DIGITS = re.compile(r"[0-9]{1,9}")         # ASCII digits only: str.isdigit() also accepts "٣" and "１７"


def _env(env):
    return os.environ if env is None else env


def _dev_learner(env) -> Optional[int]:
    text = (_env(env).get(DEV_USER_ENV) or "").strip()
    if _DIGITS.fullmatch(text) and int(text) > 0:
        return int(text)
    return None


def resolve_learner(raw, env=None) -> Optional[int]:
    """The learner id as an int, or None (= nobody: refuse). Accepts the string Langflow delivers; anything else that was
    actually sent is refused. Only a request that sent nothing may use the developer fallback."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return _dev_learner(env)
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        return None
    text = str(raw).strip()
    if _DIGITS.fullmatch(text) and int(text) > 0:
        return int(text)
    return None


def resolve_language(raw, env=None) -> Optional[str]:
    """An ISO code from a code or a name ('es', 'Spanish', 'español'), or None. Blank means the developer default, and only
    when the developer fallback is on; a language that was sent but is unknown is always refused."""
    text = " ".join(str(raw or "").split())
    if not text:
        if _dev_learner(env) is None:
            return None
        return normalize_language(_env(env).get(DEV_LANGUAGE_ENV) or "en")
    return normalize_language(text)


def _open(connect, env):
    return (connect or (lambda: db.connect(env)))()


def add_word_for_agent(word, learner_id, active_language, *, connect=None, env=None) -> str:
    learner = resolve_learner(learner_id, env)
    if learner is None:
        return NO_LEARNER_ADD
    language = resolve_language(active_language, env)
    if language is None:
        return NO_LANGUAGE_ADD
    name = LANGUAGES[language].name
    try:
        conn = _open(connect, env)
        try:
            result = vocab.add_word(conn, learner, language, word)
        finally:
            conn.close()
    except (WordError, vocab.VocabError) as e:
        return f"Couldn't add word: {e}"
    except Exception as e:  # noqa: BLE001 - the learner gets the type only; the detail goes to the log
        log.exception("add word failed")
        return f"Add word failed: {type(e).__name__}"
    if result.added:
        return f"Added '{result.word}' to your {name} vocabulary."
    return f"'{result.word}' is already in your {name} vocabulary."


def story_for_agent(language, learner_id, active_language, *, connect=None, env=None, call_groq_fn=None) -> str:
    """`language` is what the Agent passed (the learner may say "a story in French" while Spanish is active); blank means the
    hidden active language."""
    learner = resolve_learner(learner_id, env)
    if learner is None:
        return NO_LEARNER_STORY
    named = " ".join(str(language or "").split())
    if named:
        code = normalize_language(named)
        if code is None:
            return f"Stories in {named} are not available yet."
    else:
        code = resolve_language(active_language, env)
        if code is None:
            return NO_LANGUAGE_STORY
    try:                                    # generate_story itself declines a language whose story quality is not measured
        conn = _open(connect, env)
        try:
            return generate_story(conn, learner, code, call_groq_fn=call_groq_fn).text
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        log.exception("story failed")
        return FAILURE_FALLBACK_MESSAGE


def vocabulary_for_agent(learner_id, active_language, *, connect=None, env=None) -> str:
    """The Word Loader component (kept on the canvas for debugging): one learner's words, comma-separated."""
    learner = resolve_learner(learner_id, env)
    if learner is None:
        return NO_LEARNER_LIST
    language = resolve_language(active_language, env)
    if language is None:
        return "I don't know which language this vocabulary is for."
    conn = _open(connect, env)
    try:
        return ", ".join(vocab.load_words(conn, learner, language))
    finally:
        conn.close()
