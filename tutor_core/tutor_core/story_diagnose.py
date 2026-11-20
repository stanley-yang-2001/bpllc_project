"""Free checks for stories that read stiff (20 Nov 2026). No model call.

The 19 Nov round: after review and repair almost every remaining failure is a naturalness rating of 2 or less, and the written reasons are about rhythm and repetition. Four
things a program can see, and which went with a lower rating in the 150 English stories of that round (mean rating with / without the finding):

    flat_rhythm    every sentence about the same length (population SD of the sentence length below 1.0 word)     2.96 / 3.15
    same_opener    one first word on at least 35% of the sentences (and at least 3)                                2.87 / 3.16
    filler         time words ("today", "now", "then") ending 2 or more sentences, or 3 or more in all           2.77 / 3.18
    one_per_line   80% or more of the sentences on their own line (not for a dialogue)                           2.98 / 3.33

Stories with 0 findings averaged 3.42, with 1 3.38, with 2 3.04, with 3 or more 2.82 (13, 25, 52 and 60 stories). Within one request the sentence-length SD goes with the rating
(r 0.49, +0.26 rating per SD). These are correlations over 30 requests: a finding marks a weak story, it does not prove that removing it makes the story better, which is what
the `v2` and `v2_directive` test methods measure.

`one_per_line` is in 124 of the 150 stories, so it hardly separates one story from another and does not count towards the repair trigger (`actionable`).
Chinese and Japanese (no spaces between words) are not checked: a sentence is not counted in words there. The filler list exists for English, Spanish, French and German only; for
another language the filler check is simply off. The first version of these checks came from the naturalness plan of 19 Nov (repair_tools.py); this one counts words with the same
rule as the rest of the code and keeps a learner's own word out of the filler check, because a word the learner is studying is not filler."""
from __future__ import annotations

import re
import statistics as st
from collections import Counter
from typing import Iterable, Optional

from .difficulty import is_unspaced

FILLER = {
    "en": {"today", "now", "then", "later", "suddenly", "again", "still"},
    "es": {"hoy", "ahora", "luego", "después", "entonces", "todavía"},
    "fr": {"aujourd'hui", "maintenant", "puis", "ensuite", "alors", "encore", "soudain"},
    "de": {"heute", "jetzt", "dann", "später", "gerade", "hier", "wieder", "plötzlich"},
}
CONNECTORS = {
    "en": "and, but, because, so, when, while, after",
    "es": "y, pero, porque, así que, cuando, mientras, después de",
    "fr": "et, mais, parce que, alors, quand, pendant que, après",
    "de": "und, aber, weil, also, als, während, nachdem",
}
FLAT_SD = 1.0              # a population SD of the sentence length below this is flat
OPENER_SHARE = 0.35
MIN_SENTENCES = 6          # a shorter text has no rhythm to judge
MERGE_LIMIT = 20           # two neighbours are offered for joining only when together they stay at 20 words or less (the score caps a sentence there)
REPAIR_AT = 2              # the directive repair starts from this many actionable findings
LAYOUT = "one_per_line"

_SENT = re.compile(r"(?<=[.!?…])[\"”»“«]?\s+|\n+")
_TOK = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", re.U)


def split(text: str) -> list:
    return [s.strip() for s in _SENT.split(text or "") if s and s.strip()]


def words_of(sentence: str) -> list:
    return _TOK.findall(sentence)


def lengths(text: str) -> list:
    return [len(words_of(s)) for s in split(text)]


