"""Which optional quality steps a story uses (7 Nov 2026). Everything is OFF unless asked for, so the default pipeline is unchanged.

    two_pass    draft with no word list, then adapt it to the words (two_pass.py)          STORY_TWO_PASS=1
    candidates  write n versions of the word-applying step and keep the best one           STORY_CANDIDATES=3
    mixed       candidates by different strategies: half one-pass, half two-pass          STORY_MIXED=1
    gates       free pass/fail checks first; a failing candidate is dropped unseen       STORY_GATES=1
    refine      check, then fix only the flagged sentences, up to n rounds (story_refine.py)  STORY_REFINE=2
    naturalness the judge also rates how natural the best candidates read (1-5)          STORY_NATURALNESS=1
    plan        name only about one learner word per 17 words, and a maximum              STORY_PLAN=1
    judge       choose among candidates with the score plus a model review of grammar      STORY_JUDGE=1
    repair      after the usual retries, fix what the score still finds wrong, by name     STORY_REPAIR=1
    examples    show the model a saved good example (example bank, needs the database)    STORY_EXAMPLES=1
    proofread   one grammar-fixing call on every story                                     STORY_PROOFREAD=1
    range       ask for a word range and name the level (difficulty/note.py)               STORY_RANGE_PROMPT=1
    repair_nat  the repair also rates naturalness and quotes the reviewer's reason          STORY_REPAIR_NATURALNESS=1
    rules       writer rules: keep every small word, no tacked-on words, no filler (prompts/builder.py)  STORY_WRITER_RULES=1
    writer_v2   writer v2: scene first, mixed sentence length, varied openers, paragraphs, name/place/time by code  STORY_WRITER_V2=1
    outline     write from an outline: "whole" (outline call, then one call for the text) or "beats" (then one call per event)  STORY_OUTLINE=whole|beats
    repair_dir  the repair also gets concrete rhythm, opener and filler edits from free checks (story_diagnose.py)  STORY_REPAIR_DIRECTIVES=1

A value is the same everywhere it is used: `StoryOptions.from_env()` for the app, `StoryOptions(...)` in tests and the comparison runner.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, fields

MAX_CANDIDATES = 5
MAX_REFINE = 3


def _int(value) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _outline(value) -> str:
    value = str(value or "").strip().lower()
    return value if value in ("whole", "beats") else ""


@dataclass(frozen=True)
class StoryOptions:
    candidates: int = 1
    judge: bool = False
    repair: bool = False
    mixed: bool = False
    gates: bool = False
    plan: bool = False
    naturalness: bool = False
    refine: int = 0                  # rounds of check-then-fix-flagged-sentences (story_refine.py); 0 = off
    rules: bool = False              # writer rules added to the prompt (prompts/builder.py WRITER_RULES); the default prompt is unchanged
    repair_naturalness: bool = False  # the repair also rates how natural the text reads and quotes the reviewer's reason to the writer (story_repair.py)
    writer_v2: bool = False          # the writer v2 block in the prompt (prompts/builder.py, story_seed.py); the default prompt is unchanged
    repair_directives: bool = False  # the repair starts from free rhythm/opener/filler findings and gives the writer concrete edits (story_diagnose.py, story_repair.py)
    outline: str = ""                # "", "whole" or "beats": an outline call first, then one call for the text or one per event (story_outline.py)

    @classmethod
    def from_env(cls, env=None) -> "StoryOptions":
        env = os.environ if env is None else env
        try:
            n = int(env.get("STORY_CANDIDATES") or 1)
        except ValueError:
            n = 1
        return cls(candidates=max(1, min(MAX_CANDIDATES, n)), judge=env.get("STORY_JUDGE") == "1", repair=env.get("STORY_REPAIR") == "1",
                   mixed=env.get("STORY_MIXED") == "1", gates=env.get("STORY_GATES") == "1", plan=env.get("STORY_PLAN") == "1",
                   naturalness=env.get("STORY_NATURALNESS") == "1", refine=max(0, min(MAX_REFINE, _int(env.get("STORY_REFINE")))),
                   rules=env.get("STORY_WRITER_RULES") == "1", repair_naturalness=env.get("STORY_REPAIR_NATURALNESS") == "1",
                   writer_v2=env.get("STORY_WRITER_V2") == "1", repair_directives=env.get("STORY_REPAIR_DIRECTIVES") == "1", outline=_outline(env.get("STORY_OUTLINE")))

    def normalised(self) -> "StoryOptions":
        return StoryOptions(max(1, min(MAX_CANDIDATES, int(self.candidates))), bool(self.judge), bool(self.repair), bool(self.mixed),
                            bool(self.gates), bool(self.plan), bool(self.naturalness), max(0, min(MAX_REFINE, int(self.refine))), bool(self.rules),
                            bool(self.repair_naturalness), bool(self.writer_v2), bool(self.repair_directives), _outline(self.outline))

    def cache_parts(self) -> tuple:
        """What to add to a cache key: nothing when every option is off, so the default key is the one it always was."""
        o = self.normalised()
        parts = ()
        if o.candidates > 1:
            parts += (("candidates", o.candidates),)
        if o.judge:
            parts += (("judge",),)
        if o.repair:
            parts += (("repair",),)
        for name in ("mixed", "gates", "plan", "naturalness", "rules", "repair_naturalness", "writer_v2", "repair_directives"):
            if getattr(o, name):
                parts += ((name,),)
        if o.outline:
            parts += (("outline", o.outline),)
        if o.refine:
            parts += (("refine", o.refine),)
        return parts

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}
