"""
Tests for scripts/vocab_adherence.py — the Step 10 story-quality checker (LO 7).

The checker scores a generated passage against the learner's vocabulary so prompt changes can
be measured instead of guessed at. It encodes the rules the story prompt itself states:
  * words must come from the vocabulary (inflections allowed, same root),
  * basic grammar words and simple verbs (is, have, want, like, go, see) are allowed,
  * character names are allowed,
  * 5-6 short sentences or lines, dialogue lines formatted as "Name: line",
  * no leaked planning text, and never an empty passage.

Written BEFORE the checker. Run now and expect an ImportError; re-run after to confirm green.
No database, no network.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_vocab_adherence.py
"""

import sys

sys.path.insert(0, "/app/scripts")

from vocab_adherence import (  # noqa: E402
    check_passage,
    format_summary,
    language_check,
    parse_vocabulary,
    rescore_results,
    summarize,
    variety_report,
    format_variety,
    word_forms,
)

PASS = "PASS"
FAIL = "FAIL"
failures = []

VOCAB = parse_vocabulary(
    "hello, goodbye, please, thank you, yes, no, water, food, friend, house, today, tomorrow"
)

GOOD_NARRATION = (
    "Hello, I am Sam today. I want water. I see my friend near the house. "
    "I say please, can you give water? My friend says yes and gives water. "
    "I say thank you."
)

GOOD_DIALOGUE = (
    "Anna: Hello, do you have water?\n"
    "Ben: Yes, I have water today.\n"
    "Anna: Please give me water.\n"
    "Ben: Here is water, thank you.\n"
    "Anna: Thank you, goodbye friend."
)


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


# --- vocabulary parsing and word forms -------------------------------------------------------


def test_parse_vocabulary():
    check("comma-separated string is parsed", "water" in parse_vocabulary("hello, water"))
    check("a list is accepted too", "water" in parse_vocabulary(["hello", "Water"]))
    check("case is folded", "water" in parse_vocabulary("Water"))
    check("a phrase contributes each of its words", {"thank", "you"} <= parse_vocabulary("thank you"))
    check("blank entries are ignored", "" not in parse_vocabulary("hello, , water,"))


def test_word_forms():
    forms = word_forms("friend")
    check("plural accepted", "friends" in forms)
    forms = word_forms("want")
    check("-ed and -ing accepted", {"wanted", "wanting", "wants"} <= forms)
    check("consonant-final y -> ies / ied", {"studies", "studied"} <= word_forms("study"))
    check("e-final: -ing and -ed", {"making", "maked"} & word_forms("make") == {"making", "maked"})
    check("doubled final consonant", "stopped" in word_forms("stop") and "running" in word_forms("run"))
    check("the word itself is included", "water" in word_forms("water"))


# --- vocabulary adherence --------------------------------------------------------------------


def test_good_passages_pass():
    r = check_passage(GOOD_NARRATION, VOCAB)
    check("a clean narration has no out-of-vocabulary words", r["oov_words"] == [])
    r = check_passage(GOOD_DIALOGUE, VOCAB)
    check("a clean dialogue has no out-of-vocabulary words", r["oov_words"] == [])


def test_flags_words_outside_the_vocabulary():
    r = check_passage("Hello, I am hungry today. I see a shop with fresh bread.", VOCAB)
    check("content words outside the list are flagged", {"hungry", "shop", "fresh", "bread"} <= set(r["oov_words"]))
    check("vocabulary and grammar words are not flagged", not ({"hello", "today", "i", "am", "see", "a", "with"} & set(r["oov_words"])))


def test_allows_basic_grammar_and_simple_verbs():
    r = check_passage("I want it. We like the house. They go to the house and see my friend.", VOCAB)
    check("articles, pronouns, prepositions, conjunctions, simple verbs are allowed", r["oov_words"] == [])


def test_inflections_are_accepted():
    r = check_passage("My friends wanted houses. I thank my friend.", VOCAB)
    check("plural/-ed forms of vocabulary and simple verbs pass; 'thank' comes from 'thank you'", r["oov_words"] == [])


