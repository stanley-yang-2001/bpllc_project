"""
Tests for story variety (Step 10, tuning change #2).

Found by reading 48 generated stories: 81% mention water and about 75% are somebody asking for
or receiving something. Causes in the prompt: only two forms (first-person narration and
dialogue), a plan whose "Event" is by definition "a question or request needing a response", a
5-6 short-sentence cap, "no new content words", and nothing in the code that varies the topic.

The change: more story TYPES (a story with a problem and an ending, a diary entry, a letter, a
place description, a daily routine, a funny anecdote) chosen at random, a TOPIC seed chosen in
code without repeating recent topics, a looser word rule for the new types (the vocabulary stays
central; a few very common everyday words are allowed) and longer, more flexible lengths.
The two classic templates (narration, dialogue) are untouched and still pinned by checksum in
test_story_prompt_language.py; conversations are now only a part of what gets generated.

Written BEFORE the change. No database or network.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_story_variety.py
"""

import random
import sys
from collections import Counter

sys.path.insert(0, "/app/custom_components")

import story_tool  # noqa: E402
from story_tool import (  # noqa: E402
    ALL_STORY_TYPES,
    STORY_TYPES,
    TOPICS,
    build_story_prompt,
    choose_story_type,
    choose_topic,
    describe_prompt,
    generate_story_for_learner,
)

PASS = "PASS"
FAIL = "FAIL"
failures = []

WORDS = "hello, water, friend, house, thank you, book"
NEW_TYPES = ["story", "diary", "letter", "place", "routine", "anecdote"]


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return (True,)

    def fetchall(self):
        return [(w.strip(),) for w in WORDS.split(",")]


class FakeConnection:
    def cursor(self):
        return FakeCursor()


# --- the catalogue ----------------------------------------------------------------------------


def test_catalogue():
    check("the six new story types exist", all(t in STORY_TYPES for t in NEW_TYPES))
    check("each type has a form, a length rule and a form rule",
          all({"form", "length", "rule"} <= set(STORY_TYPES[t]) and all(STORY_TYPES[t].values()) for t in NEW_TYPES))
    check("the classic styles are still available", {"narration", "dialogue"} <= set(ALL_STORY_TYPES))
    check("all types are listed once", len(ALL_STORY_TYPES) == len(set(ALL_STORY_TYPES)) == 8)
    check("there are enough topics to vary (>= 16) and none repeat", len(TOPICS) >= 16 and len(TOPICS) == len(set(TOPICS)))


# --- random choice ----------------------------------------------------------------------------


def test_choose_story_type():
    check("a seeded choice is deterministic",
          [choose_story_type(random.Random(3)) for _ in range(5)] == [choose_story_type(random.Random(3)) for _ in range(5)])
    rng = random.Random(7)
    draws = Counter(choose_story_type(rng) for _ in range(1600))
    check("every type is drawn", set(draws) == set(ALL_STORY_TYPES))
    classic = (draws["narration"] + draws["dialogue"]) / 1600
    check(f"conversations/classic narration are only part of the mix (got {classic:.0%}, want < 30%)", classic < 0.30)
    check("no single type dominates (largest share < 25%)", max(draws.values()) / 1600 < 0.25)


def test_choose_topic():
    rng = random.Random(1)
    recent = list(TOPICS[:-1])
    check("a topic that is not in the recent list is preferred", choose_topic(rng, recent=recent) == TOPICS[-1])
    check("when every topic is recent, it still returns a valid one", choose_topic(rng, recent=list(TOPICS)) in TOPICS)
    seen = []
    for _ in range(8):
        seen.append(choose_topic(random.Random(), recent=seen))
    check("eight picks in a row never repeat a topic", len(set(seen)) == 8)


# --- the prompts ------------------------------------------------------------------------------


def test_new_type_prompts_english():
    for t in NEW_TYPES:
        p = build_story_prompt("English", WORDS, t, topic="a rainy day")
        spec = STORY_TYPES[t]
        check(f"[{t}] contains its form, length rule and form rule",
              spec["form"] in p and spec["length"] in p and spec["rule"] in p)
        check(f"[{t}] contains the topic and the vocabulary", "a rainy day" in p and WORDS in p)
        check(f"[{t}] keeps the planning delimiter protocol", "===STORY===" in p and "Begin:" in p)
        check(f"[{t}] has no unfilled placeholders", "{" not in p and "}" not in p)
        check(f"[{t}] has no English tone example to copy", "I am hungry today" not in p and "Mia: Hello" not in p)
        check(f"[{t}] is not built around 'a question or request needing a response'", "needing a response" not in p)
        check(f"[{t}] allows a few everyday words but keeps the list central",
              "at most 5" in p and "vocabulary words" in p.lower())


