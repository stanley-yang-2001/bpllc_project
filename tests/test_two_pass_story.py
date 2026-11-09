"""Two-pass story generation and the side-by-side comparison page (6 Nov 2026). No database, no network: the model is a function and the
learner's words are patched in.

    PYTHONPATH=tutor_core:scripts python tests/test_two_pass_story.py
"""
import os
import sys

sys.path.insert(0, "tutor_core")
sys.path.insert(0, "scripts")

import compare_story_versions as cmp  # noqa: E402
from tutor_core import story as st  # noqa: E402
from tutor_core.prompts.templates import DELIMITER  # noqa: E402
from tutor_core.two_pass import build_adapt_prompt, build_draft_prompt, form_of, target_length, two_pass_passage  # noqa: E402

failures = []


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label)
    if not condition:
        failures.append(label)


WORDS = ["casa", "mar", "amigo", "jardín", "pan"]
DRAFT = ("María vive en una casa pequeña cerca del mar. Cada mañana abre la ventana y mira el agua azul. Su amigo Pedro llega con pan fresco. "
         "Los dos comen juntos en el jardín y hablan del día. Después caminan por la playa hasta la tarde.")
ADAPTED = DRAFT.replace("pequeña", "grande")
ONE_CALL = "Ana tiene una casa. Ella mira el mar cada día. Su amigo trae pan. Todos comen en el jardín."


class Model:
    def __init__(self, fail_second=False, empty_draft=False):
        self.prompts, self.fail_second, self.empty_draft = [], fail_second, empty_draft

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if "Rewrite it so that it naturally includes" in prompt:
            if self.fail_second:
                raise RuntimeError("boom")
            return f"{DELIMITER}\n{ADAPTED}"
        if "Write " in prompt and "for a beginner learning" in prompt:
            return "" if self.empty_draft else f"{DELIMITER}\n{DRAFT}"
        return f"{DELIMITER}\n{ONE_CALL}"


def run(two_pass, **kw):
    st.load_words = lambda conn, learner, language, set_ids=None: list(WORDS)
    model = Model(**kw)
    res = st.generate_story(object(), 1, "es", call_groq_fn=model, use_cache=False, two_pass=two_pass, story_type="story", topic="a market day")
    return res, model


def test_prompts():
    d = build_draft_prompt("Spanish", "es", "story", "a market day", 80)
    check("the draft prompt has no word list and asks about 1.3 times the length", "104 words" in d and "casa" not in d and "market day" in d)
    a = build_adapt_prompt("Spanish", "es", DRAFT, "casa, mar", 80)
    check("the adapt prompt carries the words, the draft as quoted text and a length range", "casa, mar" in a and "<<<\n" + DRAFT in a and "between 68 and 92 words" in a)
    check("Chinese and Japanese lengths are in characters", "characters" in build_draft_prompt("Japanese", "ja", "story", None, 80))
    check("a tier length is the target", target_length("story", {"length": 120}) == 120 and target_length("dialogue", None) == 50 and target_length("diary", None) == 80)
    check("every kind has a form", "dialogue" in form_of("dialogue") and 'kind "poem"' in form_of("poem") and form_of("diary").startswith("a diary"))


def test_pipeline():
    res, model = run(False)
    check("off: the old pipeline makes one call and returns its text", res.ok and res.text == ONE_CALL and len(model.prompts) == 1)
    res, model = run(True)
    check("on: a draft call, then an adapt call, and the adapted text is the story", res.ok and res.text == ADAPTED and len(model.prompts) == 2)
    check("on: the draft call came first and had no words", "for a beginner learning" in model.prompts[0] and "casa" not in model.prompts[0])
    res, model = run(True, fail_second=True)
    check("a failing second pass falls back to the one-call story", res.ok and res.text == ONE_CALL and len(model.prompts) == 3)
    res, model = run(True, empty_draft=True)
    check("an empty draft falls back to the one-call story", res.ok and res.text == ONE_CALL)
    os.environ["STORY_TWO_PASS"] = "1"
    try:
        st.load_words = lambda *a, **k: list(WORDS)
        model = Model()
        res = st.generate_story(object(), 1, "es", call_groq_fn=model, use_cache=False, story_type="story")
        check("STORY_TWO_PASS=1 switches it on when the argument is not given", res.text == ADAPTED)
    finally:
        del os.environ["STORY_TWO_PASS"]
    check("two_pass_passage returns None on an error", two_pass_passage(lambda p: (_ for _ in ()).throw(RuntimeError()), "es", "Spanish", "x", WORDS, None) is None)


def test_cache_key():
    a = st.StoryRequest(1, "es", "story", None, None, None, None, False).cache_key()
    b = st.StoryRequest(1, "es", "story", None, None, None, None, True).cache_key()
    check("a two-pass story never answers for a one-call story from the cache", a != b)