def test_names_are_ignored():
    r = check_passage("Hello, I am Sam. Sam wants water.", VOCAB)
    check("a name introduced mid-sentence is ignored everywhere in the passage", r["oov_words"] == [])
    r = check_passage(GOOD_DIALOGUE.replace("Anna", "Priya").replace("Ben", "Marcus"), VOCAB)
    check("speaker labels are never counted as words", r["oov_words"] == [])


def test_contractions_and_curly_apostrophes():
    r = check_passage("I’m here. I don't have water. It's my friend's house.", VOCAB)
    check("common contractions and possessives are handled", r["oov_words"] == [])


def test_oov_rate():
    r = check_passage("Hello, I see bread today.", VOCAB)
    check("oov_rate is out-of-vocabulary words / checked words", abs(r["oov_rate"] - 1 / 5) < 1e-9 and r["oov_words"] == ["bread"])


# --- structure -------------------------------------------------------------------------------


def test_style_detection():
    check("dialogue is detected", check_passage(GOOD_DIALOGUE, VOCAB)["style"] == "dialogue")
    check("narration is detected", check_passage(GOOD_NARRATION, VOCAB)["style"] == "narration")


def test_length():
    r = check_passage(GOOD_DIALOGUE, VOCAB)
    check("dialogue unit count = number of lines", r["units"] == 5 and r["length_ok"])
    r = check_passage("Hello. I want water.", VOCAB)
    check("a two-sentence passage is flagged as off-length", r["units"] == 2 and not r["length_ok"])


def test_dialogue_format():
    bad = "Anna: Hello, do you have water?\nYes, I have water today.\nAnna: Please give me water.\nBen: Thank you.\nAnna: Goodbye."
    r = check_passage(bad, VOCAB)
    check("a dialogue line without 'Name:' fails the format check", r["style"] == "dialogue" and not r["format_ok"])
    check("a well-formed dialogue passes the format check", check_passage(GOOD_DIALOGUE, VOCAB)["format_ok"])


def test_leaks():
    leaked = "Character: Sam\nWant: water\n===STORY===\n" + GOOD_NARRATION
    check("planning text / delimiter is flagged as a leak", check_passage(leaked, VOCAB)["leaked_plan"])
    check("a clean passage has no leak", not check_passage(GOOD_NARRATION, VOCAB)["leaked_plan"])


def test_failures_are_classified():
    for text, label in [
        ("", "empty text"),
        ("   \n ", "whitespace"),
        ("I'm having trouble generating a story right now — please try again in a moment.", "fallback message"),
        ("You don't have any vocabulary yet! Add some words first.", "empty-vocabulary message"),
    ]:
        r = check_passage(text, VOCAB)
        check(f"{label} is classified as a failure, not scored as a story", r["failure"] and not r["passed"])


def test_non_english_skips_the_vocabulary_check():
    spanish = (
        "Hola, soy Ana y digo hola.\nHoy tengo sed y quiero agua.\n"
        "Le pregunto a mi amigo si me da agua.\nMi amigo dice si y me da agua.\n"
        "Gracias, bebo y digo nos vemos manana."
    )
    r = check_passage(spanish, VOCAB, check_vocab=False)
    check("vocabulary check is skipped (None) for non-English", r["oov_words"] is None and r["vocab_checked"] is False)
    check("structure is still checked, and a well-formed passage passes", r["units"] == 5 and r["passed"])


def test_strict_verbs():
    check("'give' is allowed by default", check_passage("I give water.", VOCAB)["oov_words"] == [])
    check("strict_verbs keeps only the prompt's own verbs", check_passage("I give water.", VOCAB, strict_verbs=True)["oov_words"] == ["give"])


def test_passed_flag():
    check("clean passage passes overall", check_passage(GOOD_NARRATION, VOCAB)["passed"])
    check("an out-of-vocabulary word fails by default", not check_passage("Hello, I see bread today. I want water. Yes. No. Thank you.", VOCAB)["passed"])
    check("max_oov=1 tolerates a single stray word", check_passage("Hello, I see bread today. I want water. Yes. No. Thank you.", VOCAB, max_oov=1)["passed"])


