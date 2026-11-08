"""The built-in rules, in one registry: language code -> rules. Each rule is a function `rule(ctx) -> [Hit]`; to add a rule, write the
function in the file of its language and add it to that file's RULES. No rule may raise: one that fails is skipped."""
from __future__ import annotations

from typing import Sequence

from . import rules_cjk, rules_common, rules_de, rules_en, rules_romance
from .base import Hit, merge
from .rules_common import make_ctx

REGISTRY: dict = {}
for _code, _rules in rules_common.COMMON.items():
    REGISTRY[_code] = list(_rules)
for _module in (rules_en, rules_romance, rules_de, rules_cjk):
    for _code, _rules in _module.RULES.items():
        REGISTRY.setdefault(_code, []).extend(_rules)


class BuiltinRules:
    name = "rules"

    def check(self, text: str, language: str, words: Sequence[str] = ()) -> list[Hit]:
        rules = REGISTRY.get(language)
        if not rules or not (text or "").strip():
            return []
        ctx = make_ctx(text, language, words)
        found: list[tuple] = []
        for order, rule in enumerate(rules):
            try:
                found.extend((h, order) for h in rule(ctx))
            except Exception:       # noqa: BLE001 - a broken rule must never stop a story from being scored
                continue
        # where two rules name the same words, the one with a certain fix wins, then the one listed first ("la ami" is "l'ami")
        found.sort(key=lambda pair: (pair[0].start, not pair[0].certain, pair[1]))
        return merge([h for h, _ in found])


def builtin_hits(text: str, language: str, words: Sequence[str] = ()) -> list[Hit]:
    return BuiltinRules().check(text, language, words)