def test_comparison_page():
    st.load_words = lambda conn, learner, language, set_ids=None: list(WORDS)
    model = Model()
    pair = cmp.make_pair(st.generate_story, object(), 1, "es", model, 1001, words=WORDS, translate=lambda text, code: "EN: " + text[:12],
                         story_type="story", topic="a market day")
    check("the pair has an old and a new story with their call counts", pair["old"]["text"] == ONE_CALL and pair["new"]["text"] == ADAPTED
          and pair["old"]["calls"] == 1 and pair["new"]["calls"] == 2)
    check("both stories carry a 0 to 100 score with six parts", all(0 <= pair[k]["score"]["score"] <= 100 and len([v for v in pair[k]["score"]["parts"].values() if v is not None]) == 6 for k in ("old", "new")))
    check("the adapted text scores higher than the four-sentence one", pair["new"]["score"]["score"] > pair["old"]["score"]["score"])
    check("both carry a translation", pair["new"]["translation"].startswith("EN: ") and pair["old"]["translation"].startswith("EN: "))
    plain = cmp.make_pair(st.generate_story, object(), 1, "es", model, 1001, story_type="story", topic="a market day")
    check("without words or a translator there is no score and no translation", plain["old"]["score"] is None and plain["old"]["translation"] == "")

    german = {"code": "de", "pair": pair}
    page = cmp.render({"Spanish": [{"code": "es", "pair": pair}], "German": [german]}, {"Spanish": ", ".join(WORDS), "German": "Haus"})
    check("the page has a Summary tab and a tab for each language", page.count("<button role=tab ") == 3 and "data-tab='summary'" in page
          and "data-tab='es'" in page and "data-tab='de'" in page and "id='p-es'" in page and "id='p-de'" in page)
    check("the page shows both texts, the scores and the six parts", ONE_CALL in page and ADAPTED in page and "Old: one call" in page and "New: two passes" in page
          and "Language, format" in page and "/ 100" in page and "higher score" in page)
    check("the summary compares the averages and the calls", "Old score" in page and "New score" in page and "1 / 2" in page)
    check("the translation is offered under each story", "English translation" in page and "EN: " in page)
    pair["new"]["text"] = "<script>alert(1)</script>"
    pair["new"]["score"] = None
    check("text from the model is escaped and a missing score does not break the page",
          "<script>alert" not in cmp.render({"Spanish": [{"code": "es", "pair": pair}]}, {"Spanish": "casa"}))
    sm = cmp.summarize([{"code": "es", "pair": make_scored(80, 90)}, {"code": "es", "pair": make_scored(70, 60)}, {"code": "es", "pair": make_scored(50, 50)}])
    check("the summary averages the scores and counts who was higher", sm["old"]["score"] == 66.7 and sm["new"]["score"] == 66.7 and sm["wins"] == {"old": 1, "new": 1, "tie": 1})


def make_scored(old, new):
    def version(score):
        return {"text": "t", "ok": True, "reason": None, "story_type": "story", "topic": None, "calls": 1, "seconds": 1.0, "error": None,
                "score": {"score": score, "parts": {}, "gated": None, "partial": False}, "translation": ""}
    return {"old": version(old), "new": version(new)}


def test_translator():
    seen = []
    t = cmp.translator(lambda prompt: seen.append(prompt) or " Hello. ")
    check("the translator asks for a literal translation and returns the text", t("Hola.", "es") == "Hello." and "literally" in seen[0] and "Spanish" in seen[0])
    check("English and empty text are not translated", t("Hello", "en") == "" and t("  ", "es") == "")
    check("a failing translation gives an empty string", cmp.translator(lambda p: (_ for _ in ()).throw(RuntimeError()))("Hola.", "es") == "")


def test_rescore_offline():
    text = "María vive en una casa grande cerca del mar. Cada mañana abre la ventana y mira el agua. Su amigo llega con pan fresco. Los dos desayunan juntos."
    old_score = {"score": 10.0}
    version = {"text": text, "ok": True, "story_type": "story", "score": old_score, "calls": 1, "seconds": 1.0, "reason": None, "topic": None, "error": None, "translation": ""}
    data = {"learner_id": 1, "vocabularies": {"Spanish": "casa, mar, pan"}, "samples": {"Spanish": [{"code": "es", "pair": {"old": version, "new": dict(version, ok=False)}}]}}
    out = cmp.rescore(data)
    got = out["samples"]["Spanish"][0]["pair"]
    check("rescoring replaces the saved score with the current one", got["old"]["score"]["version"] == 4.1 and got["old"]["score"]["score"] != 10.0)
    check("a failed story stays without a score", got["new"]["score"] is None)
    check("the input is not changed", version["score"] is old_score)
    check("rescored data renders", "Spanish" in cmp.render(out["samples"], out["vocabularies"]))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nFAILED:", failures) if failures else print("\nall passed")
    sys.exit(1 if failures else 0)
