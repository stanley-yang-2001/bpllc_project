"""English rules: a and an, the lower-case "I", the verb after he, she, it, I, we, you, they, and the verb after did, does, can, will."""
from __future__ import annotations

import re

from .rules_common import Ctx, hit

_SILENT_H = ("hour", "honest", "honor", "honour", "heir")
_CONSONANT_SOUND = re.compile(r"^(uni(v|form|que|on|t|fy|fied|cor|cycl)|use|usu|uti|uro|uri|uku|ubi|ute|unan|euro|eu[cl]|ewe|one|once|ufo|uk\b)")


def _vowel_sound(word: str) -> bool:
    if word.startswith(_SILENT_H):
        return True
    if _CONSONANT_SOUND.match(word):
        return False
    return word[0] in "aeiou"


def a_an(ctx: Ctx) -> list:
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if t.low not in ("a", "an") or not ctx.adjacent(i):
            continue
        n = ctx.tokens[i + 1]
        if len(n.low) < 2 or n.text.isupper() or "'" in n.low:
            continue
        right = "an" if _vowel_sound(n.low) else "a"
        if t.low != right:
            fix = right.capitalize() if t.text[0].isupper() else right
            out.append(hit(ctx, "a_an", t.start, t.end, fix, True, f'"{right}" before "{n.text}"'))
    return out


def lowercase_i(ctx: Ctx) -> list:
    out = []
    for t in ctx.tokens:
        if t.text in ("i", "i'm", "i'll", "i've", "i'd"):
            out.append(hit(ctx, "lowercase_i", t.start, t.end, "I" + t.text[1:], True, 'the pronoun "I" is always a capital'))
    return out


_BASE = frozenset("""go have like want see eat play live work make take come look need love walk write run say know get give find think help buy
drink sleep wake open close start stop watch cook clean wash visit meet speak talk listen ask answer call carry bring sit stand wait wear smile
laugh cry sing dance study learn teach try use show tell feel keep leave turn move pay pick draw drive ride fly swim jump climb fall grow miss
remember forget hope believe wish enjoy bake paint count build""".split())
_IRREGULAR_PAST = {"went": "go", "saw": "see", "ate": "eat", "took": "take", "made": "make", "came": "come", "got": "get", "had": "have",
                   "gave": "give", "said": "say", "knew": "know", "thought": "think", "found": "find", "told": "tell", "felt": "feel",
                   "left": "leave", "bought": "buy", "brought": "bring", "drank": "drink", "ran": "run", "wrote": "write", "spoke": "speak",
                   "began": "begin", "sat": "sit", "stood": "stand"}
_AFTER_THESE_A_BARE_VERB_IS_FINE = frozenset({"do", "does", "did", "will", "would", "can", "could", "shall", "should", "may", "might", "must",
                                              "need", "that", "lest", "let", "make", "makes", "made", "help", "helps", "watch", "see", "hear",
                                              "feel", "have", "get", "keep", "to"})


def _third(verb: str) -> str:
    if verb == "have":
        return "has"
    if verb == "go":
        return "goes"
    if verb.endswith(("s", "x", "z", "ch", "sh")):
        return verb + "es"
    if len(verb) > 2 and verb.endswith("y") and verb[-2] not in "aeiou":
        return verb[:-1] + "ies"
    return verb + "s"


_THIRD_FORMS = {_third(v): v for v in _BASE} | {"does": "do"}


def verb_after_pronoun(ctx: Ctx) -> list:
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if not ctx.adjacent(i):
            continue
        n, before = ctx.tokens[i + 1], ctx.prev(i)
        if t.low in ("he", "she", "it"):
            if n.low in _BASE and before not in _AFTER_THESE_A_BARE_VERB_IS_FINE:
                out.append(hit(ctx, "verb_agreement", t.start, n.end, f"{t.text} {_third(n.low)}", False, "he, she, it take -s on the verb"))
            elif n.low in ("are", "am"):
                out.append(hit(ctx, "verb_agreement", t.start, n.end, f"{t.text} is", False, '"is" after he, she, it'))
            elif n.low in ("don't", "don’t"):
                out.append(hit(ctx, "verb_agreement", t.start, n.end, f"{t.text} doesn't", False, '"doesn\'t" after he, she, it'))
        elif t.low in ("i", "we", "you", "they"):
            if n.low in _THIRD_FORMS or n.low in ("has", "goes", "does"):
                base = _THIRD_FORMS.get(n.low) or {"has": "have", "goes": "go", "does": "do"}[n.low]
                out.append(hit(ctx, "verb_agreement", t.start, n.end, f"{t.text} {base}", False, "no -s on the verb after I, we, you, they"))
            elif n.low == "is":
                out.append(hit(ctx, "verb_agreement", t.start, n.end, f"{t.text} {'am' if t.low == 'i' else 'are'}", False, 'not "is"'))
            elif n.low in ("doesn't", "doesn’t"):
                out.append(hit(ctx, "verb_agreement", t.start, n.end, f"{t.text} don't", False, '"don\'t" after I, we, you, they'))
            elif n.low == "was" and t.low in ("we", "they"):
                out.append(hit(ctx, "verb_agreement", t.start, n.end, f"{t.text} were", False, '"were" after we, they'))
    return out


_AUX = frozenset({"did", "didn't", "didn’t", "does", "doesn't", "doesn’t", "do", "don't", "don’t", "can", "could", "will", "would", "should",
                  "must", "may", "might"})


def verb_after_helper(ctx: Ctx) -> list:
    """"did went", "doesn't likes", "can plays": after did, does, do or a modal the verb stays in its plain form."""
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if t.low not in _AUX or not ctx.adjacent(i):
            continue
        n = ctx.tokens[i + 1]
        base = _IRREGULAR_PAST.get(n.low) or _THIRD_FORMS.get(n.low)
        if base is None and n.low.endswith("ed") and (n.low[:-2] in _BASE or n.low[:-1] in _BASE):
            base = n.low[:-2] if n.low[:-2] in _BASE else n.low[:-1]
        if base:
            out.append(hit(ctx, "after_helper", t.start, n.end, f"{t.text} {base}", False, f'the plain verb "{base}" after "{t.text}"'))
    return out


_PLURALS = frozenset("""friends apples eggs books houses schools shops streets cities families mothers fathers children dogs cats birds trees
flowers cars days""".split())


def article_with_plural(ctx: Ctx) -> list:
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if t.low in ("a", "an", "one", "every", "each", "another") and ctx.adjacent(i):
            n = ctx.tokens[i + 1]
            if n.low in _PLURALS and ctx.text[n.end:n.end + 1] not in ("'", "’"):
                out.append(hit(ctx, "article_plural", t.start, n.end, f"{t.text} {n.low[:-1] if n.low != 'children' else 'child'}", False,
                               f'"{t.text}" needs a singular noun'))
    return out


RULES = {"en": [a_an, lowercase_i, verb_after_pronoun, verb_after_helper, article_with_plural]}
