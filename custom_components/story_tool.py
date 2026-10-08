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
import re
import time
from collections import deque
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

# openai/gpt-oss-20b is a reasoning model: hidden "reasoning" tokens count against max_tokens.
# With max_tokens=400, nearly the whole budget (398 tokens) was spent reasoning, so Groq
# returned finish_reason="length" with content="" — an empty story. A larger budget plus a
# low reasoning effort leaves room for the plan and the passage itself.
_MAX_COMPLETION_TOKENS = 1500
_REASONING_EFFORT = "low"

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


# --- language handling -------------------------------------------------------------------------
# Found in the first live routing run: only 5 of 15 non-English stories were actually written in
# the requested language. Two causes are addressed here:
#   1. The vocabulary list is English, and "use words from this list" keeps the model in English.
#      For other languages the prompt now says the list holds English MEANINGS to be expressed in
#      the target language, with no English left in.
#   2. The tone examples in the templates are written in English, which primes English output.
#      For other languages the English example is left out.
# The English prompt is untouched (the two templates above are used exactly as written).

_NATIVE_LANGUAGE_NAMES = {
    "\u65e5\u672c\u8a9e": "Japanese", "\u306b\u307b\u3093\u3054": "Japanese", "nihongo": "Japanese",
    "\u4e2d\u6587": "Chinese", "\u6c49\u8bed": "Chinese", "\u6f22\u8a9e": "Chinese",
    "\u666e\u901a\u8bdd": "Chinese", "\u56fd\u8bed": "Chinese", "\u570b\u8a9e": "Chinese",
    "\ud55c\uad6d\uc5b4": "Korean",
    "espa\u00f1ol": "Spanish", "espanol": "Spanish", "castellano": "Spanish",
    "fran\u00e7ais": "French", "francais": "French",
    "deutsch": "German", "italiano": "Italian",
    "portugu\u00eas": "Portuguese", "portugues": "Portuguese",
    "\u0440\u0443\u0441\u0441\u043a\u0438\u0439": "Russian",
    "\u0627\u0644\u0639\u0631\u0628\u064a\u0629": "Arabic",
    "\u0939\u093f\u0928\u094d\u0926\u0940": "Hindi",
    "\u03b5\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac": "Greek",
    "\u0e44\u0e17\u0e22": "Thai", "\u05e2\u05d1\u05e8\u05d9\u05ea": "Hebrew",
    "nederlands": "Dutch", "svenska": "Swedish", "t\u00fcrk\u00e7e": "Turkish", "polski": "Polish",
    "ti\u1ebfng vi\u1ec7t": "Vietnamese", "bahasa indonesia": "Indonesian",
    "ingl\u00e9s": "English", "ingles": "English", "anglais": "English", "englisch": "English",
    "\u82f1\u8a9e": "English", "\u82f1\u8bed": "English",
}


def normalize_language(language) -> str:
    """The English name of a language, whatever the learner typed: "\u65e5\u672c\u8a9e" -> "Japanese",
    "fran\u00e7ais" -> "French", " spanish " -> "Spanish". Unknown names are only tidied up."""
    text = " ".join((language or "").split())
    if not text:
        return ""
    known = _NATIVE_LANGUAGE_NAMES.get(text.casefold())
    if known:
        return known
    if text.isascii():
        return " ".join(word.capitalize() for word in text.split(" "))
    return text


def is_english(language) -> bool:
    return normalize_language(language) == "English"


_LANGUAGE_BLOCK = (
    "LANGUAGE RULE (most important): write the ENTIRE passage or dialogue (everything after "
    "the ===STORY=== line) in {language}, and nothing in English. The vocabulary list below is "
    "written in English: treat each entry as a MEANING and use its natural {language} word for "
    "it (if the list has \"water\", write the {language} word for water). Do not leave any "
    "English word in the story; only character names may stay as they are.\n\n"
)
_LANGUAGE_REMINDER = (
    "Final check before you write: every word of the story is in {language} \u2014 each one the "
    "{language} equivalent of a word from the list, or a basic grammar word or simple verb. "
    "No English.\n\n"
)