# --- aggregate summary -----------------------------------------------------------------------


def test_summarize():
    results = [
        check_passage(GOOD_NARRATION, VOCAB),
        check_passage(GOOD_DIALOGUE, VOCAB),
        check_passage("Hello, I see bread today. I want water. Yes. No. Thank you.", VOCAB),
        check_passage("", VOCAB),
    ]
    s = summarize(results)
    check("total counts every attempt", s["total"] == 4)
    check("failures counted separately", s["failures"] == 1)
    check("pass rate is passes / total attempts", abs(s["pass_rate"] - 2 / 4) < 1e-9)
    check("top out-of-vocabulary words are listed", s["top_oov"][0][0] == "bread")
    check("style counts are reported", s["styles"].get("dialogue") == 1 and s["styles"].get("narration", 0) >= 1)


# --- beginner readability: how long are the sentences / lines? --------------------------------


def test_unit_word_metrics():
    r = check_passage(GOOD_DIALOGUE, VOCAB)
    check("dialogue: longest line is 5 words (speaker labels not counted)", r["longest_unit_words"] == 5)
    check("dialogue: mean line length is 4.6 words", abs(r["mean_unit_words"] - 4.6) < 1e-9)
    r = check_passage(GOOD_NARRATION, VOCAB)
    check("narration: longest sentence is 7 words", r["longest_unit_words"] == 7)
    check("narration: mean sentence length is 5.5 words", abs(r["mean_unit_words"] - 5.5) < 1e-9)


def test_max_unit_words_is_optional_and_enforced():
    long_one = (
        "Hello, I am Sam today and I want water and food at my house with my friend. "
        "I see my friend. I say please. My friend says yes. I say thank you."
    )
    check("long sentences do not fail by default", check_passage(long_one, VOCAB)["passed"])
    check("max_unit_words fails a passage with a too-long sentence", not check_passage(long_one, VOCAB, max_unit_words=10)["passed"])
    check("max_unit_words passes a passage within the limit", check_passage(GOOD_NARRATION, VOCAB, max_unit_words=10)["passed"])


# --- re-scoring a saved batch under a different rule (no new generation) ----------------------


def test_rescore_results():
    stray = "Hello, I see bread today. I want water. Yes. No. Thank you."
    data = {
        "vocabulary": "hello, goodbye, please, thank you, yes, no, water, food, friend, house, today, tomorrow",
        "results": {
            "English": [
                {"text": GOOD_NARRATION, "latency": 1.5, "style_requested": "narration"},
                {"text": stray, "latency": 2.5, "style_requested": "narration"},
                {"text": "I'm having trouble generating a story right now — please try again in a moment.", "latency": 9.0},
            ],
            "Spanish": [{"text": "Hola. Quiero agua. Veo a mi amigo. Digo gracias. Adios.", "latency": 1.0}],
        },
    }
    strict = rescore_results(data, max_oov=0)
    relaxed = rescore_results(data, max_oov=2)
    check("strict: the stray-word story fails", [r["passed"] for r in strict["English"]] == [True, False, False])
    check("relaxed (max_oov=2): the stray-word story passes", [r["passed"] for r in relaxed["English"]] == [True, True, False])
    check("latency and text are carried over", relaxed["English"][1]["latency"] == 2.5 and relaxed["English"][1]["text"] == stray)
    check("a saved fallback message is still a failure", relaxed["English"][2]["failure"])
    check("non-English results skip the vocabulary check", relaxed["Spanish"][0]["oov_words"] is None)
    check("summarize works on rescored results", summarize(relaxed["English"])["passes"] == 2)


# --- is the passage actually IN the requested language? (found in the first automated run) -----
# These passages are real outputs from the Step 10 routing run: a "Spanish" story that is English,
# French with English words left in, and a "Japanese" story in English. The structure-only check
# passed all of them.

REAL_VOCAB = "hello, goodbye, please, thank you, yes, no, water, food, friend, house, today, tomorrow, book, biscuit, bread, sunny"

