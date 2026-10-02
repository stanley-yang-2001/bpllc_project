"""
Story Generator Tool — consolidated, single-call version of the Step 8 pipeline, built to
be used as ONE tool by the top-level Language Agent (Step 9).

Why this duplicates logic already in word_loader.py, story_guard.py, story_prompt_builder.py,
and final_passage_extractor.py: when a component is used as a Tool by another Agent,
Langflow only returns that component's own output — it does not execute anything wired
downstream of it on the canvas. The Step 8 pipeline is four separate components chained
together, so exposing the Agent alone as a tool would leak the hidden planning summary
straight to the learner, since the Final Passage Extractor (downstream) would never run as
part of the tool call. This module inlines everything into one atomic operation instead.

The standalone Step 8 components remain on the canvas for manual, visual debugging in the
Playground — this file is the production path the top-level Agent actually calls.

generate_story_for_learner() takes an injectable call_groq_fn so it's testable without a
real network call (see tests/test_story_tool.py); call_groq() itself is the real
implementation, using the same request pattern already proven working in scripts/smoke_test.py
(including the User-Agent header, without which Groq's Cloudflare protection blocks the
request with an HTTP 1010).
"""

import json
import random
import time
import urllib.error
import urllib.request
from typing import Optional

import psycopg2
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

DB_CONFIG = dict(
    dbname="langflow",
    user="langflow",
    password="langflow",
    host="postgres",
    port=5432,
)

DELIMITER = "===STORY==="

EMPTY_VOCABULARY_MESSAGE = (
    "You don't have any vocabulary yet! Tell me a word to add, and I'll remember it — "
    "once you've added a few, ask me for a story."
)

NARRATION_TEMPLATE = (
    "You are a creative writer crafting a short, simple reading passage for a "
    "language-learning beginner in {language}.\n\n"
    "First, silently plan (do not show this):\n"
    "- Character: a simple name.\n"
    "- Want: something they want, have, or need — tied to a vocabulary word if possible.\n"
    "- Event: a question, request, or small problem needing a response, following "
    "logically from Want.\n"
    "- Resolution: how it's resolved — vary the shape (agreement, farewell, thanks, or a "
    "plan like \"tomorrow, I will...\"), not just yes/no. This is where yes/no/please/thank "
    "you fit as real reactions, not random insertions.\n"
    "Write a 1-2 sentence summary of these four parts, then the line ===STORY=== alone, "
    "then the passage.\n\n"
    "Passage rules:\n"
    "1. First person, aim for 5 to 6 short sentences (5-10 words each), each following "
    "logically from the last — no unrelated facts.\n"
    "2. Use words that truly fit from: {words}. You don't need to include every one — "
    "only use ones that make sense, never forcing a word that breaks the logical flow. "
    "You may inflect a word's form (verb tense, plural, etc.) as needed for grammar, "
    "keeping the same root word.\n"
    "3. You may add basic grammar words (articles, pronouns, prepositions, conjunctions) "
    "and simple verbs (is, have, want, like, go, see) — but no new content words outside "
    "the list.\n"
    "4. No conditionals, semicolons, or multi-idea sentences. Natural spoken tone, not "
    "formal narration.\n"
    "5. Output ONLY the ===STORY=== line and the passage — no title, no explanation, no "
    "planning notes.\n\n"
    "Tone example only (your own topic must come from your own planned Event, not this "
    "example):\n"
    '"Hello! I am hungry today. I see a small shop with fresh bread. I say thank you and '
    'eat happily."\n\n'
    "Begin: planning, then delimiter, then passage."
)

