"""Which words are allowed: the learner's list, its regular inflections, grammar words and a few basic verbs."""
from __future__ import annotations

import re

# --- allowed non-vocabulary words ------------------------------------------------------------

GRAMMAR_WORDS = set(
    """
    a an the
    i me my mine myself you your yours yourself he him his she her hers it its we us our ours
    they them their theirs this that these those who whom whose what which
    someone something anyone anything everyone everything nothing nobody
    in on at to of for with without from by about near under over into out up down after before
    between behind through around next beside inside outside
    and but or so because then if than as
    is am are was were be been being have has had having do does did done doing
    can could will would should may might must shall not
    here there now very too also just some any much many more most all each every again still
    where when why how
    """.split()
)

# The prompt names six simple verbs; the prompt's own tone example also uses "say" and the
# like, so a few very basic verbs are allowed by default. strict_verbs=True keeps only the six.
PROMPT_VERBS = ("want", "like", "go", "see")  # is/have are in GRAMMAR_WORDS
EXTRA_BASIC_VERBS = ("say", "give", "get", "take", "come", "need", "ask")

IRREGULAR = {
    "go": {"goes", "went", "gone", "going"},
    "see": {"sees", "saw", "seen", "seeing"},
    "say": {"says", "said", "saying"},
    "give": {"gives", "gave", "given", "giving"},
    "get": {"gets", "got", "gotten", "getting"},
    "take": {"takes", "took", "taken", "taking"},
    "come": {"comes", "came", "coming"},
}

CONTRACTIONS = {
    "i'm", "i'll", "i'd", "i've", "you're", "you'll", "you've", "you'd", "he's", "she's", "it's",
    "we're", "we'll", "we've", "they're", "they'll", "they've", "that's", "there's", "here's",
    "what's", "who's", "let's", "don't", "doesn't", "didn't", "can't", "won't", "isn't",
    "aren't", "wasn't", "weren't", "haven't", "hasn't", "couldn't", "wouldn't", "shouldn't",
}

_TOKEN = re.compile(r"[^\W\d_]+(?:['\-][^\W\d_]+)*")
_LABEL = re.compile(r"^\s*([^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?)\s*:\s+\S")
# Japanese/Chinese sentences end in 。！？ with no space after them, so those split without whitespace.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|(?<=[。！？])\s*|\n+")

_VOWELS = set("aeiou")


def _norm(text):
    return (text or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")


def word_forms(word):
    """The word plus its regular inflections (plural, -ed, -ing, ...). Same root only."""
    w = _norm(word).strip().lower()
    if not w:
        return set()
    forms = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing"}
    if len(w) > 1 and w.endswith("y") and w[-2] not in _VOWELS:
        forms |= {w[:-1] + "ies", w[:-1] + "ied"}
    if w.endswith("e"):
        forms.add(w[:-1] + "ing")
    if len(w) >= 2 and w[-1] not in _VOWELS | {"w", "x", "y"} and w[-2] in _VOWELS:
        forms |= {w + w[-1] + "ed", w + w[-1] + "ing"}
    forms |= IRREGULAR.get(w, set())
    return forms


def _allowed_words(strict_verbs=False, extra=()):
    allowed = set(GRAMMAR_WORDS) | set(CONTRACTIONS)
    verbs = list(PROMPT_VERBS) + ([] if strict_verbs else list(EXTRA_BASIC_VERBS))
    for verb in verbs:
        allowed |= word_forms(verb)
    for w in extra:
        allowed |= word_forms(w)
    for w in ("is", "have", "do", "be"):
        allowed |= word_forms(w)
    return allowed


def parse_vocabulary(vocab):
    """Accepts 'a, b, thank you' or a list. Returns the set of single lowercase words
    (a phrase contributes each of its words)."""
    if vocab is None:
        return set()
    items = re.split(r"[,\n]", vocab) if isinstance(vocab, str) else list(vocab)
    words = set()
    for item in items:
        for token in _TOKEN.findall(_norm(str(item)).lower()):
            words.add(token)
    return words


def _vocab_forms(vocab_words):
    forms = set()
    for w in vocab_words:
        forms |= word_forms(w)
    return forms


def _is_known(token, vocab_forms, allowed):
    """token is lowercase."""
    if token in allowed or token in vocab_forms:
        return True
    if token.endswith("'s") and (token[:-2] in vocab_forms or token[:-2] in allowed):
        return True
    if "-" in token:
        return all(_is_known(part, vocab_forms, allowed) for part in token.split("-") if part)
    return False