def diagnose(text: str, language: str, learner_words: Iterable = (), story_type: Optional[str] = None) -> list:
    """[{"code", "sentences": [1-based numbers], "detail"}] in a fixed order; empty when nothing is worth a repair or the text cannot be judged (too short, or an unspaced language)."""
    if is_unspaced(language):
        return []
    sents = split(text)
    if len(sents) < MIN_SENTENCES:
        return []
    toks = [words_of(s) for s in sents]
    lens = [len(t) for t in toks]
    own = {w.lower().removeprefix("to ") for w in learner_words}
    filler = {w for w in FILLER.get(language, ()) if w not in own}
    out = []

    sd = st.pstdev(lens)
    if sd < FLAT_SD:
        pairs, i = [], 0
        while i < len(lens) - 1:
            if lens[i] + lens[i + 1] <= MERGE_LIMIT:
                pairs.append([i + 1, i + 2])
                i += 2
            else:
                i += 1
        out.append({"code": "flat_rhythm", "sentences": [n for p in pairs[:3] for n in p], "pairs": pairs[:3],
                    "detail": f"sentence length SD {sd:.1f} words (mean {st.mean(lens):.1f})"})

    first = [t[0].lower() for t in toks if t]
    if first:
        word, n = Counter(first).most_common(1)[0]
        if n / len(first) >= OPENER_SHARE and n >= 3:
            out.append({"code": "same_opener", "sentences": [i + 1 for i, t in enumerate(toks) if t and t[0].lower() == word],
                        "detail": f"{n} of {len(first)} sentences start with '{word}'"})

    ends = [i + 1 for i, s in enumerate(sents) if any(s.lower().rstrip(" .!?…\"”»“«").endswith(" " + f) for f in filler)]
    total = sum(1 for t in toks for w in t if w.lower() in filler)
    if len(ends) >= 2 or total >= 3:
        out.append({"code": "filler", "sentences": ends, "detail": f"{total} filler time words, {len(ends)} sentences end on one"})

    lines = [ln for ln in (text or "").split("\n") if ln.strip()]
    if story_type != "dialogue" and len(lines) / len(sents) >= 0.8:
        out.append({"code": LAYOUT, "sentences": [], "detail": f"{len(lines)} lines for {len(sents)} sentences"})
    return out


def actionable(findings: list) -> list:
    """The findings a rewrite can act on and that tell stories apart (the layout one is in almost every story and does not count)."""
    return [f for f in findings if f["code"] != LAYOUT]


def should_repair(findings: list) -> bool:
    return len(actionable(findings)) >= REPAIR_AT


def directives(findings: list, language: str) -> list:
    """Concrete edit instructions, one sentence each, in the language's own connectors and filler words."""
    lines = []
    for f in findings:
        s = ", ".join(map(str, f["sentences"]))
        if f["code"] == "flat_rhythm":
            pairs = ", ".join(f"{a}+{b}" for a, b in f.get("pairs", []))
            lines.append("Every sentence has about the same length. Join these neighbouring sentences with a connector "
                         f"({CONNECTORS.get(language, CONNECTORS['en'])}): {pairs or 'three pairs of short sentences'}. "
                         "Then make one other sentence very short (3 to 5 words). Keep every sentence under 20 words.")
        elif f["code"] == "same_opener":
            lines.append(f"Sentences {s} start with the same word ({f['detail']}). Rewrite at least half of them to start differently "
                         "(a time phrase, a place, an object, a connector), keeping the meaning.")
        elif f["code"] == "filler":
            words = ", ".join(sorted(FILLER.get(language, ())))
            where = f"Sentences {s} end" if s else "Some sentences end"
            lines.append(f"{where} on a filler time word ({words}). Delete it; keep a time word only where the reader needs it, and then put it at the start.")
        elif f["code"] == LAYOUT:
            lines.append("Lay the text out as one or two paragraphs: no line break between sentences of the same paragraph.")
    return lines


def signal(text: str, language: str, learner_words: Iterable = (), story_type: Optional[str] = None) -> Optional[dict]:
    """What the report shows for one story: the findings, and the numbers behind them. None when the text cannot be judged."""
    if is_unspaced(language):
        return None
    sents = split(text)
    if len(sents) < MIN_SENTENCES:
        return None
    lens = [len(words_of(s)) for s in sents]
    first = [t[0].lower() for t in (words_of(s) for s in sents) if t]
    found = diagnose(text, language, learner_words, story_type)
    return {"findings": len(actionable(found)), "codes": [f["code"] for f in found], "sd": round(st.pstdev(lens), 2),
            "opener_share": round(Counter(first).most_common(1)[0][1] / len(first), 2) if first else 0.0, "sentences": len(sents)}