DIALOGUE_TEMPLATE = (
    "You are a creative writer crafting a short, simple dialogue for a language-learning "
    "beginner in {language}.\n\n"
    "First, silently plan (do not show this):\n"
    "- Characters: two simple, real names.\n"
    "- Want: something one friend wants, has, or needs — tied to a vocabulary word if "
    "possible.\n"
    "- Event: a question, request, or small problem needing a response, following "
    "logically from Want.\n"
    "- Resolution: how the other friend responds — vary the shape (agreement, farewell, "
    "thanks, or a plan like \"tomorrow, we will...\"), not just yes/no. This is where "
    "yes/no/please/thank you fit as real reactions, not random insertions.\n"
    "Write a 1-2 sentence summary of these four parts, then the line ===STORY=== alone, "
    "then the dialogue.\n\n"
    "Dialogue rules:\n"
    "1. Aim for 5 to 6 lines of back-and-forth conversation, each line a real, logical "
    "response to the one before — rewrite any line that doesn't answer the last.\n"
    "2. Use words that truly fit from: {words}. You don't need to include every one — "
    "only use ones that make sense, never forcing a word that breaks the logical flow. "
    "You may inflect a word's form (verb tense, plural, etc.) as needed for grammar, "
    "keeping the same root word.\n"
    "3. You may add basic grammar words (articles, pronouns, prepositions, conjunctions) "
    "and simple verbs (is, have, want, like, go, see) — but no new content words outside "
    "the list.\n"
    "4. Keep each line short (3-8 words). No conditionals, semicolons, or multi-idea "
    "lines.\n"
    "5. Format each line as: Name: line\n"
    "6. Output ONLY the ===STORY=== line and the dialogue — no title, no explanation, no "
    "planning notes.\n\n"
    "Tone example only (your own topic must come from your own planned Event, not this "
    "example):\n"
    "Mia: Hello! Do you have any bread?\n"
    "Leo: Yes, I have some. Do you want it?\n"
    "Mia: Yes, please! Thank you so much.\n\n"
    "Begin: planning, then delimiter, then dialogue."
)

VALID_STYLES = {"narration": NARRATION_TEMPLATE, "dialogue": DIALOGUE_TEMPLATE}

# Short-lived cache, keyed by language. Exists because the top-level Agent has been
# observed calling this tool multiple times for a single learner request, despite explicit
# prompt instructions not to — a 20B model isn't reliably obedient about that on its own.
# With this cache, only the FIRST call in any TTL window actually reaches Groq; repeat
# calls (same language) get the same result back for free.
#
# Successes and failures are cached separately, with different TTLs: a successful story
# is reusable for a while (SUCCESS_CACHE_TTL_SECONDS). A FAILURE is cached only briefly
# (FAILURE_CACHE_TTL_SECONDS) — just long enough that repeated Agent calls during an active
# rate limit don't each independently re-run the full 3-attempt retry loop in call_groq
# (which was making the exhaustion worse, not better), but short enough that a genuine
# retry a bit later still gets a real attempt once the rate limit clears.
_STORY_CACHE = {}
_SUCCESS_CACHE_TTL_SECONDS = 20
_FAILURE_CACHE_TTL_SECONDS = 15

