"""Spanish, French, Italian and Portuguese: an article that does not fit its noun, a pronoun with the wrong verb form, and a few fixed
mistakes (de el, di il, a missing ¿). The article check needs the noun in lexicon.py; an unknown noun is never flagged."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .base import sentence_spans
from .lexicon import NOUNS
from .rules_common import Ctx, hit

_NONE = None


@dataclass(frozen=True)
class Spec:
    dets: dict                                   # word -> (gender or None, number or None)
    plural: Callable[[str], list]                # singular noun -> its plural spellings ([] when not sure)
    swap: dict = field(default_factory=dict)     # word -> {"m": the masculine form, "f": the feminine form}
    skip: Callable[[str, str, str], bool] = lambda det, noun, gender: False
    pronouns: frozenset = frozenset()            # dets that are also object pronouns ("la" in "je la vois"), ...
    homographs: frozenset = frozenset()          # ... and nouns that are also a verb form ("il le porte"): such a pair is not judged
    rephrase: Callable = None                    # (det, noun, gender the noun has) -> the corrected phrase, for a language whose article
                                                 # depends on the sound that follows (Italian il / lo / l'); None: use `swap`


def _pairs(*rows) -> dict:
    out = {}
    for m, f in rows:
        out[m], out[f] = {"m": m, "f": f}, {"m": m, "f": f}
    return out


# --- plurals ------------------------------------------------------------------------------------------------------------------------

def plural_es(n: str) -> list:
    if n.endswith("z"):
        return [n[:-1] + "ces"]
    if n[-1] in "aeiouáéíóú":
        return [n + "s"]
    for old, new in (("ón", "ones"), ("ín", "ines"), ("ús", "uses")):
        if n.endswith(old):
            return [n[:-2] + new]
    return [n + "es"] if n[-1] in "lrdnj" else []


def plural_fr(n: str) -> list:
    if n.endswith(("s", "x", "z")):
        return []
    if n.endswith("eau"):
        return [n + "x"]
    if n.endswith("al"):
        return [n[:-2] + "aux"]
    return [n + "s"]


_PT_IRREGULAR = {"pão": "pães", "mão": "mãos", "avião": "aviões", "lição": "lições", "estação": "estações", "país": "países", "mês": "meses",
                 "hotel": "hotéis", "jardim": "jardins", "trem": "trens"}


def plural_pt(n: str) -> list:
    if n in _PT_IRREGULAR:
        return [_PT_IRREGULAR[n]]
    if n[-1] in "aeiouáéíóú":
        return [n + "s"]
    return [n + "es"] if n[-1] in "rz" else []


def plural_none(n: str) -> list:
    return []


# --- the four languages -------------------------------------------------------------------------------------------------------------

ES = Spec(
    dets={"el": ("m", "sg"), "la": ("f", "sg"), "los": ("m", "pl"), "las": ("f", "pl"), "un": ("m", "sg"), "una": ("f", "sg"),
          "unos": ("m", "pl"), "unas": ("f", "pl"), "del": ("m", "sg"), "al": ("m", "sg"), "este": ("m", "sg"), "esta": ("f", "sg"),
          "estos": ("m", "pl"), "estas": ("f", "pl"), "ese": ("m", "sg"), "esa": ("f", "sg"), "esos": ("m", "pl"), "esas": ("f", "pl"),
          "aquel": ("m", "sg"), "aquella": ("f", "sg"), "otro": ("m", "sg"), "otra": ("f", "sg"), "otros": ("m", "pl"), "otras": ("f", "pl"),
          "todos": ("m", "pl"), "todas": ("f", "pl"), "muchos": ("m", "pl"), "muchas": ("f", "pl"), "mucho": ("m", "sg"), "mucha": ("f", "sg"),
          "algunos": ("m", "pl"), "algunas": ("f", "pl"), "mis": (_NONE, "pl"), "tus": (_NONE, "pl"), "sus": (_NONE, "pl"),
          "mi": (_NONE, "sg"), "tu": (_NONE, "sg"), "su": (_NONE, "sg")},
    plural=plural_es,
    swap={**_pairs(("el", "la"), ("un", "una"), ("los", "las"), ("unos", "unas"), ("este", "esta"), ("estos", "estas"), ("ese", "esa"),
                   ("esos", "esas"), ("otro", "otra"), ("otros", "otras"), ("todos", "todas"), ("muchos", "muchas"), ("mucho", "mucha"),
                   ("algunos", "algunas")), "del": {"m": "del", "f": "de la"}, "al": {"m": "al", "f": "a la"}},
    pronouns=frozenset({"la", "las", "los"}),
    homographs=frozenset({"regalo", "cena", "casa", "trabajo", "desayuno", "almuerzo", "pregunta", "cocina", "viaje"}),
)

FR = Spec(
    dets={"le": ("m", "sg"), "la": ("f", "sg"), "un": ("m", "sg"), "une": ("f", "sg"), "du": ("m", "sg"), "au": ("m", "sg"),
          "ce": ("m", "sg"), "cet": ("m", "sg"), "cette": ("f", "sg"), "mon": ("m", "sg"), "ton": ("m", "sg"), "son": ("m", "sg"),
          "ma": ("f", "sg"), "ta": ("f", "sg"), "sa": ("f", "sg"), "les": (_NONE, "pl"), "des": (_NONE, "pl"), "ces": (_NONE, "pl"),
          "mes": (_NONE, "pl"), "tes": (_NONE, "pl"), "ses": (_NONE, "pl"), "nos": (_NONE, "pl"), "vos": (_NONE, "pl"),
          "leurs": (_NONE, "pl"), "aux": (_NONE, "pl"), "quelques": (_NONE, "pl"), "plusieurs": (_NONE, "pl"),
          "notre": (_NONE, "sg"), "votre": (_NONE, "sg"), "leur": (_NONE, "sg"), "chaque": (_NONE, "sg")},
    plural=plural_fr,
    swap={**_pairs(("le", "la"), ("un", "une"), ("ce", "cette"), ("mon", "ma"), ("ton", "ta"), ("son", "sa")),
          "du": {"m": "du", "f": "de la"}, "au": {"m": "au", "f": "à la"}},
    skip=lambda det, noun, gender: det in ("mon", "ton", "son") and gender == "f" and _elides(noun),
    pronouns=frozenset({"le", "la", "les"}),
    homographs=frozenset({"porte", "cuisine", "place", "fête", "classe", "question", "gare"}),
)

_IT_FAMILY = {"il": "the", "lo": "the", "la": "the", "un": "a", "uno": "a", "una": "a", "del": "of", "dello": "of", "della": "of",
              "al": "to", "allo": "to", "alla": "to", "dal": "from", "dallo": "from", "dalla": "from", "nel": "in", "nello": "in",
              "nella": "in", "sul": "on", "sullo": "on", "sulla": "on", "questo": "this", "questa": "this", "quel": "that", "quella": "that"}
# (masculine, masculine before z / gn / ps / x / y / s + consonant, masculine before a vowel, feminine, feminine before a vowel)
_IT_FORMS = {"the": ("il", "lo", "l'", "la", "l'"), "a": ("un", "uno", "un", "una", "un'"), "of": ("del", "dello", "dell'", "della", "dell'"),
             "to": ("al", "allo", "all'", "alla", "all'"), "from": ("dal", "dallo", "dall'", "dalla", "dall'"),
             "in": ("nel", "nello", "nell'", "nella", "nell'"), "on": ("sul", "sullo", "sull'", "sulla", "sull'"),
             "this": ("questo", "questo", "quest'", "questa", "quest'"), "that": ("quel", "quello", "quell'", "quella", "quell'")}
_IT_IMPURE = re.compile(r"^(z|gn|ps|x|y|s[^aeiouàèéìòù\W])", re.I)


def _it_phrase(det: str, noun: str, gender: str):
    """"la libro" is "il libro", "il casa" is "la casa": the form depends on the sound the noun starts with."""
    family = _IT_FAMILY.get(det)
    if family is None:
        return None
    vowel = noun[:1].casefold() in "aeiouàèéìòù"
    forms = _IT_FORMS[family]
    if gender == "f":
        word = forms[4] if vowel else forms[3]
    else:
        word = forms[2] if vowel else forms[1] if _IT_IMPURE.match(noun) else forms[0]
    return word + noun if word.endswith("'") else f"{word} {noun}"


IT = Spec(
    dets={"il": ("m", "sg"), "lo": ("m", "sg"), "un": ("m", "sg"), "uno": ("m", "sg"), "la": ("f", "sg"), "una": ("f", "sg"),
          "i": ("m", "pl"), "gli": ("m", "pl"), "le": ("f", "pl"), "del": ("m", "sg"), "dello": ("m", "sg"), "della": ("f", "sg"),
          "al": ("m", "sg"), "allo": ("m", "sg"), "alla": ("f", "sg"), "dal": ("m", "sg"), "dallo": ("m", "sg"), "dalla": ("f", "sg"),
          "nel": ("m", "sg"), "nello": ("m", "sg"), "nella": ("f", "sg"), "sul": ("m", "sg"), "sullo": ("m", "sg"), "sulla": ("f", "sg"),
          "dei": ("m", "pl"), "degli": ("m", "pl"), "delle": ("f", "pl"), "questo": ("m", "sg"), "questa": ("f", "sg"), "quel": ("m", "sg"),
          "quella": ("f", "sg")},
    plural=plural_none,
    swap={**_pairs(("il", "la"), ("lo", "la"), ("un", "una"), ("uno", "una"), ("del", "della"), ("dello", "della"), ("al", "alla"),
                   ("allo", "alla"), ("dal", "dalla"), ("nel", "nella"), ("sul", "sulla"), ("questo", "questa"), ("quel", "quella"))},
    pronouns=frozenset({"lo", "la", "le", "gli"}),
    homographs=frozenset({"porta", "cucina", "lavoro"}),
    rephrase=_it_phrase,
)

PT = Spec(
    dets={"o": ("m", "sg"), "a": ("f", "sg"), "os": ("m", "pl"), "as": ("f", "pl"), "um": ("m", "sg"), "uma": ("f", "sg"),
          "uns": ("m", "pl"), "umas": ("f", "pl"), "do": ("m", "sg"), "da": ("f", "sg"), "dos": ("m", "pl"), "das": ("f", "pl"),
          "ao": ("m", "sg"), "à": ("f", "sg"), "aos": ("m", "pl"), "às": ("f", "pl"), "no": ("m", "sg"), "na": ("f", "sg"),
          "nos": ("m", "pl"), "nas": ("f", "pl"), "pelo": ("m", "sg"), "pela": ("f", "sg"), "pelos": ("m", "pl"), "pelas": ("f", "pl"),
          "este": ("m", "sg"), "esta": ("f", "sg"), "esse": ("m", "sg"), "essa": ("f", "sg"), "aquele": ("m", "sg"), "aquela": ("f", "sg")},
    plural=plural_pt,
    swap=_pairs(("o", "a"), ("um", "uma"), ("os", "as"), ("uns", "umas"), ("do", "da"), ("dos", "das"), ("ao", "à"), ("aos", "às"),
                ("no", "na"), ("nos", "nas"), ("pelo", "pela"), ("pelos", "pelas"), ("este", "esta"), ("esse", "essa"), ("aquele", "aquela")),
    # "a" is also the preposition ("a pé", "a lápis"): only an article before a feminine singular noun is judged
    skip=lambda det, noun, gender: det == "a" and gender != "f",
    pronouns=frozenset({"o", "a", "os", "as"}),
    homographs=frozenset({"cozinha", "casa", "pergunta", "trabalho", "presente", "resposta"}),
)

SPECS = {"es": ES, "fr": FR, "it": IT, "pt": PT}
_PLURAL_INDEX: dict = {}


def _plural_index(code: str) -> dict:
    if code not in _PLURAL_INDEX:
        spec, index = SPECS[code], {}
        for noun in NOUNS[code]:
            for form in spec.plural(noun):
                if form not in NOUNS[code]:
                    index.setdefault(form, noun)
        _PLURAL_INDEX[code] = index
    return _PLURAL_INDEX[code]


_VOWELS = "aeiouyàâäéèêëîïôöùûüœæ"
_MUTE_H = frozenset({"homme", "hôtel", "histoire", "heure"})


def _elides(noun: str) -> bool:
    return noun[0] in _VOWELS or noun in _MUTE_H


def _sentence_initial(ctx: Ctx, i: int) -> bool:
    """Token i opens a sentence or a line (an object pronoun never does, so "La porte est ouverte" has an article)."""
    before = ctx.text[:ctx.tokens[i].start].rstrip(" \t\"'“‘«¿¡(—–-")
    return not before or before[-1] in ".!?:…\n"


def article_noun(ctx: Ctx) -> list:
    """The article, demonstrative or quantity word right before a known noun must match its gender and number."""
    code = ctx.language
    spec, nouns, plurals = SPECS[code], NOUNS[code], _plural_index(code)
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        det = spec.dets.get(t.low)
        if det is None or not ctx.adjacent(i):
            continue
        n = ctx.tokens[i + 1]
        lemma, number = (n.low, "sg") if n.low in nouns else ((plurals[n.low], "pl") if n.low in plurals else (None, None))
        if lemma is None:
            continue
        gender = nouns[lemma]
        if spec.skip(t.low, lemma, gender) or (t.low in spec.pronouns and lemma in spec.homographs and not _sentence_initial(ctx, i)):
            continue
        det_gender, det_number = det
        wrong = []
        if det_gender and det_gender != gender:
            wrong.append("gender")
        if det_number and det_number != number:
            wrong.append("number")
        if not wrong:
            continue
        fix, note = "", f'"{n.text}" is {"masculine" if gender == "m" else "feminine"} {"plural" if number == "pl" else "singular"}'
        if wrong == ["gender"]:
            if spec.rephrase:
                phrase = spec.rephrase(t.low, n.text, gender)
            else:
                phrase = f"{spec.swap[t.low][gender]} {n.text}" if t.low in spec.swap else None
            if phrase:
                fix = phrase[0].upper() + phrase[1:] if t.text[0].isupper() else phrase
        out.append(hit(ctx, "article_noun", t.start, n.end, fix, False, note + f" ({' and '.join(wrong)} does not match)"))
    return out


def fr_elision(ctx: Ctx) -> list:
    """le or la before a vowel (l'ami), ce before a vowel (cet ami) and cet before a consonant (ce livre)."""
    nouns = NOUNS["fr"]
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if t.low not in ("le", "la", "ce", "cet") or not ctx.adjacent(i):
            continue
        n = ctx.tokens[i + 1]
        if n.low not in nouns:
            continue
        gender, elide = nouns[n.low], _elides(n.low)
        if t.low in ("le", "la") and elide:
            out.append(hit(ctx, "elision", t.start, n.end, ("L'" if t.text[0].isupper() else "l'") + n.text, True, f"{t.text} becomes l' before a vowel"))
        elif t.low == "ce" and gender == "m" and elide:
            out.append(hit(ctx, "ce_cet", t.start, t.end, "Cet" if t.text[0].isupper() else "cet", True, '"cet" before a vowel'))
        elif t.low == "cet" and gender == "m" and not elide:
            out.append(hit(ctx, "ce_cet", t.start, t.end, "Ce" if t.text[0].isupper() else "ce", True, '"ce" before a consonant'))
    return out


# --- a subject pronoun and a verb form that do not go together ------------------------------------------------------------------------

_PERSONS = {
    "es": ({"yo": "1s", "tú": "2s", "él": "3s", "ella": "3s", "usted": "3s", "nosotros": "1p", "nosotras": "1p", "vosotros": "2p",
            "vosotras": "2p", "ellos": "3p", "ellas": "3p", "ustedes": "3p"},
           {"ser": "soy eres es somos sois son", "estar": "estoy estás está estamos estáis están",
            "tener": "tengo tienes tiene tenemos tenéis tienen", "ir": "voy vas va vamos vais van",
            "hacer": "hago haces hace hacemos hacéis hacen"},
           frozenset({"y", "e", "o", "u", "ni", "para", "por", "a", "con", "de", "en", "sin", "entre", "según", "hasta", "desde", "sobre",
                      "ante", "contra", "como", "que"})),
    "fr": ({"je": "1s", "tu": "2s", "il": "3s", "elle": "3s", "on": "3s", "ils": "3p", "elles": "3p"},
           {"être": "- es est sommes êtes sont", "avoir": "ai as a avons avez ont", "aller": "vais vas va allons allez vont",
            "faire": "- - fait faisons faites font"},
           frozenset({"et", "ou", "pour", "avec", "sans", "chez", "de", "à", "entre", "par", "que", "qui", "ne"})),
    "it": ({"io": "1s", "tu": "2s", "lui": "3s", "lei": "3s", "egli": "3s", "noi": "1p", "voi": "2p", "loro": "3p"},
           {"essere": "sono sei è siamo siete sono", "avere": "ho hai ha abbiamo avete hanno", "andare": "vado vai va andiamo andate vanno",
            "fare": "faccio fai fa facciamo fate fanno"},
           frozenset({"e", "o", "per", "a", "con", "da", "di", "in", "su", "tra", "fra", "senza", "secondo", "come", "che", "anche"})),
    "pt": ({"eu": "1s", "tu": "2s", "ele": "3s", "ela": "3s", "você": "3s", "nós": "1p", "vocês": "3p", "eles": "3p", "elas": "3p"},
           {"ser": "sou és é somos - são", "estar": "estou estás está estamos - estão", "ter": "tenho tens tem temos - têm",
            "ir": "vou vais vai vamos - vão", "fazer": "faço fazes faz fazemos - fazem"},
           frozenset({"e", "ou", "para", "por", "a", "com", "de", "em", "sem", "entre", "até", "desde", "sobre", "como", "que", "também"})),
    "de": ({"ich": "1s", "du": "2s", "er": "3s", "wir": "1p", "ihr": "2p"},
           {"sein": "bin bist ist sind seid", "haben": "habe hast hat haben habt"}, frozenset()),
}
_ORDER = ("1s", "2s", "3s", "1p", "2p", "3p")


def _table(code: str) -> dict:
    """form -> (persons it fits, {person: the form for that person}, lemma)"""
    forms = {}
    for lemma, row in _PERSONS[code][1].items():
        cells = row.split()
        by_person = {}
        if code == "de":
            by_person = {"1s": cells[0], "2s": cells[1], "3s": cells[2], "1p": cells[3], "2p": cells[4]}
            by_person["3p"] = cells[3]
        else:
            for person, form in zip(_ORDER, cells + ["-"] * (6 - len(cells))):
                if form != "-":
                    by_person[person] = form
        for person, form in by_person.items():
            entry = forms.setdefault(form, (set(), by_person, lemma))
            entry[0].add(person)
    return forms


_TABLES: dict = {}


def pronoun_verb(ctx: Ctx) -> list:
    code = ctx.language
    pronouns, _, skip_after = _PERSONS[code]
    table = _TABLES.setdefault(code, _table(code))
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        person = pronouns.get(t.low)
        if person is None or not ctx.adjacent(i):
            continue
        if ctx.prev(i) in skip_after:
            continue
        n = ctx.tokens[i + 1]
        entry = table.get(n.low)
        if entry is None or person in entry[0]:
            continue
        right = entry[1].get(person)
        fix = f"{t.text} {right}" if right else ""
        out.append(hit(ctx, "pronoun_verb", t.start, n.end, fix, False, f'"{t.text}" does not go with "{n.text}"'))
    if code == "de":
        out += _german_verb_first(ctx, table)
    return out


def _german_verb_first(ctx: Ctx, table: dict) -> list:
    """"bin du", "ist ich": a form of sein or haben followed by ich, du, er or wir. (ihr and es are left alone: they can be objects.)"""
    persons = {"ich": "1s", "du": "2s", "er": "3s", "wir": "1p"}
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        entry = table.get(t.low)
        n = ctx.tokens[i + 1]
        if entry is None or n.low not in persons or not ctx.adjacent(i) or persons[n.low] in entry[0]:
            continue
        right = entry[1].get(persons[n.low])
        out.append(hit(ctx, "pronoun_verb", t.start, n.end, f"{right} {n.text}" if right else "", False, f'"{t.text}" does not go with "{n.text}"'))
    return out


# --- fixed mistakes ------------------------------------------------------------------------------------------------------------------

def es_contraction(ctx: Ctx) -> list:
    """"de el" is "del" and "a el" is "al" (the pronoun is written "él", with an accent)."""
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if t.low in ("de", "a") and ctx.tokens[i + 1].text == "el" and ctx.adjacent(i):
            n = ctx.tokens[i + 1]
            out.append(hit(ctx, "contraction", t.start, n.end, ("del" if t.low == "de" else "al"), True, f'"{t.low} el" is written as one word'))
    return out


def es_inverted_marks(ctx: Ctx) -> list:
    """A Spanish question or exclamation opens with ¿ or ¡ as well as closing with ? or !"""
    out = []
    for a, b in sentence_spans(ctx.text):
        seg = ctx.text[a:b]
        for close, opening in (("?", "¿"), ("!", "¡")):
            if close in seg and opening not in seg:
                at = a + seg.index(close)
                out.append(hit(ctx, "inverted_mark", at, at + 1, "", False, f'a Spanish sentence with "{close}" also needs "{opening}"'))
            elif opening in seg and close not in seg:
                at = a + seg.index(opening)
                out.append(hit(ctx, "inverted_mark", at, at + 1, "", False, f'"{opening}" without a closing "{close}"'))
    return out


def es_comparative(ctx: Ctx) -> list:
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        if t.low in ("más", "muy") and ctx.tokens[i + 1].low in ("mejor", "peor") and ctx.adjacent(i):
            n = ctx.tokens[i + 1]
            out.append(hit(ctx, "comparative", t.start, n.end, f"mucho {n.text}" if t.low == "muy" else n.text, False, '"mejor" and "peor" are already comparatives'))
    return out


_IT_CONTRACTIONS = {}
for _prep, _forms in {"di": ("del", "dei", "degli", "della", "delle", "dello"), "a": ("al", "ai", "agli", "alla", "alle", "allo"),
                      "da": ("dal", "dai", "dagli", "dalla", "dalle", "dallo"), "in": ("nel", "nei", "negli", "nella", "nelle", "nello"),
                      "su": ("sul", "sui", "sugli", "sulla", "sulle", "sullo")}.items():
    for _article, _form in zip(("il", "i", "gli", "la", "le", "lo"), _forms):
        _IT_CONTRACTIONS[(_prep, _article)] = _form


def it_contraction(ctx: Ctx) -> list:
    """"di il" is "del", "a la" is "alla", "in i" is "nei": a preposition and the article after it are written as one word. (After one of
    these prepositions il, i, gli, la, le and lo are only articles, never pronouns, so this is never a false alarm.)"""
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        n = ctx.tokens[i + 1]
        fix = _IT_CONTRACTIONS.get((t.low, n.low))
        if fix and ctx.adjacent(i):
            out.append(hit(ctx, "contraction", t.start, n.end, fix.capitalize() if t.text[0].isupper() else fix, True,
                           f'"{t.low} {n.low}" is written as one word'))
    return out


def pt_contraction(ctx: Ctx) -> list:
    """"em a casa" is "na casa": em and the article are written as one word. (de, a and por are left alone: "tem de o fazer" is correct,
    because there o is a pronoun.)"""
    fixes = {"o": "no", "a": "na", "os": "nos", "as": "nas"}
    out = []
    for i, t in enumerate(ctx.tokens[:-1]):
        n = ctx.tokens[i + 1]
        if t.low == "em" and n.low in fixes and ctx.adjacent(i):
            out.append(hit(ctx, "contraction", t.start, n.end, fixes[n.low], True, f'"em {n.low}" is written as one word'))
    return out


RULES = {
    "es": [article_noun, pronoun_verb, es_contraction, es_inverted_marks, es_comparative],
    "fr": [fr_elision, article_noun, pronoun_verb],         # elision first: "la ami" is "l'ami", not "le ami"
    "it": [article_noun, pronoun_verb, it_contraction],
    "pt": [article_noun, pronoun_verb, pt_contraction],
}