def _template_for_other_languages(template: str) -> str:
    """The same template with the language rule added after the intro, the English tone example
    removed (if it has one), and a final reminder before 'Begin:'."""
    intro_end = template.index("\n\n") + 2
    begin = template.index("Begin:")
    example_start = template.find("Tone example only")
    middle_end = example_start if example_start != -1 else begin
    return (template[:intro_end] + _LANGUAGE_BLOCK + template[intro_end:middle_end]
            + _LANGUAGE_REMINDER + template[begin:])


_OTHER_LANGUAGE_STYLES = {style: _template_for_other_languages(t) for style, t in VALID_STYLES.items()}


# --- story variety (Step 10, tuning change #2) ---------------------------------------------------
# Reading 48 generated stories showed 81% mentioned water and ~75% were somebody asking for or
# receiving something. The classic prompts define the story's "Event" as a question or request
# needing a response, offer only two forms (narration, dialogue), cap stories at 5-6 short
# sentences, and nothing in the code varies the topic. So, in addition to the two classic styles
# (left exactly as they were), there are more story TYPES, a TOPIC seed chosen in code without
# repeating recent topics, a looser word rule (the vocabulary stays central, a few very common
# everyday words are allowed) and longer, more flexible lengths.

STORY_TYPES = {
    "story": {
        "form": "a short story with a beginning, a small problem, and a happy or surprising ending",
        "length": "Aim for 7 to 9 short sentences (up to 12 words each), each following logically from the last.",
        "rule": "Use a named character, and show what happens (actions and small events), not only talking.",
    },
    "diary": {
        "form": "a diary entry about someone's day",
        "length": "Aim for 6 to 8 short sentences (up to 12 words each).",
        "rule": "Write in the first person and start with a day or a time (for example, Monday morning). Say what happened and how the writer felt.",
    },
    "letter": {
        "form": "a short, friendly letter to a friend",
        "length": "Aim for 6 to 8 short lines (up to 12 words each).",
        "rule": "Start with a greeting to a named friend, and end with a sign-off and your name.",
    },
    "place": {
        "form": "a description of a place (what you can see, hear and do there)",
        "length": "Aim for 6 to 8 short sentences (up to 12 words each).",
        "rule": "Describe the place; do not tell a plot. Use phrases like 'there is' and 'there are'.",
    },
    "routine": {
        "form": "a description of a typical day, in order (morning, afternoon, evening)",
        "length": "Aim for 6 to 8 short sentences (up to 12 words each).",
        "rule": "Write in the first person with simple present tense, and put the parts of the day in order.",
    },
    "anecdote": {
        "form": "a funny or surprising little anecdote (something that went wrong in an amusing way)",
        "length": "Aim for 7 to 9 short sentences (up to 12 words each).",
        "rule": "Build up to the funny or surprising moment, then end quickly.",
    },
}

ALL_STORY_TYPES = tuple(VALID_STYLES) + tuple(STORY_TYPES)  # classic first: narration, dialogue

# Conversations and classic narration stay available, but are only part of the mix (3/16).
_TYPE_WEIGHTS = {"narration": 1, "dialogue": 2, "story": 3, "diary": 2, "letter": 2,
                 "place": 2, "routine": 2, "anecdote": 2}

TOPICS = (
    "a market day", "a birthday party", "a rainy day", "a lost key", "a new pet",
    "a trip by train", "cooking dinner", "a day at school", "a visit to a friend's house",
    "a walk in the park", "a surprise gift", "a busy morning", "a day at the beach",
    "fixing something at home", "a quiet evening at home", "a bus ride", "a picnic",
    "a snowy morning", "a small garden", "a new neighbor", "a long walk home",
)
_RECENT_TOPICS = deque(maxlen=8)

_VARIETY_TEMPLATE = (
    "You are a creative writer crafting a short, interesting reading text for a "
    "language-learning beginner in {language}.\n\n"
    "Form: {form}.\n"
    "Topic: {topic}.\n\n"
    "First, silently plan (do not show this): who or what the text is about, what happens or "
    "what is described, and how it ends or what stands out. Write a 1-2 sentence summary of "
    "your plan, then the line ===STORY=== alone, then the text.\n\n"
    "Text rules:\n"
    "1. {length}\n"
    "2. {rule}\n"
    "3. Build the text around the learner's vocabulary words wherever they fit naturally: "
    "{words}. You don't need every one, and never force a word that breaks the flow. You may "
    "inflect a word's form (tense, plural) while keeping the same root word.\n"
    "4. You may also use basic grammar words, simple verbs, and at most 5 other very common "
    "everyday words that a beginner would already know (like eat, drink, buy, read, school, "
    "rain). No rare or difficult words.\n"
    "5. Keep the language simple and natural: short sentences, simple tenses, no semicolons.\n"
    "6. Output ONLY the ===STORY=== line and the text \u2014 no title, no explanation, no "
    "planning notes.\n\n"
    "Begin: planning, then delimiter, then the text."
)
_OTHER_LANGUAGE_VARIETY = _template_for_other_languages(_VARIETY_TEMPLATE)


