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
