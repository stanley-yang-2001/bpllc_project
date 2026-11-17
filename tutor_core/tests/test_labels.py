"""Human labels for the story tests: picking, the blind sheets, reading the answers back and comparing them with the reviewers (scripts/story_eval/labels.py)."""
import csv
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from story_eval import labels, stats  # noqa: E402

openpyxl = pytest.importorskip("openpyxl")


def entry(text, kind, free=99.0):
    """A finished story: kind is 'pass' (no reviewer failed it), 'split' (gpt did) or 'fail' (both did)."""
    failed = {"pass": [], "split": ["gpt"], "fail": ["gpt", "qwen"]}[kind]
    rating = {"pass": (4, 4), "split": (2, 3), "fail": (2, 2)}[kind]
    def sc(label, bad):
        return {"score": 40.0 if bad else 90.0, "failed": ["unnatural"] if bad else [], "gated": None}
    return {"ok": True, "text": text, "score": {"score": free}, "audit_scores": {"gpt": sc("gpt", "gpt" in failed), "qwen": sc("qwen", "qwen" in failed)},
            "audits": {"gpt": {"naturalness": {"score": rating[0]}}, "qwen": {"naturalness": {"score": rating[1]}}},
            "audit_union": {"score": 60.0, "failed": failed, "gated": None}}


def run(languages=("en", "es"), per_language=6, reviewed=True):
    requests, results = [], {}
    n = 0
    for code in languages:
        for k in range(per_language):
            rid = f"{code}-{n}"
            n += 1
            tier = ("easy", "medium", "hard")[k % 3]
            requests.append({"id": rid, "code": code, "tier": tier, "story_type": "diary", "topic": "a day", "pack": ("basics", "food")[k % 2], "words": ["uno", "dos", "tres"], "seed": n})
            row = {"baseline": entry(f"{code} first version number {k}. Hello there.", "fail" if k % 2 == 0 else "split"),
                   "cascade": entry(f"{code} second version number {k}. A good day.", "pass")}
            if not reviewed:
                for e in row.values():
                    e.pop("audit_scores"), e.pop("audits"), e.pop("audit_union")
            results[rid] = row
    return {"format": "story-methods-1", "requests": requests, "results": results}


def test_spearman_handles_ties_and_degenerate_input():
    assert stats.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert stats.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert stats.spearman([1, 1, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9486, abs=1e-3)
    assert stats.spearman([1, 2], [1, 2]) is None and stats.spearman([3, 3, 3], [1, 2, 3]) is None
    assert stats.ranks([5, 1, 1, 9]) == [3.0, 1.5, 1.5, 4.0]


def test_pick_shows_every_method_on_some_requests_and_samples_each_verdict_from_the_rest():
    stories = labels.stories_of(run(("en",), per_language=8), "a.json")         # 7 requests are left after the method comparison; 6 are wanted
    chosen = labels.pick(stories, method_requests=1, per_verdict=2, seed=3)
    assert len(chosen) == 2 + 6 and len({s["id"] for s in chosen}) == len(chosen)
    assert all(s["id"].startswith("EN") for s in chosen)
    comparison = [s for s in chosen if s["why"] == labels.METHOD_SET]
    assert {s["method"] for s in comparison} == {"baseline", "cascade"} and len({s["request"] for s in comparison}) == 1
    rest = [s for s in chosen if s["why"] != labels.METHOD_SET]
    assert len({s["request"] for s in rest}) == len(rest)                   # one story a request
    assert Counter_of(rest, "verdict") == {"pass": 2, "split": 2, "fail": 2}
    again = labels.pick(stories, method_requests=1, per_verdict=2, seed=3)
    assert [(s["id"], s["request"], s["method"]) for s in again] == [(s["id"], s["request"], s["method"]) for s in chosen]


def Counter_of(rows, field):
    out = {}
    for r in rows:
        out[r[field]] = out.get(r[field], 0) + 1
    return out


def test_with_no_reviews_in_the_file_a_random_sample_is_taken():
    stories = labels.stories_of(run(("en",), reviewed=False), "a.json")
    assert all(s["verdict"] == "" for s in stories)
    chosen = labels.pick(stories, method_requests=0, per_verdict=1)
    assert len(chosen) == 3 and all(s["why"] == "run verdict: unreviewed" for s in chosen)


def test_the_sheets_are_blind_and_the_key_names_the_methods(tmp_path):
    data = run()
    chosen = labels.pick(labels.stories_of(data, "round.json"), method_requests=1, per_verdict=1, seed=2)
    made = labels.build(chosen, str(tmp_path))
    assert set(made["counts"]) == {"en", "es"} and Path(made["zip"]).exists() and Path(made["key"]).exists()
    z = zipfile.ZipFile(made["zip"])
    assert sorted(z.namelist()) == ["story_labeling/README.txt", "story_labeling/english_stories.xlsx", "story_labeling/spanish_stories.xlsx"]
    leaked = []
    for name in z.namelist():
        z.extract(name, tmp_path / "unzipped")
    for path in (tmp_path / "unzipped" / "story_labeling").iterdir():
        if path.suffix == ".txt":
            text = path.read_text()
        else:
            wb = openpyxl.load_workbook(path)
            text = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value)
        leaked += [w for w in ("baseline", "cascade", "gpt", "qwen", "verdict", "score", "reviewer", "round.json") if w in text.lower().replace("the automatic checks", "")]
    assert leaked == [], leaked
    ws = openpyxl.load_workbook(tmp_path / "unzipped" / "story_labeling" / "english_stories.xlsx")["Stories"]
    assert [c.value for c in ws[1]][:2] == ["ID", "Level"] and len(ws.data_validations.dataValidation) == 3
    ids = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
    assert ids == sorted(ids) and all(i.startswith("EN") for i in ids)
    key = labels.read_key(made["key"])
    assert set(ids) <= set(key) and key[ids[0]]["method"] in ("baseline", "cascade") and key[ids[0]]["language"] == "English"


