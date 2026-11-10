"""The offline story signals and their agreement maths, with fakes: no server, no model, no network.
    PYTHONPATH=tutor_core:scripts python tests/test_eval_signals.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path[:0] = ["tutor_core", "scripts"]

import eval_signals  # noqa: E402
from story_eval import agreement  # noqa: E402
from story_eval.signals import LanguageToolSignal, PerplexitySignal, WorstSentenceSignal, count_words, sentences  # noqa: E402

failures = []


def check(label, ok, detail=""):
    print(("PASS" if ok else "FAIL"), label, detail if not ok else "")
    if not ok:
        failures.append(label)


def test_languagetool():
    seen = {}

    def post(url, fields):
        seen.update(url=url, **fields)
        return {"matches": [{"rule": {"issueType": "grammar"}}, {"rule": {"issueType": "style"}}, {"rule": {"issueType": "misspelling"}}]}
    s = LanguageToolSignal("http://lt:8010/", post=post)
    v = s.measure("one two three four five six seven eight nine ten", "en")
    check("style hints are not counted, errors per 100 words", v == 20.0, str(v))
    check("posts to /v2/check with the right language code", seen["url"] == "http://lt:8010/v2/check" and seen["language"] == "en-US")
    check("a language without rules (Korean) gives None, not a guess", s.measure("안녕하세요", "ko") is None)


def test_perplexity():
    fake = {"good sentence here.": 1.0, "bad bad sentence.": 3.0}
    scorer = lambda t: fake.get(t, 2.0)  # noqa: E731
    text = "good sentence here. bad bad sentence."
    check("perplexity is exp of the mean loss", PerplexitySignal(scorer=scorer).measure(text, "en") == round(2.718281828 ** 2.0, 3))
    check("worst sentence picks the most surprising one", WorstSentenceSignal(scorer=scorer).measure(text, "en") == round(2.718281828 ** 3.0, 3))
    check("nan loss gives None", PerplexitySignal(scorer=lambda t: float("nan")).measure("x y z", "en") is None)


def test_text_helpers():
    check("sentences split", sentences("Hello there. How are you? Fine!") == ["Hello there.", "How are you?", "Fine!"])
    check("unspaced languages count characters", count_words("今日は天気です", "ja") == 7)


def test_agreement():
    check("pearson of a perfect line", agreement.pearson([1, 2, 3, 4], [2, 4, 6, 8]) == 1.0)
    check("spearman ignores shape", agreement.spearman([1, 2, 3, 4], [1, 10, 100, 1000]) == 1.0)
    check("too few points gives None", agreement.pearson([1, 2], [1, 2]) is None)
    rows = [{"language": "en", "hand": h, "err": e} for h, e in [(90, 1), (70, 3), (50, 5), (30, 8)]]
    c = agreement.correlate(rows, "err")
    check("errors fall as grades rise: strongly negative", c["n"] == 4 and c["pearson"] < -0.9, str(c))
    rows2 = agreement.meta_score(rows, ["err"], {"err": False})
    check("meta score flips the sign for lower-is-better", rows2[0]["meta"] > rows2[3]["meta"])


def test_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        results = {f"en-{i}": {"v": {"ok": True, "text": "w " * (10 * (i + 1)), "score": {"score": 50 + 10 * i}}} for i in range(4)}
        run = {"created": "T1", "requests": [{"id": k, "code": "en"} for k in results], "results": results}
        (d / "run.json").write_text(json.dumps(run))
        (d / "g.json").write_text(json.dumps({"runs": {"T1": {f"en-{i}": {"v": 50 + 10 * i} for i in range(4)}}}))
        sig = LanguageToolSignal("http://x", post=lambda u, f: {"matches": [{"rule": {}}] * (len(f["text"].split()) // 10)})
        rows = eval_signals.collect([d / "run.json"], eval_signals.load_grades(d / "g.json"), [sig])
        result = eval_signals.build(rows, [sig])
        check("rows carry the grade, score and signal", len(rows) == 4 and rows[0]["hand"] == 50 and rows[0]["languagetool_per100"] is not None)
        check("the story score matches the grades exactly", result["score"]["pearson"] == 1.0, str(result["score"]))
        check("the table prints", "languagetool_per100" in eval_signals.table(result))


if __name__ == "__main__":
    for t in (test_languagetool, test_perplexity, test_text_helpers, test_agreement, test_end_to_end):
        t()
    sys.exit(1 if failures else 0)
