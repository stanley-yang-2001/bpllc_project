"""The example bank (6 Nov 2026): the table (migration 0016), the replace-if-higher rule, the gate, two per language, and the refresh
script with a scripted model. The learners' words are never involved."""
import os
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutor_core"))

import refresh_story_bank as refresh  # noqa: E402
from tutor_core import example_bank as bank, story as tc_story  # noqa: E402
from tutor_core.prompts.templates import DELIMITER  # noqa: E402
from tutor_core.quality import score_story  # noqa: E402

from conftest import DB_URL  # noqa: E402

GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer. "
        "Por la tarde vuelven a casa y leen un libro. Al final del día los dos duermen contentos.")
ENGLISH = ("Mary lives in a big house near the sea. Every morning she opens the window and looks at the water. Her friend Peter comes with "
           "fresh bread and they eat together in the garden.")
OK = "Casa. Mar. Pan. Sol. Agua. Perro. Gato. Mesa."


def scored(score, **extra):
    return {"score": score, "parts": {"length": score}, "gated": None, "version": 1, **extra}


@pytest.fixture
def conn(app):
    c = psycopg2.connect(DB_URL)
    with c, c.cursor() as cur:
        cur.execute("TRUNCATE tutor.story_examples RESTART IDENTITY")
    yield c
    with c, c.cursor() as cur:
        cur.execute("TRUNCATE tutor.story_examples RESTART IDENTITY")
    c.close()


def test_the_first_two_stories_are_added_whatever_they_score(conn):
    assert bank.offer(conn, "es", "uno", scored(40)) == "added"
    assert bank.offer(conn, "es", "dos", scored(60)) == "added"
    assert [e["text"] for e in bank.examples(conn, "es")] == ["dos", "uno"]
    assert all(e["provisional"] for e in bank.examples(conn, "es"))          # under 85: kept only until a better one arrives


def test_a_higher_score_replaces_the_lower_story_and_its_score(conn):
    bank.offer(conn, "es", "uno", scored(40))
    bank.offer(conn, "es", "dos", scored(60))
    assert bank.offer(conn, "es", "tres", scored(75)) == "replaced"
    rows = bank.examples(conn, "es")
    assert [(e["text"], e["score"]) for e in rows] == [("tres", 75.0), ("dos", 60.0)]
    assert bank.offer(conn, "es", "cuatro", scored(90)) == "replaced"
    rows = bank.examples(conn, "es")
    assert [(e["text"], e["score"], e["provisional"]) for e in rows] == [("cuatro", 90.0, False), ("tres", 75.0, True)]
    assert len(rows) == 2


def test_a_lower_or_equal_score_is_kept_out(conn):
    bank.offer(conn, "es", "uno", scored(70))
    bank.offer(conn, "es", "dos", scored(80))
    assert bank.offer(conn, "es", "tres", scored(70)) == "kept"            # a tie keeps the older story
    assert bank.offer(conn, "es", "cuatro", scored(50)) == "kept"
    assert sorted(e["text"] for e in bank.examples(conn, "es")) == ["dos", "uno"]


def test_the_gate_and_empty_text_never_get_in(conn):
    assert bank.offer(conn, "es", "x", scored(0.0, gated="wrong_language")) == "rejected"
    assert bank.offer(conn, "es", "x", scored(80, gated="empty")) == "rejected"
    assert bank.offer(conn, "es", "  ", scored(80)) == "rejected"
    assert bank.counts(conn, ["es"]) == {"es": 0}


def test_languages_are_kept_apart_and_the_table_allows_only_two(conn):
    for lang in ("es", "de"):
        bank.offer(conn, lang, f"{lang}1", scored(50))
        bank.offer(conn, lang, f"{lang}2", scored(60))
    assert bank.counts(conn, ["es", "de", "fr"]) == {"es": 2, "de": 2, "fr": 0}
    with pytest.raises(psycopg2.Error), conn, conn.cursor() as cur:
        cur.execute("INSERT INTO tutor.story_examples (language, slot, text, score) VALUES ('es', 3, 'x', 50)")
    with pytest.raises(psycopg2.Error), conn, conn.cursor() as cur:
        cur.execute("INSERT INTO tutor.story_examples (language, slot, text, score) VALUES ('es', 1, 'x', 50)")      # the slot is taken
    with pytest.raises(psycopg2.Error), conn, conn.cursor() as cur:
        cur.execute("INSERT INTO tutor.story_examples (language, slot, text, score) VALUES ('fr', 1, 'x', 0)")       # score 0 is never stored


