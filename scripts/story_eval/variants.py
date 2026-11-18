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
    plan: bool = False              # name only about one learner word per 17 words, and a maximum (story_plan.py)
    mixed: bool = False             # candidates by different strategies (one-pass and two-pass)
    gates: bool = False             # free pass/fail checks drop failing candidates before any review
    refine: int = 0                 # rounds of check-then-fix-flagged-sentences (story_refine.py)
    naturalness: bool = False       # the judge also rates how natural the best candidates read (1-5)
    rules: bool = False             # writer rules in the prompt: keep every small word, no tacked-on words, no filler (prompts/builder.py)
    story_model: str = None         # alias of the model that writes: "gpt" or "qwen" (None: the default story model)
    judge_model: str = None         # alias of the model that judges (None: the default judge model, else the story model)

    def options(self) -> StoryOptions:
        return StoryOptions(self.candidates, self.judge, self.repair, self.mixed, self.gates, self.plan, self.naturalness, self.refine, self.rules)

    def as_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "note": self.note, "range_prompt": self.range_prompt, "two_pass": self.two_pass,
                "candidates": self.candidates, "judge": self.judge, "repair": self.repair, "proofread": self.proofread, "examples": self.examples,
                "plan": self.plan, "mixed": self.mixed, "gates": self.gates, "naturalness": self.naturalness, "refine": self.refine, "rules": self.rules, "story_model": self.story_model, "judge_model": self.judge_model}


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
# The mixture (8 Nov 2026): who writes and who judges, the same method for all four: range prompt, two passes, 3 candidates, judge.
_MIX = dict(range_prompt=True, two_pass=True, candidates=3, judge=True)
ALL += [
    Variant("baseline_qwen", "Baseline, Qwen writes", "today's one-call pipeline on the Qwen model", story_model="qwen"),
    Variant("gpt_gpt", "GPT writes, GPT judges", "candidates + judge, both on the GPT model", story_model="gpt", judge_model="gpt", **_MIX),
    Variant("qwen_qwen", "Qwen writes, Qwen judges", "candidates + judge, both on the Qwen model", story_model="qwen", judge_model="qwen", **_MIX),
    Variant("gpt_qwen", "GPT writes, Qwen judges", "candidates by GPT, reviewed by Qwen", story_model="gpt", judge_model="qwen", **_MIX),
    Variant("qwen_gpt", "Qwen writes, GPT judges", "candidates by Qwen, reviewed by GPT", story_model="qwen", judge_model="gpt", **_MIX),
]
# The cascade (8 Nov 2026): cheap first. Plan limits the featured words; mixed strategies; free gates drop bad candidates; only the best two are
# reviewed (by the judge model); one repair for what is left; the last variant swaps the repair for one proofreading call.
_CASCADE = dict(range_prompt=True, plan=True, mixed=True, candidates=4, gates=True)
ALL += [
    Variant("plan", "+ plan limits", "the prompt names about one word per 17 and a maximum", range_prompt=True, plan=True),
    Variant("mixed_gates", "+ mixed candidates, gates", "2 one-pass and 2 two-pass candidates, free gates pick (no model review)", **_CASCADE),
    Variant("cascade", "Cascade", "+ the best two reviewed (grammar and naturalness) by the judge, then one repair", judge=True, repair=True, naturalness=True, **_CASCADE),
    Variant("cascade_proofread", "Cascade, proofread", "the cascade with one proofreading call instead of the repair", judge=True, proofread=True, naturalness=True, **_CASCADE),
]
# Cheaper cascades (17 Nov 2026). The 30-request run: the cascade had 22 of 30 stories passed by every reviewer against 11 of 30 for the baseline, at 12.6 calls a story
# against 1.7. In that run its repair changed the story in 15 of 30 and found nothing to fix in 11 (all passed); the plan and the mixed candidates with free checks, without
# a model review, stayed near the baseline. These two separate the cascade's two halves: the choice of the best candidate by a model review, and the repair.
ALL += [
    Variant("cascade_pick", "Cascade without repair", "the cascade's four candidates and the judge's choice of the best, no repair", judge=True, naturalness=True, **_CASCADE),
    Variant("review_repair", "Review, then repair", "one draft (with the plan), a model review for mistakes, one repair: no candidates, no choice", range_prompt=True, plan=True, judge=True,
            repair=True),
]
# Check, then fix only what was found (10 Nov 2026): one-call writer, free checks + model review, sentence-level repair, kept only if the score rises.
ALL += [Variant("refine", "Refine", "one call writes; checks + review; fixes only the flagged sentences (up to 2 rounds, kept only if the score rises)",
                story_model="gpt", judge_model="gpt", refine=2)]
# Writer rules (14 Nov 2026): the same prompt with three added sentences (small words stay, no tacked-on words, no filler), alone and with the refine loop on top.
ALL += [Variant("rules", "+ writer rules", "today's one-call pipeline, the prompt adds: keep every small word, no tacked-on words, no filler", rules=True),
        Variant("rules_refine", "Writer rules + refine", "the writer rules, then the refine loop", story_model="gpt", judge_model="gpt", refine=2, rules=True)]
DEFAULT = ["baseline", "range", "two_pass", "candidates", "judge", "repair"]
WRITER = ["baseline", "rules"]
CASCADE = ["baseline", "plan", "mixed_gates", "cascade", "cascade_proofread"]
ABLATION = ["baseline", "cascade", "review_repair", "cascade_pick"]
MIX = ["baseline", "baseline_qwen", "gpt_gpt", "qwen_qwen", "gpt_qwen", "qwen_gpt"]
BY_NAME = {v.name: v for v in ALL}


def resolve(spec: str) -> list[Variant]:
    """'default' (the first six), 'cascade' (the cascade plan, step by step), 'mix' (GPT and Qwen as writer and judge), 'writer' (baseline and the writer rules), 'ablation' (baseline, the cascade, the cascade without its repair, and a single draft with a review and a repair), 'all', or names separated by commas.
    'cascade' is both a group of five methods and the name of one method: a leading = names the method alone ('baseline,=cascade' is two methods, 'baseline,cascade' is five).
    An unknown name is an error that lists the valid ones."""
    groups = {"default": DEFAULT, "mix": MIX, "cascade": CASCADE, "writer": WRITER, "ablation": ABLATION, "all": [v.name for v in ALL]}
    names = []
    for part in (spec or "default").strip().lower().split(","):
        part = part.strip()
        one = part.startswith("=")
        part = part.lstrip("=").strip()
        for n in ([part] if one and part else groups.get(part, [part] if part else [])):
            if n not in names:
                names.append(n)
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        raise ValueError(f"unknown variant(s) {', '.join(unknown)}; choose from {', '.join(BY_NAME)}")
    return [BY_NAME[n] for n in names]


# Rough model calls per story, for the estimate printed before a run (a retry or repair adds more).
CALLS = {"baseline": 1.3, "range": 1.3, "two_pass": 2.3, "candidates": 4.3, "judge": 6.3, "repair": 8.3, "proofread": 3.3, "examples": 8.3,
         "plan": 1.3, "mixed_gates": 6.3, "cascade": 10.3, "cascade_proofread": 9.3, "cascade_pick": 8.3, "review_repair": 4.3, "refine": 7.3, "rules": 1.3, "rules_refine": 7.3,
         "baseline_qwen": 1.3, "gpt_gpt": 6.3, "qwen_qwen": 6.3, "gpt_qwen": 6.3, "qwen_gpt": 6.3}
