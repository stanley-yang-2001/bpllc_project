"""German: an article, possessive or this/each/which before a known noun must fit its gender, a noun is written with a capital letter, and
a pronoun must fit the form of sein or haben. The article check names a mistake only when the form can never be right for that gender
in the singular, so a case ending (dem, den, des) is not a reason to flag; "der" before a feminine noun can be the dative, so it is left."""
from __future__ import annotations

from .lexicon import NOUNS
from .rules_common import Ctx, hit
from .rules_romance import pronoun_verb

# which genders a form can belong to, in the singular
_ARTICLES = {"der": "m", "den": "m", "dem": "mn", "des": "mn", "die": "f", "das": "n"}
_EIN_ROOTS = ("ein", "kein", "mein", "dein", "sein", "ihr", "unser", "euer")
_EIN_SUFFIX = {"": "mn", "e": "f", "en": "m", "em": "mn", "er": "f", "es": "mn"}
_DIES_ROOTS = ("dies", "jed", "welch")
_DIES_SUFFIX = {"er": "mf", "e": "f", "en": "m", "em": "mn", "es": "mn"}       # dieser: m nominative or f dative; dieses: n, or m/n genitive
_CONTRACTED = {"im": "mn", "am": "mn", "zum": "mn", "vom": "mn", "beim": "mn", "ins": "n", "ans": "n", "aufs": "n", "zur": "f"}


def _can_take(word: str):
    """The genders `word` can go with in the singular, or None when it is not an article-like word."""
    if word in _ARTICLES:
        return _ARTICLES[word]
    if word in _CONTRACTED:
        return _CONTRACTED[word]
    for root in _EIN_ROOTS:
        if word.startswith(root):
            rest = word[len(root):]
            if rest in _EIN_SUFFIX:
                return _EIN_SUFFIX[rest]
    for root in _DIES_ROOTS:
        if word.startswith(root):
            rest = word[len(root):]
            if rest in _DIES_SUFFIX:
                return _DIES_SUFFIX[rest]
    return None


# "ihr" is also "to her" and "sein" is also the verb: never judged. ("der" before a feminine noun is skipped in article_noun: it can be
# the dative or genitive, mit der Frau.)
_NEVER_JUDGED = frozenset({"sein", "ihr"})


def article_noun(ctx: Ctx) -> list:
    nouns = NOUNS["de"]
    lower = {k.casefold(): (k, g) for k, g in nouns.items()}
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if not ctx.adjacent(i) or t.low in _NEVER_JUDGED:
            continue
        n = ctx.tokens[i + 1]
        found = lower.get(n.low)
        if found is None or not n.text[0].isupper():
            continue
        genders = _can_take(t.low)
        if genders is None:
            continue
        gender = found[1]
        if gender in genders:
            continue
        if t.low == "der" and gender == "f":
            continue
        out.append(hit(ctx, "article_noun", t.start, n.end, "", False,
                       f'"{n.text}" is {"masculine" if gender == "m" else "feminine" if gender == "f" else "neuter"}: "{t.text}" does not fit'))
    return out


def noun_capital(ctx: Ctx) -> list:
    """A known noun in the middle of a sentence written with a small letter."""
    lower = {k.casefold(): k for k in NOUNS["de"]}
    out = []
    for i, t in enumerate(ctx.tokens):
        right = lower.get(t.low)
        if right is None or not t.text[0].islower() or i == 0:
            continue
        before = ctx.text[:t.start].rstrip()
        if not before or before[-1] in ".!?:\n":
            continue
        out.append(hit(ctx, "noun_capital", t.start, t.end, right, True, "German nouns are written with a capital letter"))
    return out


RULES = {"de": [article_noun, noun_capital, pronoun_verb]}
