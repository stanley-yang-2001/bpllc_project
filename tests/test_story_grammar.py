"""Grammar and fluency of generated stories (6 Nov 2026): the fluency checks, the repair call, the optional proofreading call, and the
rule that a rewrite is used only when it is safe. No database, no network: the model is a function.

    PYTHONPATH=tutor_core python tests/test_story_grammar.py
"""
import sys

sys.path.insert(0, "tutor_core")

from tutor_core.prompts import build_proofread_prompt, build_repair_prompt, build_story_prompt  # noqa: E402
from tutor_core.quality import fluency_problems  # noqa: E402
from tutor_core.story_retries import RetryPolicy  # noqa: E402

failures = []


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label)
    if not condition:
        failures.append(label)


GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer.")
LIST = "Casa. Mar. María mira. Pedro pan. Agua azul. Ella come. Sol. Jardín grande."
TWICE = "Ana abre la puerta de la casa. Ana abre la puerta de la casa. El perro corre por el jardín verde. Luego todos comen pan en la mesa."
SAME = ("El niño abre la puerta. El niño mira el jardín. El niño come una manzana. El niño lee un libro. "
        "El niño habla con su madre. Después duerme.")
WORDS = ["casa", "mar", "amigo", "jardín"]


def test_checks():
    check("a natural text has no problem", fluency_problems(GOOD) == [])
    check("a list of words is telegraphic", any("only a few words" in p for p in fluency_problems(LIST)))
    check("a repeated sentence is named", any("more than once" in p for p in fluency_problems(TWICE)))
    check("the same opening is named", any("same words" in p for p in fluency_problems(SAME)))
    check("short dialogue lines are natural", fluency_problems("Ana: Hola.\nPedro: Sí.\nAna: ¿Cómo estás?\nPedro: Bien.\nAna: Adiós.") == [])
    check("too few sentences is not judged", fluency_problems("Casa. Mar.") == [])
    check("Chinese is counted in characters", fluency_problems("我家。海。我看海。他来。我们吃饭。", unspaced=True) != [] and
          fluency_problems("我住在海边的一座大房子里。每天早上我打开窗户看海。朋友带着新鲜的面包来看我。我们在花园里一起吃早饭。然后我们沿着海滩慢慢地走。", unspaced=True) == [])


def policy(call, proofread=False, words=WORDS):
    return RetryPolicy("es", "PROMPT", words, None, call, proofread=proofread)


def test_repair():
    calls = []

    def call(prompt):
        calls.append(prompt)
        return "plan\n===STORY===\n" + GOOD
    out = policy(call).improve(LIST)
    check("a list-like story gets one repair call naming the problem", len(calls) == 1 and "only a few words" in calls[0] and Casa_in(calls[0]))
    check("a repair 3 times longer than a list-like text is refused", out == LIST)
    similar = "Casa grande. María mira el mar. Pedro es su amigo. Come pan en el jardín. El agua es azul. Ella come."
    out = policy(lambda p: "===STORY===\n" + "María tiene una casa cerca del mar y mira el agua azul. Su amigo Pedro come pan en el jardín grande.").improve(similar)
    check("a repair of similar length with fewer problems is used", out.startswith("María tiene"))
    calls.clear()
    check("a natural story makes no extra call", policy(call).improve(GOOD) == GOOD and calls == [])
    check("a failing repair keeps the first text", policy(lambda p: (_ for _ in ()).throw(RuntimeError("x"))).improve(LIST) == LIST)


def Casa_in(prompt):
    return "Casa. Mar." in prompt


def test_safety_of_rewrites():
    long_text = GOOD + " " + GOOD
    check("a rewrite twice as long is not used", policy(lambda p: "===STORY===\n" + long_text, proofread=True).improve(GOOD) == GOOD)
    check("a rewrite in English is not used", policy(lambda p: "===STORY===\nMaria lives in a big house near the sea. Every morning she opens the window and watches the water. Her friend Pedro comes with fresh bread.", proofread=True).improve(GOOD) == GOOD)
    cut = GOOD.rsplit(" ", 3)[0]
    check("a rewrite cut off mid-sentence is not used", policy(lambda p: "===STORY===\n" + cut, proofread=True).improve(GOOD) == GOOD)
    lost = GOOD.replace("casa", "choza").replace("mar", "río").replace("jardín", "patio").replace("amigo", "vecino")
    check("a rewrite that drops the learner's words is not used", policy(lambda p: "===STORY===\n" + lost, proofread=True).improve(GOOD) == GOOD)


def test_proofread():
    fixed = GOOD.replace("Los dos desayunan", "Los dos desayunaron")
    calls = []

    def call(prompt):
        calls.append(prompt)
        return "===STORY===\n" + fixed
    check("proofreading is off by default", policy(call).improve(GOOD) == GOOD and calls == [])
    out = policy(call, proofread=True).improve(GOOD)
    check("proofreading makes one call and uses a safe fix", len(calls) == 1 and out == fixed and "Proofread" in calls[0])


def test_prompts():
    p = build_repair_prompt("Spanish", GOOD, ["a", "b"], "casa, mar")
    check("the repair prompt lists the problems and quotes the draft", "- a\n- b" in p and "<<<\n" + GOOD in p and "===STORY===" in p)
    check("the proofread prompt names grammar", "agreement" in build_proofread_prompt("Spanish", GOOD, "casa"))
    for lang, vt in (("Spanish", True), ("German", False), ("Japanese", True)):
        check(f"the story prompt carries the natural-sentence rule ({lang})", "complete, natural sentences" in build_story_prompt(lang, "a, b, c", vocab_in_target=vt))
    check("the English prompt is unchanged (pinned elsewhere)", "complete, natural sentences" not in build_story_prompt("English", "a, b, c"))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nFAILED:", failures) if failures else print("\nall passed")
    sys.exit(1 if failures else 0)
