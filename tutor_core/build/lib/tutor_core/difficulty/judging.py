"""Did the story meet what was asked for? And the report's difficulty section."""
from __future__ import annotations

from .measuring import measure
from .presets import CHARS_PER_WORD, LENGTH_TOLERANCE, UNCOMMON_SLACK, is_unspaced


def evaluate(targets: dict, measured: dict, language_code: str, list_size: int) -> dict:
    """Did each measure meet its target? True / False, or None when the measure does not apply (no everyday list)."""
    want_len = targets["length"] * (CHARS_PER_WORD if is_unspaced(language_code) else 1)
    length_ok = abs(measured["length"] - want_len) <= LENGTH_TOLERANCE * want_len
    own_ok = measured["own_words"] >= min(targets["own_words"], max(list_size, 0))
    uncommon = measured["uncommon_pct"]
    uncommon_ok = None if uncommon is None else uncommon <= targets["uncommon_pct"] + UNCOMMON_SLACK
    return {"length": length_ok, "own_words": own_ok, "uncommon_pct": uncommon_ok}


def section(targets: dict, text: str, language_code: str, vocab_words) -> dict:
    """The report's difficulty section: what was asked for, what was measured, and whether each measure was met."""
    vocab_words = list(vocab_words or [])
    measured = measure(text, language_code, vocab_words)
    return {"requested": targets, "measured": measured, "met": evaluate(targets, measured, language_code, len(vocab_words)),
            "list_size": len(vocab_words)}
