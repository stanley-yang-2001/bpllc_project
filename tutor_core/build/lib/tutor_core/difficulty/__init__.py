"""Story difficulty (24 Oct 2026, docs/DIFFICULTY-TIERS-DESIGN.md): three measures, three presets, and the learner's own settings.

  1. LENGTH         the story's length in words (characters for Chinese and Japanese, which have no spaces)
  2. OWN WORDS      how many DIFFERENT words from the learner's list the story uses
  3. UNCOMMON SHARE the share of words that are neither in the language's everyday list nor the learner's own words
                    (all nine languages; Chinese, Japanese and Korean need the splitter, see splitter.py, else None)

A tier is a set of targets for the three. They go into the story prompt as a note at the top, and the finished story is measured
against them. The model follows them loosely (own-word counts and the uncommon share especially), so the report shows what was
measured next to what was asked for and a story that misses is shown as it is, never relabelled or silently regenerated.

The work is in four files; this one keeps `tutor_core.difficulty` importing as it always did:

    presets.py   the tiers, the limits, resolve, the sizes the prompt asks for
    measuring.py everyday lists, and what a finished story measures
    note.py      the note at the top of the story prompt
    judging.py   whether the story met what was asked, and the report section
"""
from .. import splitter                                       # noqa: F401  (tests reach it as difficulty.splitter)
from .judging import evaluate, section
from .measuring import (_covered, _everyday, _lemma, _own_found, _own_set, _tokens, _uncommon_share, _uncommon_split, can_measure_uncommon,  # noqa: F401
                      has_everyday_list, is_everyday, measure)
from .note import prompt_note
from .presets import (CHARS_PER_WORD, LENGTH_TOLERANCE, LIMITS, TIER_NAMES, TIERS, UNCOMMON_SLACK, UNSPACED, _unit, ask_size,  # noqa: F401
                      is_unspaced, resolve)

everyday_words = _everyday                                     # the public name for the language's everyday-word set

__all__ = ["CHARS_PER_WORD", "LENGTH_TOLERANCE", "LIMITS", "TIERS", "TIER_NAMES", "UNCOMMON_SLACK", "UNSPACED", "ask_size", "can_measure_uncommon",
           "evaluate", "everyday_words", "has_everyday_list", "is_everyday", "is_unspaced", "measure", "prompt_note", "resolve", "section"]