def fill(src, dst, who, answers):
    wb = openpyxl.load_workbook(src)
    ws = wb["Stories"]
    for r in range(2, ws.max_row + 1):
        a = answers(ws.cell(row=r, column=1).value)
        if a:
            for col, v in zip((6, 7, 8, 9), a):
                ws.cell(row=r, column=col, value=v)
    if who:
        about = wb["Read me first"]
        for row in about.iter_rows():
            for c in row:
                if c.value == "Name or initials":
                    about.cell(row=c.row, column=c.column + 1, value=who)
    wb.save(dst)


def returned_round(tmp_path):
    data = run()
    chosen = labels.pick(labels.stories_of(data, "round.json"), method_requests=2, per_verdict=2, seed=5)
    made = labels.build(chosen, str(tmp_path / "out"))
    key = labels.read_key(made["key"])
    src = tmp_path / "out" / "story_labeling" / "english_stories.xlsx"
    mine = {"pass": ("Yes", 5, "No problem", "reads well"), "split": ("Small fix first", 3, "Unnatural wording", "stiff"), "fail": ("No", 2, "Grammar mistake", "missing word")}
    other = {"pass": ("Yes", 4, "No problem", ""), "split": ("Small fix first", 3, "Unnatural wording", ""), "fail": ("No", 1, "Grammar mistake", "")}
    back = tmp_path / "back"
    back.mkdir()
    fill(src, back / "english_stories_AB.xlsx", "AB", lambda i: mine[key[i]["run_verdict"]])
    fill(src, back / "english_stories_CD.xlsx", None, lambda i: other[key[i]["run_verdict"]] if not i.endswith("03") else None)
    return made, key, back


def test_answers_are_read_back_by_labeler_and_a_blank_row_is_left_out(tmp_path):
    made, key, back = returned_round(tmp_path)
    got = labels.read_labels([str(back)])
    assert sorted(got) == ["AB", "CD"]                        # the initials in the sheet, else what follows english_stories_ in the file name
    assert len(got["AB"]) == len([k for k in key.values() if k["language"] == "English"]) and len(got["CD"]) == len(got["AB"]) - 1
    some = next(iter(got["AB"].values()))
    assert some["q1"] in labels.Q1_VERDICT and some["q2"] in (2, 3, 5) and some["q3"]
    assert labels.labeler_of("x/spanish_stories_Maria R.xlsx", None) == "Maria R" and labels.labeler_of("x/plain.xlsx", " ") == "plain"


