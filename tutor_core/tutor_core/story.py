"""The story pipeline, per learner (M3, commit 2 of 2).

    load THIS learner's words in THIS language  ->  guard against an empty list  ->  cap the list for the prompt
    ->  build the prompt  ->  call Groq  ->  return only the passage, plus which type and topic were used.

The short-lived cache exists only because the top-level Agent has been seen calling the story tool 3 to 5 times for
one request. It is keyed by (learner, language, type, topic): the earlier language-only key would have served one
learner's story, built from their words, to another learner. Successes and failures are cached for different times: a
success is reusable for a while, a failure only briefly, so repeated Agent calls during a rate limit do not each re-run
the retry loop but a genuine retry a bit later still gets a real attempt. Callers that must produce a NEW story every
time (the Story Studio "Regenerate" button) pass use_cache=False and never read or write the cache.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from typing import Optional

from . import groq as groq_module
from .languages import LANGUAGES, stories_enabled
from .quality import language_check
from .prompts import (EMPTY_VOCABULARY_MESSAGE, build_story_prompt, clean_topic, describe_prompt, extract_final_passage,
                      resolve_story_type)
from .vocab import _check, load_words, max_prompt_words, sample_words

_STORY_CACHE: dict = {}
_SUCCESS_CACHE_TTL_SECONDS = 20
_FAILURE_CACHE_TTL_SECONDS = 15

FAILURE_FALLBACK_MESSAGE = (
    "I'm having trouble generating a story right now — please try again in a moment."
)
BAD_TYPE_MESSAGE = (
    "I can't write that kind of text. Try a story, a dialogue, a diary entry, a letter, a place, a daily routine or a "
    "funny anecdote, or name a short kind of text in plain words."
)

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoryResult:
    text: str                       # the passage, or the fixed message for the two non-success cases
    ok: bool
    reason: Optional[str]           # None | "empty_vocabulary" | "failed" | "language_not_enabled" | "bad_type"
    language: str                   # ISO 639-1 code
    story_type: Optional[str] = None
    topic: Optional[str] = None     # only the newer story types have one
    cached: bool = False
    words_total: int = 0            # the learner's full list (the quality check uses this one)
    words_used: int = 0             # what went into the prompt after the cap
    difficulty: Optional[dict] = None   # the targets asked for (tutor_core.difficulty.resolve), or None


def generate_story(
    conn,
    learner_id: int,
    language: str,
    *,
    call_groq_fn=None,
    use_cache: bool = True,
    story_type: Optional[str] = None,
    topic: Optional[str] = None,
    max_words: Optional[int] = None,
    difficulty: Optional[dict] = None,
    rng=None,
    clock=time.time,
) -> StoryResult:
    """`language` is an ISO code. Raises VocabError for a malformed learner or language (a caller bug, not a story
    failure); every story failure comes back as a StoryResult with ok=False.

    `story_type` may be a built-in type, an alias ("conversation"), a short custom label of the learner's own, or
    blank / "random" for the weighted random choice; one that cannot be used comes back as reason "bad_type" and never
    reaches the prompt. `topic` may be one from the built-in list or a short free-text subject; a topic that cannot be
    used is dropped (a random one is chosen) rather than failing the story."""
    _check(learner_id, language)
    if not stories_enabled(language):       # a measured flag (design 3C), checked before anything else is touched
        return StoryResult(f"Stories in {LANGUAGES[language].name} are not available yet.", False, "language_not_enabled", language)
    if story_type is not None and str(story_type).strip().casefold() not in ("", "random"):
        story_type = resolve_story_type(story_type)
        if story_type is None:
            return StoryResult(BAD_TYPE_MESSAGE, False, "bad_type", language)
    else:
        story_type = None
    topic = clean_topic(topic) if topic else None
    key = (learner_id, language, story_type or "", topic or "") + ((tuple(sorted(difficulty.items())),) if difficulty else ())
    now = clock()

    if use_cache and key in _STORY_CACHE:
        stamp, cached = _STORY_CACHE[key]
        if now - stamp < (_SUCCESS_CACHE_TTL_SECONDS if cached.ok else _FAILURE_CACHE_TTL_SECONDS):
            return replace(cached, cached=True)

    words = load_words(conn, learner_id, language)
    if not words:
        return StoryResult(EMPTY_VOCABULARY_MESSAGE, False, "empty_vocabulary", language)

    used = sample_words(words, max_words if max_words is not None else max_prompt_words(), rng)
    # A learner's list is stored per language, so for any language but English the words are already in the target
    # language; the prompt says so instead of asking the model to translate English meanings.
    prompt = build_story_prompt(LANGUAGES[language].name, ", ".join(used), story_type, topic, rng, vocab_in_target=True, difficulty=difficulty)
    picked_type, picked_topic = describe_prompt(prompt)
    base = dict(language=language, story_type=picked_type, topic=picked_topic,
                words_total=len(words), words_used=len(used), difficulty=difficulty)

    def remember(result: StoryResult) -> StoryResult:
        if use_cache:
            _STORY_CACHE[key] = (now, result)
        return result

    try:
        raw = (call_groq_fn or groq_module.call_groq)(prompt)
    except Exception as exc:
        _log.warning("story generation failed (%s): %s", language, exc)
        return remember(StoryResult(FAILURE_FALLBACK_MESSAGE, False, "failed", **base))

    passage = extract_final_passage(raw)
    # An empty passage (the model ran out of tokens, or returned nothing after the delimiter) must never reach the Agent
    # as an empty string: the Agent fills the gap by inventing its own story. It is a failure, cached briefly.
    if not passage.strip():
        _log.warning("story generation returned no passage (%s); raw length %d", language, len(raw or ""))
        return remember(StoryResult(FAILURE_FALLBACK_MESSAGE, False, "failed", **base))
    # The model sometimes answers in English (or mixes English in) when asked for another language (seen 23 Oct, Chinese).
    # Ask once more before the learner ever sees it; whatever the second try gives is returned and reported honestly.
    if language != "en" and language_check(passage, LANGUAGES[language].name, "")["verdict"] not in ("ok", "not_checked"):
        try:
            second = extract_final_passage((call_groq_fn or groq_module.call_groq)(prompt))
        except Exception:
            second = ""
        if second.strip():
            passage = second
    return remember(StoryResult(passage, True, None, **base))
