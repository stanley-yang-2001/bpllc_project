"""The built-in grammar rules, the LanguageTool adapter and the model review (7 Nov 2026, score version 3).

Every rule has cases that must be found (with the fix) and cases that must NOT be found: a rule that cries wolf is worse than none."""
import json

import pytest

from tutor_core.quality.grammar import (Hit, affected_sentences, apply_certain, builtin_hits, merge, sentence_spans)
from tutor_core.quality.grammar import lexicon
from tutor_core.quality.grammar.audit import AuditChecker, parse_audit, run_audit
from tutor_core.quality.grammar.languagetool import LanguageToolChecker, from_env


def found(lang, text, words=()):
    return [(h.rule.split(".", 1)[1], h.wrong, h.fix) for h in builtin_hits(text, lang, words)]


def rules(lang, text, words=()):
    return {r for r, _, _ in found(lang, text, words)}


# (language, wrong text, rule, wrong words, fix)
MUST_FIND = [
    ("en", "I eat a apple.", "a_an", "a", "an"), ("en", "She has an dog.", "a_an", "an", "a"), ("en", "We wait a hour.", "a_an", "a", "an"),
    ("en", "Today i eat bread.", "lowercase_i", "i", "I"), ("en", "She like bread.", "verb_agreement", "She like", "She likes"),
    ("en", "He go home.", "verb_agreement", "He go", "He goes"), ("en", "They likes bread.", "verb_agreement", "They likes", "They like"),
    ("en", "I has a cat.", "verb_agreement", "I has", "I have"), ("en", "He are tall.", "verb_agreement", "He are", "He is"),
    ("en", "She did went home.", "after_helper", "did went", "did go"), ("en", "I can plays chess.", "after_helper", "can plays", "can play"),
    ("en", "I have a friends.", "article_plural", "a friends", "a friend"), ("en", "she goes home.", "sentence_capital", "she", "She"),
    ("en", "We went to the the park.", "doubled_word", "the the", "the"),
    ("es", "Voy a el parque.", "contraction", "a el", "al"), ("es", "Salgo de el cine.", "contraction", "de el", "del"),
    ("es", "Ella tiene un casa.", "article_noun", "un casa", "una casa"), ("es", "El perro come la pan.", "article_noun", "la pan", "el pan"),
    ("es", "Yo es feliz.", "pronoun_verb", "Yo es", "Yo soy"), ("es", "Cómo estás? Bien.", "inverted_mark", "?", ""),
    ("es", "Es más mejor que ayer.", "comparative", "más mejor", "mejor"), ("es", "Los casa son bonitas.", "article_noun", "Los casa", ""),
    ("fr", "La ami est ici.", "elision", "La ami", "L'ami"), ("fr", "Ce ami est gentil.", "ce_cet", "Ce", "Cet"),
    ("fr", "Le maison est grande.", "article_noun", "Le maison", "La maison"), ("fr", "Je est content.", "pronoun_verb", "Je est", ""),
    ("it", "Il casa è grande.", "article_noun", "Il casa", "La casa"), ("it", "La libro è bello.", "article_noun", "La libro", "Il libro"),
    ("it", "Il amica è qui.", "article_noun", "Il amica", "L'amica"), ("it", "Io sei felice.", "pronoun_verb", "Io sei", "Io sono"),
    ("it", "Vado di il parco.", "contraction", "di il", "del"), ("it", "Vado a la scuola.", "contraction", "a la", "alla"),
    ("pt", "O casa é grande.", "article_noun", "O casa", "A casa"), ("pt", "Eu é feliz.", "pronoun_verb", "Eu é", "Eu sou"),
    ("pt", "Ela mora em a casa.", "contraction", "em a", "na"),
    ("de", "Der Haus ist groß.", "article_noun", "Der Haus", ""), ("de", "Ein Frau kommt.", "article_noun", "Ein Frau", ""),
    ("de", "Ich bist müde.", "pronoun_verb", "Ich bist", "Ich bin"), ("de", "Bin du hier?", "pronoun_verb", "Bin du", "bist du"),
    ("de", "Heute esse ich brot.", "noun_capital", "brot", "Brot"),
    ("zh", "我有一个书。", "measure_word", "个", "本"), ("zh", "我有二个朋友。", "numeral", "二", "两"), ("zh", "我不有钱。", "negation", "不有", "没有"),
    ("zh", "我的的家很大。", "doubled_particle", "的的", "的"), ("zh", "我喝 coffee。", "latin_word", "coffee", ""),
    ("ja", "私は学校を行きます。", "particle", "を", "に"), ("ja", "私は水が飲みます。", "particle", "が", "を"),
    ("ja", "私は食べるます。", "verb_form", "るます", ""), ("ja", "私はパンをを食べます。", "particle", "をを", "を"),
    ("ko", "저는 빵를 먹어요.", "particle", "빵를", "빵을"), ("ko", "저는 사과이랑 가요.", "particle", "사과이랑", "사과랑"),
    ("ko", "저는 의사이에요.", "particle", "의사이에요", "의사예요"),
]