def test_the_comparison_finds_agreement_trustworthy_verdicts_and_the_better_method(tmp_path):
    made, key, back = returned_round(tmp_path)
    result = labels.compare(key, labels.read_labels([str(back)]))
    pair = result["pairs"][0]
    assert pair["spearman"] > 0.9 and pair["q2_within_one"] == 1.0 and pair["pass_fail_agree"] == 1.0
    assert result["reviewers"]["free score"]["spearman"] is None                       # every fake story scored 99: it says nothing
    assert result["reviewers"]["gpt rating"]["spearman"] > 0.7           # gpt rates split stories 2, the labelers 3: ties pull it down
    assert result["unanimous"]["pass"]["labeler_answers"].get("fail", 0) == 0 and result["unanimous"]["pass"]["any_labeler_disagrees"] == 0
    assert result["unanimous"]["fail"]["labeler_answers"].get("pass", 0) == 0
    by = {m["method"]: m for m in result["methods"]}
    assert by["cascade"]["q2_mean"] > by["baseline"]["q2_mean"] and by["cascade"]["no"] == 0 and by["baseline"]["no"] > 0
    assert result["paired"] and all(p["minus_baseline"]["cascade"] > 0 for p in result["paired"])
    text = labels.text_report(result)
    for line in ("Each labeler", "rank correlation", "When the reviewers agreed", "The methods on the same requests", "cascade"):
        assert line in text
    rows = labels.joined_rows(key, labels.read_labels([str(back)]))
    assert len(rows) == len(key) and "AB_q2" in rows[0] and "CD_comment" in rows[0]


def test_the_command_line_builds_a_round_and_analyses_it(tmp_path, capsys):
    import label_stories
    source = tmp_path / "round.json"
    source.write_text(json.dumps(run(("en",))))
    assert label_stories.main(["build", "--from", str(source), "--out", str(tmp_path / "o"), "--method-requests", "1", "--per-verdict", "1"]) == 0
    assert "Send this:" in capsys.readouterr().out
    key = tmp_path / "o" / "label_key_PRIVATE.csv"
    rows = list(csv.DictReader(open(key)))
    assert len(rows) == 2 + 3
    back = tmp_path / "back"
    back.mkdir()
    fill(tmp_path / "o" / "story_labeling" / "english_stories.xlsx", back / "english_stories_AB.xlsx", "AB", lambda i: ("Yes", 4, "No problem", ""))
    assert label_stories.main(["analyze", "--key", str(key), "--labels", str(back), "--out", str(tmp_path / "joined.csv")]) == 0
    printed = capsys.readouterr().out
    assert "Human labels against the model reviewers" in printed and (tmp_path / "joined.csv").exists()
    assert label_stories.main(["analyze", "--key", str(key), "--labels", str(tmp_path / "o" / "story_labeling")]) == 2      # unfilled sheets: nothing to compare
    assert label_stories.main(["build", "--from", str(source), "--out", str(tmp_path / "o2"), "--languages", "fr"]) == 2


def test_a_labeler_that_says_it_is_a_model_is_flagged_and_can_be_left_out(tmp_path):
    assert labels.is_ai("AI-assisted benchmark (ChatGPT)") and labels.is_ai("Claude") and not labels.is_ai("SY") and not labels.is_ai("Maria Aino")
    made, key, back = returned_round(tmp_path)
    given = labels.read_labels([str(back)])
    given["AI-assisted benchmark (ChatGPT)"] = given.pop("CD")
    both = labels.compare(key, given)
    humans = labels.compare(key, given, humans_only=True)
    assert both["labelers"]["AI-assisted benchmark (ChatGPT)"]["ai"] and set(both["labelers"]) == {"AB", "AI-assisted benchmark (ChatGPT)"}
    assert set(humans["labelers"]) == {"AB"} and humans["excluded"] == ["AI-assisted benchmark (ChatGPT)"] and humans["pairs"] == []
    assert "[says it is an AI]" in labels.text_report(both) and "Left out (they say they are a model)" in labels.text_report(humans)
