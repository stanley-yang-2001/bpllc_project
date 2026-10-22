"""scripts/seed_batch_words.py: every starter word is valid, 25 per language, and seeding is additive and repeatable."""
import importlib.util
import pathlib

import pytest

from tutor_core import vocab
from tutor_core.languages import LANGUAGES
from tutor_core.words import validate_word

_path = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "seed_batch_words.py"
_spec = importlib.util.spec_from_file_location("seed_batch_words", _path)
seed_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_mod)


@pytest.mark.parametrize("code", list(seed_mod.WORDS))
def test_every_starter_word_is_valid_and_unique(code):
    assert code in LANGUAGES
    words = seed_mod.word_list(code)
    assert len(words) == 25 or code == "ja" and len(words) == 25
    stored = [validate_word(w, code) for w in words]
    assert len(set(stored)) == len(stored)


def test_seeding_adds_then_is_a_no_op(conn, make_learner):
    learner = make_learner()
    first = seed_mod.seed(conn, learner, ["de", "ko"])
    assert first == {"de": (25, 0), "ko": (25, 0)}
    assert len(vocab.load_words(conn, learner, "de")) == 25
    assert seed_mod.seed(conn, learner, ["de"]) == {"de": (0, 25)}


def test_seeding_one_learner_does_not_touch_another(conn, make_learner):
    a, b = make_learner(), make_learner()
    seed_mod.seed(conn, a, ["it"])
    assert vocab.load_words(conn, b, "it") == []