REAL_SPANISH_OK = (
    "Ana: Hola, \u00bftienes agua, por favor?  \nLuis: S\u00ed, tengo agua en mi casa.  \n"
    "Ana: \u00bfPodemos beber agua hoy?  \nLuis: No, hoy no.  \nAna: Entonces ma\u00f1ana, s\u00ed?  \nLuis: S\u00ed, ma\u00f1ana, gracias."
)
REAL_SPANISH_IS_ENGLISH = (
    "Ana: hello, do you have water?  \nLuis: yes, I have water.  \nAna: please, I want water today.  \n"
    "Luis: no, I need water today.  \nAna: okay, tomorrow then?  \nLuis: yes, I bring water tomorrow, thank you."
)
REAL_FRENCH_MIXED = (
    "Bonjour, je suis L\u00e9a today.  \nJ'ai soif et je veux water.  \nJe demande \u00e0 ami please water.  \n"
    "Il dit oui et me donne water.  \nJe dis thank you et bois water.  \nTomorrow je aiderai ami gentil."
)
REAL_JAPANESE_IS_ENGLISH = (
    "Hello, I am Taro today. I want water. My friend is nearby. I say, please water. "
    "Friend says yes and has water. Thank you, we will drink tomorrow."
)
GOOD_FRENCH = (
    "Bonjour, je suis L\u00e9a.\nJ'ai soif et je veux de l'eau.\nJe demande de l'eau \u00e0 mon ami.\n"
    "Il dit oui et me donne de l'eau.\nMerci, je bois et je dis \u00e0 demain."
)
GOOD_JAPANESE = "\u3053\u3093\u306b\u3061\u306f\u3001\u79c1\u306f\u30b5\u30e0\u3067\u3059\u3002\n\u4eca\u65e5\u306f\u6c34\u304c\u307b\u3057\u3044\u3067\u3059\u3002\n\u53cb\u9054\u306b\u4f1a\u3044\u307e\u3059\u3002\n\u53cb\u9054\u306f\u6c34\u3092\u304f\u308c\u307e\u3059\u3002\n\u3042\u308a\u304c\u3068\u3046\u3001\u3055\u3088\u3046\u306a\u3089\u3002"


def test_language_check_real_outputs():
    check("a real Spanish story passes", language_check(REAL_SPANISH_OK, "Spanish", REAL_VOCAB)["ok"])
    r = language_check(REAL_SPANISH_IS_ENGLISH, "Spanish", REAL_VOCAB)
    check("a 'Spanish' story written in English is caught", not r["ok"] and r["verdict"] == "english")
    r = language_check(REAL_FRENCH_MIXED, "French", REAL_VOCAB)
    check("French with English words left in is caught as mixed", not r["ok"] and r["verdict"] in ("mixed", "english"))
    check("fully French text passes", language_check(GOOD_FRENCH, "French", REAL_VOCAB)["ok"])
    r = language_check(REAL_JAPANESE_IS_ENGLISH, "\u65e5\u672c\u8a9e", REAL_VOCAB)
    check("a 'Japanese' story written in English is caught (wrong script)", not r["ok"] and r["verdict"] == "wrong_script")
    check("real Japanese passes, whether asked for as 'Japanese' or by its own name",
          language_check(GOOD_JAPANESE, "Japanese", REAL_VOCAB)["ok"] and language_check(GOOD_JAPANESE, "\u65e5\u672c\u8a9e", REAL_VOCAB)["ok"])


def test_language_check_edge_cases():
    check("English is never language-checked", language_check(REAL_SPANISH_IS_ENGLISH, "English", REAL_VOCAB)["verdict"] == "not_checked")
    check("a language with no script rule is still caught when the story is just English",
          language_check(REAL_SPANISH_IS_ENGLISH, "Klingon", REAL_VOCAB)["verdict"] == "english")
    check("language names are matched case-insensitively", language_check(REAL_SPANISH_OK, " spanish ", REAL_VOCAB)["ok"])
    check("ambiguous short words (no, a, me) alone don't count as English",
          language_check("No, a mi me gusta. Vamos a casa. No hay agua. Es mi amigo. Hasta ma\u00f1ana.", "Spanish", "no, water")["ok"])