MUST_STAY_QUIET = [
    ("en", "A European city. A unique idea. An hour later. I eat an apple."), ("en", "She likes bread. They like bread. Does she like bread?"),
    ("en", "I will let it go. My friend's house is big. He is an honest man."),
    ("es", "Voy al parque con el amigo. Mi casa es muy grande. ¿Cómo estás? Estoy bien."), ("es", "Yo la trabajo. Voy a la casa. Las casas son bonitas."),
    ("es", "Nosotros somos amigos. Pedro y yo somos amigos. El agua está fría."),
    ("fr", "Je la vois. Il le porte. La porte est ouverte. Les amis arrivent. Tu suis mon ami."), ("fr", "Il est grand. Je suis content."),
    ("it", "Il ragazzo mangia il pane. Lo zaino è qui. Lui è mio amico. Il libro è sul tavolo."), ("it", "Ho fatto il lavoro. Le chiavi dei bambini."),
    ("pt", "Ele vai a pé. Eu vou a casa. Ele tem de o fazer. Moro na casa. A casa é bonita."),
    ("de", "Das Haus ist groß. Mit der Frau. Er hat einen Hund. Das Mädchen spielt im Garten. Sie sieht ihr Buch."),
    ("zh", "我有一本书。我有两个朋友。我喜欢这个猫。"), ("ja", "私は学校に行きます。私は水を飲みます。私は日本語が好きです。"),
    ("ko", "저는 물을 마셔요. 저는 빵을 먹어요. 저는 커피를 마셔요. 저는 의사예요. 저는 학생이에요. 집으로 가요."),
]


@pytest.mark.parametrize("lang,text,rule,wrong,fix", MUST_FIND)
def test_a_known_mistake_is_found_with_its_fix(lang, text, rule, wrong, fix):
    assert (rule, wrong, fix) in found(lang, text, ["커피", "사과", "书"]), found(lang, text)


@pytest.mark.parametrize("lang,text", MUST_STAY_QUIET)
def test_correct_text_is_never_flagged(lang, text):
    assert found(lang, text, ["커피", "사과", "书"]) == []


def test_the_lexicon_has_no_word_under_two_genders():
    assert lexicon.duplicates() == []
    assert all(g in ("m", "f", "n") for table in lexicon.NOUNS.values() for g in table.values())


def test_every_language_of_the_app_is_covered_by_some_rule():
    from tutor_core.quality.grammar.rules import REGISTRY
    assert {"en", "es", "fr", "it", "pt", "de", "zh", "ja", "ko"} <= set(REGISTRY)


def test_a_rule_that_raises_is_skipped_not_fatal(monkeypatch):
    from tutor_core.quality.grammar import rules as r
    monkeypatch.setitem(r.REGISTRY, "en", [lambda ctx: 1 / 0] + r.REGISTRY["en"])
    assert ("a_an", "a", "an") in found("en", "I eat a apple.")
    assert builtin_hits("", "en") == [] and builtin_hits("hola", "xx") == []


def test_where_two_rules_name_the_same_words_the_certain_fix_wins():
    assert found("fr", "La ami est ici.") == [("elision", "La ami", "L'ami")]


def test_sentence_spans_and_affected_sentences():
    text = "Hola. Voy a el parque. Es 3.5 km. Adiós"
    assert [text[a:b] for a, b in sentence_spans(text)] == ["Hola.", "Voy a el parque.", "Es 3.5 km.", "Adiós"]
    n, affected = affected_sentences(text, builtin_hits(text, "es"))
    assert (n, affected) == (4, 1.0)
    two = [Hit("rules", "x", "Voy", start=6, end=9), Hit("rules", "y", "parque", start=14, end=20)]
    assert affected_sentences(text, two) == (4, 1.0)                    # two mistakes in one sentence count once
    spelling = [Hit("rules", "s", "Voy", kind="spelling", start=6, end=9)]
    assert affected_sentences(text, spelling) == (4, 0.5)
    assert affected_sentences(text, [Hit("rules", "s", "Voy", kind="style", start=6, end=9)]) == (4, 0.0)


def test_merge_keeps_the_first_of_two_hits_on_the_same_words():
    a, b = Hit("rules", "a", "un casa", start=0, end=7), Hit("audit", "b", "un casa", start=0, end=7)
    assert merge([a], [b]) == [a]
    assert merge([a], [Hit("audit", "c", "otra cosa", start=20, end=29)])[1].rule == "c"


