"""The methods under comparison. Each is the previous idea plus one more, so a row differs from the one above it by one thing."""
from __future__ import annotations

from dataclasses import dataclass

from tutor_core.story_options import StoryOptions


@dataclass(frozen=True)
class Variant:
    name: str
    label: str
    note: str
    range_prompt: bool = False
    two_pass: bool = False
    candidates: int = 1
    judge: bool = False
    repair: bool = False
    proofread: bool = False
    examples: bool = False          # needs the example bank (the database): skipped without --db

    def options(self) -> StoryOptions:
        return StoryOptions(self.candidates, self.judge, self.repair)

    def as_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "note": self.note, "range_prompt": self.range_prompt, "two_pass": self.two_pass,
                "candidates": self.candidates, "judge": self.judge, "repair": self.repair, "proofread": self.proofread, "examples": self.examples}


ALL = [
    Variant("baseline", "Baseline", "today's one-call pipeline"),
    Variant("range", "+ word range", "the prompt asks for a range and names the level", range_prompt=True),
    Variant("two_pass", "+ two passes", "draft without the word list, then adapt it", range_prompt=True, two_pass=True),
    Variant("candidates", "+ 3 candidates", "three adaptations of the draft, best score kept", range_prompt=True, two_pass=True, candidates=3),
    Variant("judge", "+ judge", "a model reviews the best two for grammar", range_prompt=True, two_pass=True, candidates=3, judge=True),
    Variant("repair", "+ repair", "names every missed requirement and rewrites (up to 2 calls)", range_prompt=True, two_pass=True, candidates=3,
            judge=True, repair=True),
    Variant("proofread", "two passes + proofread", "one grammar-fixing call on every story", range_prompt=True, two_pass=True, proofread=True),
    Variant("examples", "+ saved example", "the full set plus an example from the bank (needs --db)", range_prompt=True, two_pass=True, candidates=3,
            judge=True, repair=True, examples=True),
]
DEFAULT = ["baseline", "range", "two_pass", "candidates", "judge", "repair"]
BY_NAME = {v.name: v for v in ALL}


def resolve(spec: str) -> list[Variant]:
    """'default' (the first six), 'all', or names separated by commas. An unknown name is an error that lists the valid ones."""
    spec = (spec or "default").strip().lower()
    names = DEFAULT if spec == "default" else [v.name for v in ALL] if spec == "all" else [n.strip() for n in spec.split(",") if n.strip()]
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        raise ValueError(f"unknown variant(s) {', '.join(unknown)}; choose from {', '.join(BY_NAME)}")
    return [BY_NAME[n] for n in names]


# Rough model calls per story, for the estimate printed before a run (a retry or repair adds more).
CALLS = {"baseline": 1.3, "range": 1.3, "two_pass": 2.3, "candidates": 4.3, "judge": 6.3, "repair": 8.3, "proofread": 3.3, "examples": 8.3}
