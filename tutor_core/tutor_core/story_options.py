"""Which optional quality steps a story uses (7 Nov 2026). Everything is OFF unless asked for, so the default pipeline is unchanged.

    two_pass    draft with no word list, then adapt it to the words (two_pass.py)          STORY_TWO_PASS=1
    candidates  write n versions of the word-applying step and keep the best one           STORY_CANDIDATES=3
    mixed       candidates by different strategies: half one-pass, half two-pass          STORY_MIXED=1
    gates       free pass/fail checks first; a failing candidate is dropped unseen       STORY_GATES=1
    plan        name only about one learner word per 17 words, and a maximum              STORY_PLAN=1
    judge       choose among candidates with the score plus a model review of grammar      STORY_JUDGE=1
    repair      after the usual retries, fix what the score still finds wrong, by name     STORY_REPAIR=1
    examples    show the model a saved good example (example bank, needs the database)    STORY_EXAMPLES=1
    proofread   one grammar-fixing call on every story                                     STORY_PROOFREAD=1
    range       ask for a word range and name the level (difficulty/note.py)               STORY_RANGE_PROMPT=1

A value is the same everywhere it is used: `StoryOptions.from_env()` for the app, `StoryOptions(...)` in tests and the comparison runner.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, fields

MAX_CANDIDATES = 5


@dataclass(frozen=True)
class StoryOptions:
    candidates: int = 1
    judge: bool = False
    repair: bool = False
    mixed: bool = False
    gates: bool = False
    plan: bool = False

    @classmethod
    def from_env(cls, env=None) -> "StoryOptions":
        env = os.environ if env is None else env
        try:
            n = int(env.get("STORY_CANDIDATES") or 1)
        except ValueError:
            n = 1
        return cls(candidates=max(1, min(MAX_CANDIDATES, n)), judge=env.get("STORY_JUDGE") == "1", repair=env.get("STORY_REPAIR") == "1",
                   mixed=env.get("STORY_MIXED") == "1", gates=env.get("STORY_GATES") == "1", plan=env.get("STORY_PLAN") == "1")

    def normalised(self) -> "StoryOptions":
        return StoryOptions(max(1, min(MAX_CANDIDATES, int(self.candidates))), bool(self.judge), bool(self.repair), bool(self.mixed),
                            bool(self.gates), bool(self.plan))

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
        for name in ("mixed", "gates", "plan"):
            if getattr(o, name):
                parts += ((name,),)
        return parts

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}
