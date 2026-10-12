"""tutor_core.story: the story pipeline, per learner (M3, commit 2 of 2).

Groq is replaced by a recorder, so no network is needed; the database is real. What must hold:
  * a learner's story is built only from THAT learner's words in THAT language;
  * the short-lived cache is keyed by (learner, language, type, topic): one learner's story is never served to another;
  * the word cap, the empty-vocabulary guard, failure handling and the returned story type and topic."""
import random

import pytest

from tutor_core import prompts, story, vocab
from tutor_core.languages import LANGUAGES
from tutor_core.story import EMPTY_VOCABULARY_MESSAGE, FAILURE_FALLBACK_MESSAGE, generate_story


@pytest.fixture(autouse=True)
def fresh_cache():
    story._STORY_CACHE.clear()
    prompts._RECENT_TOPICS.clear()
    yield
    story._STORY_CACHE.clear()


class Groq:
    """A stand-in for call_groq that records the prompts it was given."""

    def __init__(self, text="Ana: Hola.", error=None, raw=None):
        self.prompts, self.text, self.error, self.raw = [], text, error, raw

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.raw if self.raw is not None else f"my private plan\n{prompts.DELIMITER}\n{self.text}"


def learner_with(conn, make_learner, language, words):
    l = make_learner()
    for w in words:
        vocab.add_word(conn, l, language, w)
    return l


# --- whose words ------------------------------------------------------------------------------------------

def test_the_story_uses_only_this_learners_words_in_this_language(conn, make_learner):
    a = learner_with(conn, make_learner, "es", ["manzana", "naranja"])
    b = learner_with(conn, make_learner, "es", ["pan", "queso"])
    vocab.add_word(conn, b, "fr", "fromage")
    g = Groq()
    generate_story(conn, b, "es", call_groq_fn=g, story_type="narration", topic="a market")
    prompt = g.prompts[0]
    assert "pan, queso" in prompt
    assert "manzana" not in prompt and "naranja" not in prompt     # not the other learner's
    assert "fromage" not in prompt                                 # not another language's