def choose_story_type(rng=None) -> str:
    rng = rng or random
    return rng.choices(ALL_STORY_TYPES, weights=[_TYPE_WEIGHTS[t] for t in ALL_STORY_TYPES])[0]


def choose_topic(rng=None, recent=None) -> str:
    """A topic that is not in `recent` (if any are left), so consecutive stories differ."""
    rng = rng or random
    recent = set(recent or ())
    candidates = [t for t in TOPICS if t not in recent] or list(TOPICS)
    return rng.choice(candidates)


def build_story_prompt(language: str, words: str, style: Optional[str] = None,
                       topic: Optional[str] = None, rng=None) -> str:
    """style: one of ALL_STORY_TYPES, or None/"random" for a weighted random choice. topic only
    applies to the new story types; when omitted it is chosen at random, avoiding recent topics."""
    language = normalize_language(language)
    words = (words or "").strip()
    if not language:
        raise ValueError("language must be a non-empty string")
    if not words:
        raise ValueError("words must be a non-empty string")
    if not style or style == "random":
        style = choose_story_type(rng)
    english = is_english(language)

    if style in VALID_STYLES:  # the two classic prompts, unchanged
        templates = VALID_STYLES if english else _OTHER_LANGUAGE_STYLES
        return templates[style].format(language=language, words=words)
    if style in STORY_TYPES:
        if not topic:
            topic = choose_topic(rng, recent=_RECENT_TOPICS)
            _RECENT_TOPICS.append(topic)
        template = _VARIETY_TEMPLATE if english else _OTHER_LANGUAGE_VARIETY
        return template.format(language=language, words=words, topic=topic, **STORY_TYPES[style])
    raise ValueError(f"style must be one of {list(ALL_STORY_TYPES)}, got {style!r}")


def describe_prompt(prompt: str):
    """(story type, topic) of a prompt built by build_story_prompt; ("unknown", None) otherwise."""
    prompt = prompt or ""
    if "short, simple dialogue" in prompt:
        return "dialogue", None
    if "simple reading passage" in prompt:
        return "narration", None
    for story_type, spec in STORY_TYPES.items():
        if f"Form: {spec['form']}." in prompt:
            match = re.search(r"Topic: (.*?)\.\n", prompt)
            return story_type, (match.group(1) if match else None)
    return "unknown", None


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
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _MAX_COMPLETION_TOKENS,
            "reasoning_effort": _REASONING_EFFORT,
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
    story_type: Optional[str] = None,
    topic: Optional[str] = None,
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

    cache_key = normalize_language(language).lower()
    if story_type or topic:  # an explicit request is cached separately from the random default
        cache_key = f"{cache_key}|{story_type or ''}|{topic or ''}"

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

        prompt = build_story_prompt(language, words, story_type, topic)
        try:
            raw_response = call_groq_fn(prompt)
        except Exception:
            if use_cache:
                _STORY_CACHE[cache_key] = (time.time(), FAILURE_FALLBACK_MESSAGE, "failure")
            return FAILURE_FALLBACK_MESSAGE

        result = extract_final_passage(raw_response)

        # An empty passage (the model ran out of tokens, or returned nothing after the
        # delimiter) must never reach the Agent as an empty string: the Agent fills the gap
        # by inventing its own story or error. Treat it as a failure instead — cached
        # briefly, like any other failure.
        if not result.strip():
            if use_cache:
                _STORY_CACHE[cache_key] = (time.time(), FAILURE_FALLBACK_MESSAGE, "failure")
            return FAILURE_FALLBACK_MESSAGE

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
            info="Name of the language for the story, e.g. 'Spanish', 'Chinese' ,'English' etc. Required.",
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