def test_the_story_tool_role_can_read_but_not_write(app, conn):
    bank.offer(conn, "es", "uno", scored(70))
    with conn, conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE tutor_tools")
        cur.execute("SELECT count(*) FROM tutor.story_examples")
        assert cur.fetchone()[0] == 1
    conn.rollback()
    with pytest.raises(psycopg2.Error), conn, conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE tutor_tools")
        cur.execute("DELETE FROM tutor.story_examples")


def test_best_for_prompt(conn):
    assert bank.best_for_prompt(conn, "es") is None
    bank.offer(conn, "es", "uno", scored(60))
    bank.offer(conn, "es", "dos", scored(80))
    assert bank.best_for_prompt(conn, "es") == "dos"


# --- the refresh script, with a scripted model ----------------------------------------------------------------------------------

class Model:
    """Answers every story prompt with the next text of a list (the last one repeats); records the prompts."""

    def __init__(self, *texts):
        self.texts, self.prompts = list(texts), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        i = min(len(self.prompts), len(self.texts)) - 1
        return f"{DELIMITER}\n{self.texts[i]}"


def test_refresh_fills_a_language_to_two_and_improves_it(conn):
    model = Model(OK, GOOD, GOOD + " Mañana ellos vuelven.")
    out = refresh.refresh_language(conn, "es", rounds=2, per_round=2, call=model, say=lambda *_: None, seed=1)
    rows = bank.examples(conn, "es")
    assert len(rows) == 2 and out["outcomes"][0] == "added" and rows[0]["score"] > 80
    assert refresh.status(conn, ["es"], say=lambda *_: None) == []


def test_refresh_reports_languages_that_still_have_fewer_than_two(conn):
    refresh.refresh_language(conn, "de", rounds=1, per_round=1, call=Model(ENGLISH), say=lambda *_: None, seed=1)       # English text for German: gated
    assert bank.counts(conn, ["de"]) == {"de": 0}
    assert refresh.status(conn, ["de", "es"], say=lambda *_: None) == ["de", "es"]


def test_the_candidates_come_from_starter_pack_words_only(conn):
    model = Model(GOOD)
    refresh.refresh_language(conn, "es", rounds=1, per_round=1, call=model, say=lambda *_: None, seed=1)
    words = refresh.starter_words("es")
    assert len(words) >= 20 and any(w in model.prompts[0] for w in words[:10])
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tutor.words")
        assert cur.fetchone()[0] == 0                                         # no learner's list was read or written


def test_every_language_has_starter_words():
    from tutor_core.languages import LANGUAGES
    assert all(len(refresh.starter_words(code)) >= 20 for code in LANGUAGES)


def test_an_example_reaches_the_prompt_only_when_switched_on(conn, monkeypatch):
    bank.offer(conn, "es", "EXAMPLE-TEXT-ONE", scored(90))
    words = refresh.starter_words("es")
    plain = Model(GOOD)
    tc_story.story_from_words("es", words, plain, rng=__import__("random").Random(1))
    assert "EXAMPLE-TEXT-ONE" not in plain.prompts[0]
    shown = Model(GOOD)
    tc_story.story_from_words("es", words, shown, rng=__import__("random").Random(1), with_example=True, conn=conn)
    assert "EXAMPLE-TEXT-ONE" in shown.prompts[0] and "do not copy its topic" in shown.prompts[0]


# --- the comparison script's fix: a learner with no words in a language gets the starter words ----------------------------------

def test_the_comparison_script_adds_starter_words_when_a_learner_has_none(conn, make_learner, capsys):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
    import compare_story_versions as cmp
    from tutor_core import vocab
    learner = make_learner()
    assert vocab.load_words(conn, learner, "de") == []
    words = cmp.seed_words(conn, learner, "de")
    assert len(words) == 25 and "Haus" in words
    assert cmp.seed_words(conn, learner, "de") == words                      # run twice: nothing doubled, nothing removed
    assert len(cmp.seed_words(conn, learner, "en")) == 25                    # English has a starter list too (6 Nov)
    assert cmp.seed_words(conn, learner, "xx") == []                         # no starter list for an unknown language
    assert cmp.seed_words(conn, 99999, "es") == []                           # a learner id that does not exist: a message, not a crash
    assert "User ID shown in Settings" in capsys.readouterr().out