def test_the_prompt_is_the_one_the_agent_path_always_built_for_that_language(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan", "queso"])
    g = Groq()
    generate_story(conn, l, "es", call_groq_fn=g, story_type="dialogue", topic="a market")
    assert g.prompts[0] == prompts.build_story_prompt("Spanish", "pan, queso", "dialogue", "a market")


@pytest.mark.parametrize("code", sorted(LANGUAGES))
def test_every_supported_language_builds_a_prompt_with_its_english_name(conn, make_learner, monkeypatch, code):
    monkeypatch.setenv("STORY_ALLOW_UNMEASURED", "1")           # this test is about the prompt, not the gate (tested below)
    l = learner_with(conn, make_learner, code, ["pan"])
    g = Groq()
    generate_story(conn, l, code, call_groq_fn=g, story_type="narration", topic="a market")
    assert g.prompts[0] == prompts.build_story_prompt(LANGUAGES[code].name, "pan", "narration", "a market")


@pytest.mark.parametrize("learner, language", [(None, "es"), (0, "es"), ("1", "es"), (1, "xx"), (1, None)])
def test_malformed_arguments_are_refused_before_any_work(conn, make_learner, learner, language):
    make_learner()
    g = Groq()
    with pytest.raises(vocab.VocabError):
        generate_story(conn, learner, language, call_groq_fn=g)
    assert g.prompts == []


# --- the language gate (design 3C: it lives in the story function so Studio and chat obey it equally) ----------

@pytest.mark.parametrize("code", ["de", "it", "pt", "zh", "ko"])
def test_a_language_without_measured_story_quality_is_declined_before_any_work(code):
    g = Groq()
    r = generate_story(None, 1, code, call_groq_fn=g)               # no connection at all: nothing may be touched
    assert (r.ok, r.reason) == (False, "language_not_enabled") and g.prompts == []
    assert r.text == f"Stories in {LANGUAGES[code].name} are not available yet."


@pytest.mark.parametrize("code", ["en", "es", "fr", "ja"])
def test_the_measured_languages_are_not_declined(conn, make_learner, code):
    l = learner_with(conn, make_learner, code, ["pan"])
    assert generate_story(conn, l, code, call_groq_fn=Groq()).ok is True


def test_the_measurement_scripts_can_bypass_the_gate(conn, make_learner, monkeypatch):
    l = learner_with(conn, make_learner, "de", ["Haus"])
    monkeypatch.setenv("STORY_ALLOW_UNMEASURED", "1")
    assert generate_story(conn, l, "de", call_groq_fn=Groq()).ok is True


# --- the result -------------------------------------------------------------------------------------------

def test_a_success_returns_only_the_passage_and_what_was_used(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan", "queso", "agua"])
    r = generate_story(conn, l, "es", call_groq_fn=Groq(text="Ana: Hola.\nBen: Hola."), story_type="diary", topic="a market")
    assert r.text == "Ana: Hola.\nBen: Hola." and "private plan" not in r.text
    assert (r.ok, r.reason, r.language, r.cached) == (True, None, "es", False)
    assert (r.story_type, r.topic) == ("diary", "a market")
    assert (r.words_total, r.words_used) == (3, 3)


def test_the_classic_styles_report_no_topic(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan"])
    r = generate_story(conn, l, "es", call_groq_fn=Groq(), story_type="narration", topic="a market")
    assert (r.story_type, r.topic) == ("narration", None)


def test_the_type_and_topic_are_reported_even_when_the_code_picked_them(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan", "queso"])
    seen_topic = False
    for seed in range(25):
        story._STORY_CACHE.clear()
        g = Groq()
        r = generate_story(conn, l, "es", call_groq_fn=g, rng=random.Random(seed), use_cache=False)
        assert r.story_type in prompts.ALL_STORY_TYPES
        assert prompts.describe_prompt(g.prompts[0]) == (r.story_type, r.topic)       # what is reported is what was asked
        seen_topic = seen_topic or bool(r.topic)
    assert seen_topic                                                                  # the newer types do carry a topic


def test_an_empty_vocabulary_never_reaches_groq_and_is_not_cached(conn, make_learner):
    rich = learner_with(conn, make_learner, "es", ["pan"])
    empty = make_learner()
    g = Groq()
    r = generate_story(conn, empty, "es", call_groq_fn=g)
    assert (r.text, r.ok, r.reason) == (EMPTY_VOCABULARY_MESSAGE, False, "empty_vocabulary") and g.prompts == []
    vocab.add_word(conn, empty, "es", "agua")
    assert generate_story(conn, empty, "es", call_groq_fn=g).ok is True      # not stuck on the cached refusal
    assert rich != empty


def test_a_learner_with_words_only_in_another_language_gets_the_empty_message(conn, make_learner):
    l = learner_with(conn, make_learner, "fr", ["pain"])
    assert generate_story(conn, l, "es", call_groq_fn=Groq()).reason == "empty_vocabulary"


# --- what comes back from the model (ported from the old root tests) ------------------------------------------

class NoneGroq:
    def __call__(self, prompt):
        return None


def test_a_response_without_the_delimiter_is_used_whole_not_an_error(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan"])
    r = generate_story(conn, l, "es", call_groq_fn=Groq(raw="Hello, this is a fake story with no delimiter."))
    assert (r.ok, r.text) == (True, "Hello, this is a fake story with no delimiter.")


@pytest.mark.parametrize("groq", [NoneGroq(), Groq(raw="   \n  "), Groq(raw=f"{prompts.DELIMITER}")])
def test_none_or_blank_model_output_is_the_apology_never_an_empty_string(conn, make_learner, groq):
    l = learner_with(conn, make_learner, "es", ["pan"])
    r = generate_story(conn, l, "es", call_groq_fn=groq)
    assert (r.text, r.reason) == (FAILURE_FALLBACK_MESSAGE, "failed")


def test_an_explicit_type_and_topic_reach_the_prompt_and_the_result(conn, make_learner):
    l = learner_with(conn, make_learner, "en", ["bread"])
    g = Groq()
    r = generate_story(conn, l, "en", call_groq_fn=g, story_type="letter", topic="a surprise gift")
    assert (r.story_type, r.topic) == ("letter", "a surprise gift") and "a surprise gift" in g.prompts[0]


def test_random_requests_share_one_cache_entry_and_each_explicit_type_gets_its_own(conn, make_learner):
    l = learner_with(conn, make_learner, "en", ["bread"])
    g = Groq()
    for _ in range(3):
        generate_story(conn, l, "en", call_groq_fn=g)                         # no type asked: random, but one entry
    assert len(g.prompts) == 1
    for t in ("letter", "diary"):
        generate_story(conn, l, "en", call_groq_fn=g, story_type=t)
    assert len(g.prompts) == 3 and (l, "en", "", "") in story._STORY_CACHE


# --- failures ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("groq", [Groq(error=RuntimeError("429")), Groq(raw=""), Groq(raw=f"plan only\n{prompts.DELIMITER}\n   ")])
def test_a_failure_is_the_fixed_apology_never_an_empty_string(conn, make_learner, groq):
    l = learner_with(conn, make_learner, "es", ["pan"])
    r = generate_story(conn, l, "es", call_groq_fn=groq)
    assert (r.text, r.ok, r.reason) == (FAILURE_FALLBACK_MESSAGE, False, "failed")


def test_a_failure_is_remembered_only_briefly(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan"])
    g, now = Groq(error=RuntimeError("429")), [1000.0]
    generate_story(conn, l, "es", call_groq_fn=g, clock=lambda: now[0])
    now[0] += story._FAILURE_CACHE_TTL_SECONDS - 1
    again = generate_story(conn, l, "es", call_groq_fn=g, clock=lambda: now[0])
    assert len(g.prompts) == 1 and again.cached is True                       # the Agent's repeat calls do not re-hit Groq
    now[0] += 2
    generate_story(conn, l, "es", call_groq_fn=g, clock=lambda: now[0])
    assert len(g.prompts) == 2                                                # but a retry a bit later gets a real attempt


def test_a_success_is_reused_for_a_while_then_refreshed(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan"])
    g, now = Groq(), [1000.0]
    first = generate_story(conn, l, "es", call_groq_fn=g, clock=lambda: now[0])
    now[0] += story._SUCCESS_CACHE_TTL_SECONDS - 1
    second = generate_story(conn, l, "es", call_groq_fn=g, clock=lambda: now[0])
    assert (first.cached, second.cached, len(g.prompts)) == (False, True, 1) and second.text == first.text
    now[0] += 2
    generate_story(conn, l, "es", call_groq_fn=g, clock=lambda: now[0])
    assert len(g.prompts) == 2


def test_the_direct_path_can_switch_the_cache_off(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan"])
    g = Groq()
    generate_story(conn, l, "es", call_groq_fn=g, use_cache=False)
    generate_story(conn, l, "es", call_groq_fn=g, use_cache=False)
    assert len(g.prompts) == 2 and story._STORY_CACHE == {}                   # "Regenerate" must make a new story


# --- the cache never crosses learners ---------------------------------------------------------------------

def test_one_learners_story_is_never_served_to_another(conn, make_learner):
    a = learner_with(conn, make_learner, "es", ["manzana"])
    b = learner_with(conn, make_learner, "es", ["pan"])
    ga, gb = Groq(text="story for a"), Groq(text="story for b")
    ra = generate_story(conn, a, "es", call_groq_fn=ga)
    rb = generate_story(conn, b, "es", call_groq_fn=gb)
    assert (ra.text, rb.text) == ("story for a", "story for b")
    assert len(ga.prompts) == 1 and len(gb.prompts) == 1                     # b got a real call, not a's cached story
    assert "manzana" in ga.prompts[0] and "pan" in gb.prompts[0] and "manzana" not in gb.prompts[0]
    assert rb.cached is False


def test_the_cache_key_is_learner_language_type_and_topic(conn, make_learner):
    l = learner_with(conn, make_learner, "es", ["pan"])
    for w in ("pain",):
        vocab.add_word(conn, l, "fr", w)
    g = Groq()
    generate_story(conn, l, "es", call_groq_fn=g, story_type="narration", topic="a market")
    generate_story(conn, l, "fr", call_groq_fn=g, story_type="narration", topic="a market")      # another language
    generate_story(conn, l, "es", call_groq_fn=g, story_type="dialogue", topic="a market")       # another type
    generate_story(conn, l, "es", call_groq_fn=g, story_type="narration", topic="a train trip")  # another topic
    assert len(g.prompts) == 4
    generate_story(conn, l, "es", call_groq_fn=g, story_type="narration", topic="a market")      # the very same request
    assert len(g.prompts) == 4
    assert {k[0] for k in story._STORY_CACHE} == {l}
    assert all(len(k) == 4 for k in story._STORY_CACHE)


# --- the word cap -----------------------------------------------------------------------------------------

def test_a_long_list_is_capped_in_the_prompt_but_reported_in_full(conn, make_learner, monkeypatch):
    l = learner_with(conn, make_learner, "es", [f"palabra{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(300)])
    seen = []
    real = prompts.build_story_prompt
    monkeypatch.setattr(story, "build_story_prompt", lambda lang, words, *a: (seen.append(words), real(lang, words, *a))[1])
    r = generate_story(conn, l, "es", call_groq_fn=Groq(), max_words=150, rng=random.Random(5), story_type="narration", topic="a market")
    assert len(seen[0].split(", ")) == 150
    assert (r.words_total, r.words_used) == (300, 150)


def test_the_cap_comes_from_the_environment_by_default(conn, make_learner, monkeypatch):
    l = learner_with(conn, make_learner, "es", [f"palabra{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(60)])
    monkeypatch.setenv("MAX_PROMPT_WORDS", "25")
    r = generate_story(conn, l, "es", call_groq_fn=Groq())
    assert r.words_used == 25