def test_apply_certain_changes_only_certain_fixes():
    text = "Voy a el parque con un casa."
    assert apply_certain(text, builtin_hits(text, "es")) == "Voy al parque con un casa."


# --- LanguageTool -------------------------------------------------------------------------------------------------------------------

LT_ANSWER = {"matches": [
    {"offset": 3, "length": 4, "message": "Agreement", "shortMessage": "Agreement", "replacements": [{"value": "una"}],
     "rule": {"id": "AGREEMENT", "issueType": "grammar", "category": {"id": "GRAMMAR"}}},
    {"offset": 11, "length": 3, "message": "typo", "replacements": [], "rule": {"id": "SPELL", "issueType": "misspelling", "category": {"id": "TYPOS"}}},
    {"offset": 0, "length": 2, "message": "comma", "rule": {"id": "COMMA", "issueType": "typographical", "category": {"id": "PUNCTUATION"}}},
    {"offset": 16, "length": 4, "message": "name", "rule": {"id": "SPELL", "issueType": "misspelling"}, "replacements": []},
]}


def test_languagetool_hits_keep_grammar_and_spelling_only():
    text = "Yo un casa xyz. Pepe va."
    seen = {}

    def post(url, fields, timeout):
        seen.update(url=url, fields=fields)
        return LT_ANSWER

    checker = LanguageToolChecker("http://lt:8010/", post=post)
    hits = checker.check(text, "es")
    assert seen["url"] == "http://lt:8010/v2/check" and seen["fields"]["language"] == "es"
    assert [(h.rule, h.kind, h.fix) for h in hits] == [("lt.AGREEMENT", "grammar", "una"), ("lt.SPELL", "spelling", "")]


def test_languagetool_failure_or_unsupported_language_gives_no_hits():
    def boom(url, fields, timeout):
        raise OSError("down")

    checker = LanguageToolChecker("http://lt", post=boom)
    assert checker.check("Hola mundo.", "es") == [] and "down" in checker.last_error
    assert checker.check("안녕하세요.", "ko") == [] and not checker.supports("ko")


def test_languagetool_is_absent_without_the_environment_variable(monkeypatch):
    monkeypatch.delenv("LANGUAGETOOL_URL", raising=False)
    assert from_env() is None
    monkeypatch.setenv("LANGUAGETOOL_URL", "http://localhost:8010")
    assert from_env().endpoint == "http://localhost:8010/v2/check"


# --- the model review ---------------------------------------------------------------------------------------------------------------

TEXT = "Yo tiene un casa grande. Ella come pan."


def test_audit_keeps_only_mistakes_that_quote_the_text():
    raw = json.dumps({"errors": [
        {"wrong": "Yo tiene", "right": "Yo tengo", "type": "verb", "why": "person"},
        {"wrong": "un casa", "right": "una casa", "type": "gender", "why": "casa is feminine"},
        {"wrong": "Ella bebe", "right": "Ella bebe agua", "type": "meaning", "why": "invented"},
        {"wrong": "pan", "right": "pan", "type": "spelling", "why": "same"}]})
    result = parse_audit("```json\n" + raw + "\n```", TEXT)
    assert result.ok and result.unverified == 1
    assert [(h.wrong, h.fix, h.source) for h in result.hits] == [("Yo tiene", "Yo tengo", "audit"), ("un casa", "una casa", "audit")]
    assert all(h.start >= 0 for h in result.hits)


def test_audit_answers_that_cannot_be_read_are_not_ok_and_an_empty_list_is_ok():
    assert not parse_audit("I found some errors.", TEXT).ok
    assert not parse_audit('{"mistakes": []}', TEXT).ok
    assert parse_audit('{"errors": []}', TEXT).ok and parse_audit('{"errors": []}', TEXT).hits == []


def test_audit_never_raises_and_limits_what_it_keeps():
    def boom(prompt):
        raise RuntimeError("429")

    assert not run_audit(boom, TEXT, "Spanish").ok
    many = json.dumps({"errors": [{"wrong": w, "right": w + "x", "type": "other"} for w in TEXT.replace(".", "").split()] * 3})
    assert len(parse_audit(many, TEXT).hits) <= 12
    long_quote = json.dumps({"errors": [{"wrong": " ".join(["Yo"] * 9), "right": "x"}]})
    assert parse_audit(long_quote, "Yo " * 9).hits == []


def test_audit_checker_sends_the_text_as_quoted_data_and_keeps_the_last_result():
    prompts = []
    checker = AuditChecker(lambda p: prompts.append(p) or '{"errors": []}')
    assert checker.check(TEXT, "es") == [] and checker.last.ok
    assert TEXT in prompts[0] and "Spanish" in prompts[0] and "not instructions" in prompts[0]