def test_new_type_prompts_other_languages():
    for t in NEW_TYPES:
        p = build_story_prompt("Spanish", WORDS, t, topic="a market day")
        check(f"[{t}/Spanish] asks for the ENTIRE text in Spanish, translating the English meanings",
              "LANGUAGE RULE" in p and "ENTIRE" in p and "meaning" in p.lower() and "Spanish" in p)
        check(f"[{t}/Spanish] has no unfilled placeholders", "{" not in p and "}" not in p)


def test_classic_styles_are_unchanged_when_requested():
    d = build_story_prompt("English", WORDS, "dialogue")
    n = build_story_prompt("English", WORDS, "narration")
    check("explicit 'dialogue' still gives the classic dialogue prompt", "short, simple dialogue" in d)
    check("explicit 'narration' still gives the classic narration prompt", "simple reading passage" in n)


def test_default_style_is_a_mix():
    types = Counter()
    rng = random.Random(11)
    for _ in range(200):
        types[describe_prompt(build_story_prompt("English", WORDS, rng=rng))[0]] += 1
    check("the default (no style) now produces all 8 types", set(types) == set(ALL_STORY_TYPES))


def test_invalid_style():
    try:
        build_story_prompt("English", WORDS, "poem")
        check("an unknown style raises ValueError", False)
    except ValueError as e:
        check("an unknown style raises ValueError that lists the valid types", "diary" in str(e) and "dialogue" in str(e))


def test_describe_prompt():
    for t in ALL_STORY_TYPES:
        p = build_story_prompt("English", WORDS, t, topic="a school day")
        kind, topic = describe_prompt(p)
        check(f"describe_prompt recovers the type '{t}'", kind == t)
        if t in NEW_TYPES:
            check(f"describe_prompt recovers the topic for '{t}'", topic == "a school day")
    check("an unrecognised prompt is reported as unknown", describe_prompt("hello")[0] == "unknown")


def test_recent_topics_are_remembered():
    story_tool._RECENT_TOPICS.clear()
    rng = random.Random(5)
    topics = [describe_prompt(build_story_prompt("English", WORDS, "story", rng=rng))[1] for _ in range(8)]
    check("eight random prompts in a row use eight different topics", len(set(topics)) == 8)


# --- generate_story_for_learner ---------------------------------------------------------------


def test_generate_passes_type_and_topic_through():
    story_tool._STORY_CACHE.clear()
    prompts = []

    def fake_groq(prompt):
        prompts.append(prompt)
        return "plan\n===STORY===\nDear Anna, hello."

    generate_story_for_learner("English", conn=FakeConnection(), call_groq_fn=fake_groq, use_cache=False,
                               story_type="letter", topic="a surprise gift")
    kind, topic = describe_prompt(prompts[0])
    check("an explicit story type and topic reach the prompt", kind == "letter" and topic == "a surprise gift")


def test_cache_key_separates_explicit_requests_but_not_random_ones():
    story_tool._STORY_CACHE.clear()
    calls = []

    def fake_groq(prompt):
        calls.append(1)
        return "plan\n===STORY===\nA story."

    for kwargs in ({}, {}, {"story_type": "diary"}, {"story_type": "letter"}, {"story_type": "diary"}):
        generate_story_for_learner("English", conn=FakeConnection(), call_groq_fn=fake_groq, use_cache=True, **kwargs)
    check("repeat calls absorb into one (random) entry, and each explicit type gets its own", len(calls) == 3)
    check("the plain language key is kept for the random case (other tests rely on it)", "english" in story_tool._STORY_CACHE)
    story_tool._STORY_CACHE.clear()


def main():
    print("Running story variety tests...\n")
    test_catalogue()
    test_choose_story_type()
    test_choose_topic()
    test_new_type_prompts_english()
    test_new_type_prompts_other_languages()
    test_classic_styles_are_unchanged_when_requested()
    test_default_style_is_a_mix()
    test_invalid_style()
    test_describe_prompt()
    test_recent_topics_are_remembered()
    test_generate_passes_type_and_topic_through()
    test_cache_key_separates_explicit_requests_but_not_random_ones()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