def test_check_passage_uses_the_language():
    r = check_passage(REAL_SPANISH_IS_ENGLISH, REAL_VOCAB, check_vocab=False, language="Spanish")
    check("an English story requested in Spanish fails overall", not r["passed"] and r["language_check"]["verdict"] == "english")
    r = check_passage(REAL_SPANISH_OK, REAL_VOCAB, check_vocab=False, language="Spanish")
    check("a real Spanish story passes overall", r["passed"])
    r = check_passage(REAL_SPANISH_IS_ENGLISH, REAL_VOCAB, check_vocab=False)
    check("without a language the old behavior is unchanged", r["passed"] and r["language_check"] is None)


def test_summarize_reports_language_problems():
    results = [
        check_passage(REAL_SPANISH_OK, REAL_VOCAB, check_vocab=False, language="Spanish"),
        check_passage(REAL_SPANISH_IS_ENGLISH, REAL_VOCAB, check_vocab=False, language="Spanish"),
        check_passage(REAL_FRENCH_MIXED, REAL_VOCAB, check_vocab=False, language="French"),
    ]
    s = summarize(results)
    check("summary counts wrong-language passages", s["language_bad"] == 2)
    check("summary breaks the verdicts down", s["language_verdicts"].get("english") == 1)


def test_rescore_applies_the_language_check():
    data = {"vocabulary": REAL_VOCAB, "results": {"Spanish": [
        {"text": REAL_SPANISH_OK, "latency": 1.0}, {"text": REAL_SPANISH_IS_ENGLISH, "latency": 1.0}]}}
    r = rescore_results(data)
    check("re-scoring a saved non-English run now catches stories in the wrong language",
          [x["passed"] for x in r["Spanish"]] == [True, False])


def test_summary_only_reports_language_when_something_was_checked():
    english = [check_passage(GOOD_NARRATION, VOCAB, language="English") for _ in range(3)]
    text = format_summary(summarize(english))
    check("an English-only run prints no 'written in the requested language' line", "requested language" not in text)
    mixed = [
        check_passage(REAL_SPANISH_OK, REAL_VOCAB, check_vocab=False, language="Spanish"),
        check_passage(REAL_SPANISH_IS_ENGLISH, REAL_VOCAB, check_vocab=False, language="Spanish"),
        check_passage(GOOD_NARRATION, VOCAB, language="English"),
    ]
    s = summarize(mixed)
    check("only passages whose language was checked are counted", s["language_checked"] == 2 and s["language_bad"] == 1)
    check("the line shows ok / checked, not ok / everything", "Written in the requested language: 1/2" in format_summary(s))


# --- variety: are the stories different from one another? (Step 10, tuning change #2) ----------
# Found by reading 48 stories: 81% mentioned water and ~75% were somebody asking for something.


def _res(text, kind=None, failure=False):
    return {"text": text, "story_type": kind, "failure": failure}


SAME = "Hello, I am Sam today. I want water. I see my friend near the house. I say please. My friend gives water."
DIVERSE = [
    _res("Dear Anna, the market was busy today. I bought bread and a new book. My friend laughed at the hat.", "letter"),
    _res("Monday. Rain came early, so we stayed in the house. Tom read a book and I cooked a big soup.", "diary"),
    _res("There is a small park near my house. Children play with a red ball. Old men sit and talk.", "place"),
    _res("A dog stole my bread! It ran to the garden and hid. My friend found it asleep with the bread.", "anecdote"),
]


def test_variety_report_repetitive_set():
    rep = variety_report([_res(SAME, "narration") for _ in range(4)], REAL_VOCAB)
    check("identical stories overlap completely", abs(rep["mean_overlap"] - 1.0) < 1e-9)
    check("the most used vocabulary word is in every story",
          rep["top_vocab_word"][1] == 1.0 and rep["top_vocab_word"][0] in ("water", "friend", "house", "today"))
    check("one type only", rep["distinct_types"] == 1 and rep["types"] == {"narration": 4})
    check("one opening used by everything", rep["top_opening"][1] == 1.0)