FAILURE_FALLBACK_MESSAGE = (
    "I'm having trouble generating a story right now — please try again in a moment."
)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def load_words(conn, table_name: str = "words") -> str:
    """Return every word in the table as a comma-separated string, in insertion order."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);",
            (table_name,),
        )
        if not cur.fetchone()[0]:
            raise RuntimeError(
                f"Table '{table_name}' does not exist. Run Upload Word File at least once first."
            )
        cur.execute(f"SELECT word FROM {table_name} ORDER BY id;")
        rows = cur.fetchall()
    return ", ".join(row[0] for row in rows)


def build_story_prompt(language: str, words: str, style: Optional[str] = None) -> str:
    language = (language or "").strip()
    words = (words or "").strip()
    if not language:
        raise ValueError("language must be a non-empty string")
    if not words:
        raise ValueError("words must be a non-empty string")
    if not style or style == "random":
        style = random.choice(list(VALID_STYLES.keys()))
    if style not in VALID_STYLES:
        raise ValueError(f"style must be one of {list(VALID_STYLES.keys())}, got {style!r}")
    return VALID_STYLES[style].format(language=language, words=words)


def extract_final_passage(raw_text, delimiter: str = DELIMITER) -> str:
    if not raw_text:
        return ""
    if delimiter in raw_text:
        _, _, after = raw_text.partition(delimiter)
        return after.strip()
    return raw_text.strip()


def call_groq(prompt: str) -> str:
    """Real Groq call with automatic retry on rate limiting (HTTP 429).

    Same request pattern already proven working in scripts/smoke_test.py — including the
    User-Agent header, without which Cloudflare blocks the request (HTTP 1010).

    Retries up to MAX_RETRIES times on a 429, with a short backoff between attempts, since
    Groq's free-tier TPM limit is a small rolling window that typically clears within a
    second or two — not a long-term block. Non-429 errors are not retried.
    """
    import os

    MAX_RETRIES = 3
    BACKOFF_SECONDS = 1.5

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your-groq-api-key-here":
        raise RuntimeError("GROQ_API_KEY is missing or still the placeholder value.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps(
        {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "language-tutor-story-tool/1.0",
        },
        method="POST",
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS)
                last_error = RuntimeError(f"Groq API error {e.code}: {detail}")
                continue
            raise RuntimeError(f"Groq API error {e.code}: {detail}") from e

    raise last_error


def generate_story_for_learner(
    language: str,
    conn=None,
    table_name: str = "words",
    call_groq_fn=call_groq,
    use_cache: bool = True,
) -> str:
    """Full pipeline: load vocabulary, guard against empty vocab, build the prompt, call
    Groq, and return only the cleaned final passage.

    If `conn` is provided, it's used as-is and left open (caller's responsibility to close
    it) — this is how tests inject a connection to a test table. If not provided, a fresh
    connection is created and closed internally.

    If `use_cache` is True (the default — production use), a repeated call for the same
    language within _CACHE_TTL_SECONDS returns the cached result instead of calling Groq
    again. Tests pass use_cache=False to stay isolated from each other.
    """
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    cache_key = (language or "").strip().lower()

    try:
        if use_cache and cache_key in _STORY_CACHE:
            cached_time, cached_result, cached_kind = _STORY_CACHE[cache_key]
            ttl = (
                _SUCCESS_CACHE_TTL_SECONDS
                if cached_kind == "success"
                else _FAILURE_CACHE_TTL_SECONDS
            )
            if time.time() - cached_time < ttl:
                return cached_result

        words = load_words(conn, table_name=table_name)
        if not words.strip():
            return EMPTY_VOCABULARY_MESSAGE

        prompt = build_story_prompt(language, words)
        try:
            raw_response = call_groq_fn(prompt)
        except Exception:
            if use_cache:
                _STORY_CACHE[cache_key] = (time.time(), FAILURE_FALLBACK_MESSAGE, "failure")
            return FAILURE_FALLBACK_MESSAGE

        result = extract_final_passage(raw_response)

        if use_cache:
            _STORY_CACHE[cache_key] = (time.time(), result, "success")

        return result
    finally:
        if owns_connection:
            conn.close()


class StoryGeneratorTool(Component):
    display_name = "Story Generator Tool"
    description = (
        "Generates a vocabulary-constrained story or dialogue for the learner, ready to "
        "use as a single tool for the top-level Language Agent. Handles vocabulary "
        "lookup, the empty-vocabulary guard, prompt building, the Groq call, and stripping "
        "the hidden planning summary — all in one atomic call."
    )
    icon = "BookOpenCheck"
    name = "StoryGeneratorTool"

    inputs = [
        MessageTextInput(
            name="language",
            display_name="Language",
            info="The target language for the story, e.g. 'Spanish'.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Story", name="story", method="run"),
    ]

    def run(self) -> Message:
        language = (self.language or "").strip()
        if not language:
            # The Agent has been observed occasionally sending an empty language argument
            # on repeat tool calls within the same turn. Rather than raising an error here
            # (which risks the Agent giving up on the tool entirely and writing its own
            # unconstrained story instead — exactly the failure mode this is guarding
            # against), fall back to a sensible default so the pipeline still runs.
            language = "English"

        result = generate_story_for_learner(language)
        message = Message(text=result)
        self.status = message
        return message