"""The language heuristics of scripts/meanings_check.py (the live check itself needs Groq and is run with run-checks.bat --round)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import meanings_check as mc  # noqa: E402


def test_english_is_ascii_with_an_english_word():
    assert mc.looks_english("A clear liquid that you drink.")
    assert not mc.looks_english("Un líquido que se bebe.")
    assert not mc.looks_english("水")
    assert not mc.looks_english("")


def test_spanish_needs_a_spanish_word_and_not_english_ones():
    assert mc.looks_spanish("Un líquido transparente que se bebe.")
    assert mc.looks_spanish("Animal doméstico de cuatro patas")
    assert not mc.looks_spanish("A clear liquid that you drink.")
    assert not mc.looks_spanish("水")


def test_french_and_japanese():
    assert mc.looks_french("Un liquide qui est transparent.")
    assert not mc.looks_french("A clear liquid that you drink.")
    assert mc.looks_japanese("飲む液体") and mc.looks_japanese("みず") and not mc.looks_japanese("water")


def test_both_halves_must_be_two_parts_in_order():
    assert mc.both_halves("A pet that purrs / Un animal que maúlla", mc.looks_english, mc.looks_spanish)
    assert not mc.both_halves("Un animal que maúlla / A pet that purrs", mc.looks_english, mc.looks_spanish)
    assert not mc.both_halves("A pet that purrs", mc.looks_english, mc.looks_spanish)
    assert not mc.both_halves("A pet / Un animal / extra", mc.looks_english, mc.looks_spanish)
    assert not mc.both_halves(" / Un animal que maúlla", mc.looks_english, mc.looks_spanish)


def test_one_word_glosses_from_the_first_live_run_are_accepted():
    """The 0040 round failed three cases only because 'water', 'arbre' and 'cat / gato' hold none of the function words the lists look for."""
    assert not mc.looks_english("water") and mc.plain_translation("agua", "water")
    assert not mc.looks_french("arbre") and mc.plain_translation("árbol", "arbre")
    assert mc.plain_translation("ventana", "Fenêtre") and mc.plain_translation("camino", "chemin")
    assert mc.both_gloss("gato", "cat / gato") and mc.both_gloss("puerta", "door / puerta")


def test_a_wrong_one_word_gloss_is_still_refused():
    assert not mc.plain_translation("agua", "fire") and not mc.plain_translation("agua", "agua")
    assert not mc.plain_translation("árbol", "tree"), "the French case wants French, not English"
    assert not mc.both_gloss("gato", "cat / cat"), "the Spanish half must not just repeat the English"
    assert not mc.both_gloss("gato", "gato / cat") and not mc.both_gloss("gato", "cat") and not mc.both_gloss("gato", "猫 / gato")


def test_a_busy_model_is_waited_for_as_long_as_the_api_says():
    import text_tools_check as tt
    waits, answers = [], [(429, {"retry_after": 20}), (429, {"retry_after": 8}), (200, {"ok": True})]
    real_sleep = {"m": mc.time.sleep, "t": tt.time.sleep}
    mc.time.sleep = tt.time.sleep = waits.append
    try:
        for module in (mc, tt):
            waits.clear()
            queue = list(answers)
            assert module.with_retry(lambda: queue.pop(0), 10) == (200, {"ok": True})
            assert waits == [23, 15], waits       # retry_after + 3, never under 15 seconds
        queue = [(429, {"retry_after": 1})] * 5
        assert tt.with_retry(lambda: queue.pop(0), 10)[0] == 429 and len(queue) == 2, "it gives up after two retries"
    finally:
        mc.time.sleep, tt.time.sleep = real_sleep["m"], real_sleep["t"]