def test_variety_report_diverse_set():
    rep = variety_report(DIVERSE, REAL_VOCAB)
    check("different stories overlap little (< 0.2)", rep["mean_overlap"] < 0.2)
    check("no vocabulary word is in more than half of the stories", rep["top_vocab_word"][1] <= 0.5)
    check("four distinct types", rep["distinct_types"] == 4)
    check("no repeated opening", rep["top_opening"][1] <= 0.25)


def test_variety_report_details():
    greet = [dict(t, text="Hello! " + t["text"]) for t in DIVERSE]
    rep = variety_report(greet, REAL_VOCAB)
    check("greetings and politeness words ('hello', 'please', 'thank you') are not counted as the repeated word",
          rep["top_vocab_word"][0] not in ("hello", "please", "thank", "you", "yes", "no", "goodbye"))
    mixed = DIVERSE + [_res("I'm having trouble generating a story right now — please try again in a moment.", None, failure=True)]
    check("failed generations are left out", variety_report(mixed, REAL_VOCAB)["n"] == 4)
    check("one story cannot be compared with another (overlap is None)", variety_report(DIVERSE[:1], REAL_VOCAB)["mean_overlap"] is None)
    check("with no stories nothing breaks", variety_report([], REAL_VOCAB)["n"] == 0)
    rep = variety_report([_res(SAME, "story") for _ in range(2)], REAL_VOCAB, english=False)
    check("for non-English runs the English-vocabulary word metric is skipped", rep["top_vocab_word"] is None)
    check("results without a recorded type are still scored (older saved runs)", variety_report([_res(SAME), _res(SAME)], REAL_VOCAB)["distinct_types"] == 0)


def test_format_variety():
    text = format_variety(variety_report(DIVERSE, REAL_VOCAB))
    check("the summary line reports types, overlap and the repeated word", "distinct" in text and "overlap" in text and "vocabulary word" in text)
    check("an empty report prints a short note", "no stories" in format_variety(variety_report([], REAL_VOCAB)).lower())


def test_rescore_keeps_the_story_type():
    data = {"vocabulary": REAL_VOCAB, "results": {"English": [{"text": SAME, "latency": 1.0, "story_type": "diary"}]}}
    check("a saved story type survives re-scoring", rescore_results(data)["English"][0]["story_type"] == "diary")


# --- three measurement bugs found by reading the saved variety run -----------------------------

JAPANESE_ONE_LINE = (
    "\u4eca\u65e5\u306f\u6674\u308c\u3067\u3059\u3002\u65b0\u3057\u3044\u30da\u30c3\u30c8\u306e\u3046\u3055\u304e\u304c\u5bb6\u306b\u3044\u307e\u3059\u3002"
    "\u3046\u3055\u304e\u306f\u6c34\u3092\u98f2\u307f\u307e\u3059\u3002\u98df\u3079\u7269\u306f\u30d3\u30b9\u30b1\u30c3\u30c8\u3068\u30d1\u30f3\u3067\u3059\u3002"
    "\u53cb\u9054\u304c\u672c\u3092\u8aad\u3093\u3067\u3044\u307e\u3059\u3002\u3042\u308a\u304c\u3068\u3046\u3001\u3055\u3088\u3046\u306a\u3089\u3002"
)


def test_cjk_sentences_without_spaces_are_counted():
    r = check_passage(JAPANESE_ONE_LINE, REAL_VOCAB, check_vocab=False, language="Japanese")
    check("a Japanese story written on one line counts its 6 sentences (was counted as 1)", r["units"] == 6 and r["length_ok"])
    r = check_passage("\u3053\u3093\u306b\u3061\u306f\u3002\u79c1\u306f\u30b5\u30e0\u3067\u3059\u3002\n\u4eca\u65e5\u306f\u6c34\u304c\u6b32\u3057\u3044\u3067\u3059\u3002", REAL_VOCAB, check_vocab=False)
    check("sentences are counted per line and per terminator", r["units"] == 3)
    r = check_passage("Hello. I am Sam. I want water. Thank you. Goodbye.", REAL_VOCAB)
    check("English sentence counting is unchanged", r["units"] == 5)


