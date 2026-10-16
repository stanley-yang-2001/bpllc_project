"""M6 commit 1: the checker moved from scripts/ into tutor_core.quality, unchanged. The old import path must keep working."""
import importlib.util
import pathlib

from tutor_core import quality

SHIM = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "vocab_adherence.py"


def load_shim():
    spec = importlib.util.spec_from_file_location("vocab_adherence_shim", SHIM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_checker_is_importable_from_the_package():
    assert callable(quality.check_passage) and callable(quality.language_check) and callable(quality.summarize)


def test_the_old_script_path_still_exposes_every_name():
    shim = load_shim()
    missing = [n for n in vars(quality) if not n.startswith("__") and not hasattr(shim, n)]
    assert missing == []
    assert shim.check_passage is quality.check_passage and shim._norm is quality._norm


def test_a_passage_scores_the_same_through_either_path():
    text = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye."
    vocab = "hello, friend, water, please, thank you, goodbye"
    assert load_shim().check_passage(text, vocab) == quality.check_passage(text, vocab)
    assert quality.check_passage(text, vocab)["passed"] is True
