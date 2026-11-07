"""The 0 to 100 story score (6 Nov 2026): six requirements at equal weight, a gate for stories that must never be kept, and the example
wording. No database, no network.

    PYTHONPATH=tutor_core python tests/test_story_score.py
"""
import sys

sys.path.insert(0, "tutor_core")

from tutor_core.prompts import build_story_prompt, with_example  # noqa: E402
from tutor_core.quality import score_story  # noqa: E402
from tutor_core.quality.score import NAMES  # noqa: E402

failures = []


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label)
    if not condition:
        failures.append(label)


WORDS = ["casa", "mar", "amigo", "jardín", "pan"]
GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer. "
        "Por la tarde vuelven a casa y leen un libro. Al final del día los dos duermen contentos.")
LIST = "Casa. Mar. Pan. Sol. Agua. Perro. Gato. Mesa."


def test_parts_and_weights():
    r = score_story(GOOD, "es", WORDS, None, "story")
    check("a good story has six parts, all measured", tuple(r["parts"]) == NAMES and all(v is not None for v in r["parts"].values()) and not r["partial"])
    check("the score is the plain mean of the parts (equal weights)", abs(r["score"] - round(sum(r["parts"].values()) / 6, 1)) < 0.06)
    check("a good story of about the right length scores high", r["score"] >= 90 and r["parts"]["language_format"] == 100)
    check("the story is within 0 and 100", 0 <= r["score"] <= 100)


def test_each_requirement_moves_the_score():
    base = score_story(GOOD, "es", WORDS, None, "story")
    short = score_story(GOOD.split(". ")[0] + ".", "es", WORDS, None, "story")
    check("a story far too short loses points for length", short["parts"]["length"] < base["parts"]["length"] and short["parts"]["length"] <= 30)
    check("a story using none of the words loses 'your words'", score_story(GOOD, "es", ["zapato", "lluvia", "reloj"], None, "story")["parts"]["own_words"] == 0.0)
    r = score_story(LIST, "es", WORDS, None, "story")
    check("a list of words loses on sentence length and grammar", r["parts"]["sentence_length"] < 50 and r["parts"]["grammar"] <= 66 and r["score"] < 70)
    again = GOOD + " " + GOOD.split(". ")[0] + "."
    check("a repeated sentence costs the grammar part", score_story(again, "es", WORDS, None, "story")["parts"]["grammar"] <= 66)
    check("an unfinished last sentence costs the format part", score_story(GOOD.rstrip(".") + " y", "es", WORDS, None, "story")["parts"]["language_format"] <= 75)
    check("a text that is not a dialogue loses format when a dialogue was asked for", score_story(GOOD, "es", WORDS, None, "dialogue")["parts"]["language_format"] <= 75)
    tier = {"tier": "easy", "length": 60, "own_words": 3, "uncommon_pct": 5}
    check("a tier changes the length target", score_story(GOOD, "es", WORDS, tier, "story")["targets"]["length"] == 60)


def test_the_gate():
    for label, text in (("empty", ""), ("a failure message", "I'm having trouble generating a story right now"),
                        ("a leaked plan", "Character: Ana\nWant: bread\n" + GOOD),
                        ("the wrong language", "Mary lives in a big house near the sea. Every morning she opens the window and looks at the water. "
                                               "Her friend Peter comes with fresh bread and they eat together in the garden.")):
        r = score_story(text, "es", WORDS, None, "story")
        check(f"{label}: score 0 and gated", r["score"] == 0.0 and r["gated"])


def test_other_languages():
    ja = "私は大きい家に住んでいます。毎朝、窓を開けて海を見ます。友達のピーターがパンを持ってきます。二人で庭で食べます。それから海の近くを歩きます。"
    r = score_story(ja, "ja", ["家", "海", "友達", "パン", "庭"], None, "story")
    check("Japanese is scored in characters and is not gated", not r["gated"] and r["measured"]["length"] > 20 and r["score"] > 0)
    en = ("Mary lives in a big house near the sea. Every morning she opens the window and looks at the water. Her friend Peter comes with "
          "fresh bread. They eat together in the garden and talk about the day. Later they walk along the beach until it is time for lunch.")
    check("English works without a language check", score_story(en, "en", ["house", "sea", "friend", "bread", "garden"], None, "story")["score"] > 80)


def test_example_wording():
    p = build_story_prompt("Spanish", "a, b", vocab_in_target=True)
    q = with_example(p, "Ana come pan.")
    check("the example is quoted before the last instruction", q.index("Ana come pan.") < q.rindex("Begin:") and "<<<\nAna come pan.\n>>>" in q)
    check("the wording says what to take and what not to take", "only to see how natural and correct" in q and "do not copy its topic" in q and "requirements above decide" in q)
    check("no example, no change", with_example(p, "") == p and with_example("no begin line", "x") == "no begin line")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nFAILED:", failures) if failures else print("\nall passed")
    sys.exit(1 if failures else 0)