FRENCH_NARRATION_WITH_COLON = (
    "Bonjour, je m'appelle L\u00e9a et je rentre \u00e0 la maison.\nAujourd'hui il fait beau et je marche.\n"
    "Je rencontre mon ami Marc sur le chemin.\nMarc dit : \u00ab Veux\u2011tu un biscuit ? \u00bb\n"
    "Oui, il me donne un biscuit et du pain.\nNous parlons, puis je continue vers la maison."
)


def test_a_colon_after_a_verb_is_not_a_speaker_label():
    r = check_passage(FRENCH_NARRATION_WITH_COLON, REAL_VOCAB, check_vocab=False, language="French")
    check("'Marc dit : ...' inside a narration is not a speaker label", r["style"] == "narration" and r["format_ok"])
    r = check_passage("Marie : Bonjour, as-tu de l'eau ?\nPaul : Oui, j'ai de l'eau.\nMarie : Merci.\nPaul : De rien.\nMarie : Au revoir.", REAL_VOCAB, check_vocab=False)
    check("real French-style labels ('Marie : ...') are still recognised", r["style"] == "dialogue" and r["format_ok"])
    r = check_passage(GOOD_DIALOGUE, REAL_VOCAB)
    check("normal 'Name: line' dialogue still passes the format check", r["format_ok"])
    r = check_passage("\u30bf\u30ed\u30a6: \u3053\u3093\u306b\u3061\u306f\u3002\n\u30b8\u30ed\u30a6: \u3053\u3093\u306b\u3061\u306f\u3002\n\u30bf\u30ed\u30a6: \u6c34\u304c\u6b32\u3057\u3044\u3067\u3059\u3002\n\u30b8\u30ed\u30a6: \u306f\u3044\u3002\n\u30bf\u30ed\u30a6: \u3042\u308a\u304c\u3068\u3046\u3002", REAL_VOCAB, check_vocab=False)
    check("labels in scripts without letter case (katakana names) are still recognised", r["style"] == "dialogue" and r["format_ok"])


def test_names_that_only_start_sentences_are_not_stray_words():
    story = ("Sam wakes up and sees rain outside.\nSam looks out and says hello.\n"
             "Sam feels bored because there is no sunny day.\nSam shares bread with his friend.")
    r = check_passage(story, REAL_VOCAB)
    check("a name that only ever starts sentences is recognised as a name", "sam" not in r["oov_words"] and "sam" in r["names"])
    r = check_passage("Today I eat bread. Today I read a book. Today I drink water.", REAL_VOCAB)
    check("a vocabulary word that starts sentences ('Today') is not mistaken for a name", "today" not in r["names"])
    r = check_passage("I read a book. I read it today. I like to read. Read with me.", REAL_VOCAB)
    check("an ordinary word that also appears in lower case is not a name", "read" in r["oov_words"])


def main():
    print("Running vocabulary adherence checker tests...\n")
    test_parse_vocabulary()
    test_word_forms()
    test_good_passages_pass()
    test_flags_words_outside_the_vocabulary()
    test_allows_basic_grammar_and_simple_verbs()
    test_inflections_are_accepted()
    test_names_are_ignored()
    test_contractions_and_curly_apostrophes()
    test_oov_rate()
    test_style_detection()
    test_length()
    test_dialogue_format()
    test_leaks()
    test_failures_are_classified()
    test_non_english_skips_the_vocabulary_check()
    test_strict_verbs()
    test_passed_flag()
    test_summarize()
    test_unit_word_metrics()
    test_max_unit_words_is_optional_and_enforced()
    test_rescore_results()
    test_language_check_real_outputs()
    test_language_check_edge_cases()
    test_check_passage_uses_the_language()
    test_summarize_reports_language_problems()
    test_rescore_applies_the_language_check()
    test_summary_only_reports_language_when_something_was_checked()
    test_variety_report_repetitive_set()
    test_variety_report_diverse_set()
    test_variety_report_details()
    test_format_variety()
    test_rescore_keeps_the_story_type()
    test_cjk_sentences_without_spaces_are_counted()
    test_a_colon_after_a_verb_is_not_a_speaker_label()
    test_names_that_only_start_sentences_are_not_stray_words()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
