"""Human labels for the story tests (17 Nov 2026): pick stories from saved runs, make blind sheets for people to label, then compare their answers with the model reviewers.

Why: the free score checks the brief, not the language (it correlated -0.11 with two labelers' ratings of 38 stories), and the model reviewers are noisy and have never been
checked against a reader. A person's label is the only measurement that can say which of them to trust. The first round (16 Nov: 28 English and 10 Spanish stories, two of
three labelers back) found the labelers agreeing with each other (rank correlation 0.87), with the reviewers where both reviewers agreed, and preferring the cascade
(4.25 of 5 against 2.0 for the baseline on four requests).

The sheets are BLIND: no method, no score, no verdict, texts shuffled, ids that say nothing. The key that says which method wrote which text is a separate file that
is not in the zip. Three questions per text: would you give it to a learner as it is (Yes / Small fix first / No: pass, split, fail), how natural 1 to 5 (the reviewers'
scale), and the main problem. Needs openpyxl, only to write and read the sheets (`pip install openpyxl`)."""
from __future__ import annotations

import csv
import math
import os
import random
import re
import zipfile
from collections import Counter, defaultdict
from typing import Iterable, Optional

from tutor_core.languages import LANGUAGES

from . import stats, verdicts

Q1_ANSWERS = ("Yes", "Small fix first", "No")
Q1_VERDICT = {"Yes": verdicts.PASS, "Small fix first": verdicts.SPLIT, "No": verdicts.FAIL}
Q3_ANSWERS = ("No problem", "Grammar mistake", "Unnatural wording", "Events do not make sense", "Vocabulary words forced in",
              "Wrong level (too hard or too easy)", "Other (say what in the comment)")
SCALE = (("5", "Reads as if a good writer wrote it: it flows, the events make sense, nothing is odd."),
         ("4", "Natural, with one or two slightly odd phrases."),
         ("3", "Understandable but stiff: filler words added to every line, a list of words, a few odd phrases."),
         ("2", "Often unnatural: words stuck on after commas, sentences that exist only to use a word, events that do not follow, odd meaning."),
         ("1", "Broken or nonsense."))
KIND_TEXT = {"story": "a short story", "letter": "a letter", "diary": "a diary entry", "place": "a description of a place",
             "routine": "a description of a daily routine", "anecdote": "a short anecdote", "dialogue": "a dialogue"}
LEVEL_TEXT = {"easy": "easy (A1-A2)", "medium": "medium (A2-B1)", "hard": "hard (B1-B2)"}
FAIL_AT = 2                          # a rating at or below this is a fail, the same line as the reviewers'
KEY_COLUMNS = ["id", "language", "source_file", "request", "method", "level", "kind", "topic", "word_pack", "why_chosen", "run_verdict", "gpt_rating", "qwen_rating",
               "free_score", "reviewed_score", "words_in_text", "practice_words"]
METHOD_SET = "method comparison"
METHOD_SETS = (METHOD_SET, "cascade set")      # "cascade set" is what the first round (16 Nov) wrote in its key


# ------------------------------------------------------------------------------------------------------------------ picking
def clean(text: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", (text or "").replace("\r", "")).strip()


def stories_of(data: dict, source: str) -> list:
    """Every finished story of a saved run: a dict with the request and the model verdicts, for the key."""
    requests = {r["id"]: r for r in data.get("requests", [])}
    out, seen = [], set()
    for rid, row in (data.get("results") or {}).items():
        request = requests.get(rid) or {}
        for name, entry in row.items():
            text = clean(entry.get("text"))
            if not entry.get("ok") or not text or (rid, text) in seen:
                continue
            seen.add((rid, text))
            got = verdicts.ratings(entry)
            v = verdicts.verdict(entry)
            out.append({"source": source, "request": rid, "method": name, "code": request.get("code", "en"), "level": request.get("tier") or "",
                        "kind": request.get("story_type") or entry.get("story_type") or "story", "topic": request.get("topic") or entry.get("topic") or "",
                        "pack": request.get("pack") or "", "words": list(request.get("words") or []), "text": text, "verdict": v["kind"] if v else "",
                        "gpt": got.get("gpt"), "qwen": got.get("qwen"), "free": verdicts.free_score(entry), "reviewed": verdicts.reviewed_score(entry)})
    return out


def pick(stories: list, *, method_requests: int = 4, per_verdict: int = 6, seed: int = 1) -> list:
    """The stories to label, for every language in `stories` (a list from stories_of).

    1. `method_requests` requests per language with every method that wrote them (so the methods can be compared on the same request by human readers);
    2. `per_verdict` more stories for each model verdict (every reviewer passed, split, every reviewer failed) from other requests, one story a request, spread
       over levels and word packs; with no reviews in the file, `3 * per_verdict` random stories.
    Shuffled, with ids such as EN07 that say nothing."""
    rng = random.Random(seed)
    chosen, by_language = [], defaultdict(list)
    for s in stories:
        by_language[s["code"]].append(s)
    for code, rows in by_language.items():
        requests = list(dict.fromkeys(s["request"] for s in rows))
        multi = [r for r in requests if len({s["method"] for s in rows if s["request"] == r}) >= 2]
        first = multi[:max(0, method_requests)]
        for s in rows:
            if s["request"] in first:
                chosen.append({**s, "why": METHOD_SET})
        rest = [s for s in rows if s["request"] not in first]
        reviewed = [s for s in rest if s["verdict"]]
        groups = [(v, [s for s in reviewed if s["verdict"] == v], per_verdict) for v in (verdicts.PASS, verdicts.SPLIT, verdicts.FAIL)] if reviewed \
            else [("unreviewed", rest, 3 * per_verdict)]
        used = set(first)
        for name, pool, n in sorted(groups, key=lambda g: len({s["request"] for s in g[1]})):         # the scarcest verdict picks first, so it is not starved
            pool = [s for s in pool if s["request"] not in used]
            rng.shuffle(pool)
            got = []
            while pool and len(got) < n:
                pool.sort(key=lambda s: Counter(x["level"] for x in got)[s["level"]] + Counter(x["pack"] for x in got)[s["pack"]])
                s = pool.pop(0)
                if s["request"] in used:
                    continue
                got.append({**s, "why": f"run verdict: {name}"})
                used.add(s["request"])
            chosen += got
    rng.shuffle(chosen)
    counter = Counter()
    for s in chosen:
        counter[s["code"]] += 1
        s["id"] = f"{s['code'].upper()}{counter[s['code']]:02d}"
    return chosen


# ------------------------------------------------------------------------------------------------------------------ the sheets
def _openpyxl():
    try:
        import openpyxl
        return openpyxl
    except ImportError as exc:                                  # pragma: no cover
        raise SystemExit("openpyxl is needed for the labeling sheets: pip install openpyxl") from exc


def language_name(code: str) -> str:
    return LANGUAGES[code].name if code in LANGUAGES else code


def minutes_for(n: int) -> int:
    return max(5, math.ceil(n * 1.3 / 5) * 5)


def _lines(text: str, width: int) -> int:
    return sum(max(1, math.ceil(len(p) / width)) for p in text.split("\n"))


def _instructions(ws, name: str, n: int):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.properties import PageSetupProperties
    fill_in = PatternFill("solid", fgColor="FFF8CC")
    ws.sheet_view.showGridLines = False
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    for col, width in (("A", 4), ("B", 26), ("C", 90)):
        ws.column_dimensions[col].width = width
    row = [2]

    def put(col, text, bold=False, size=10, height=None):
        cell = ws.cell(row=row[0], column=col, value=text)
        cell.font = Font(name="Arial", size=size, bold=bold)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if height:
            ws.row_dimensions[row[0]].height = height
        return cell

    def para(text, col=2, span=True):
        put(col, text, height=15 * math.ceil(len(text) / (105 if span else 95)) + 4)
        if span:
            ws.merge_cells(start_row=row[0], start_column=2, end_row=row[0], end_column=3)
        row[0] += 1

    put(2, f"Story labeling: {name}", bold=True, size=16)
    ws.merge_cells(start_row=row[0], start_column=2, end_row=row[0], end_column=3)
    row[0] += 2
    para(f"Thank you for helping. There are {n} short {name} texts on the next tab, written by an AI for language learners. I need to know, as a reader of {name}, "
         "whether each one reads well. The automatic checks I have cannot tell me that reliably, so your judgement is the measurement.")
    para("Please work alone and trust your own reading: do not use AI tools, translators or a dictionary to decide, and do not compare notes with anyone until you have "
         "sent the file back. About 1 minute per text. Honest, critical answers help most; a polite 4 helps less than an honest 2.")
    row[0] += 1
    put(2, "What to do", bold=True, size=12)
    row[0] += 1
    steps = ["Open the tab \"Stories\". Read one text.",
             "Each text was written for a learner at the level shown (easy, medium or hard) and was asked to use some of the practice words shown. Short, simple sentences "
             "are normal at easy level: judge whether it sounds right and makes sense for that level, not whether it is sophisticated.",
             "Fill in the yellow cells of that row: Q1, Q2, Q3, and a comment if you can.",
             "In the comment, copy the phrase or sentence that bothers you most (or what you liked). This is the most useful part when you have the time.",
             "If you cannot judge a text, leave it empty and say why in the comment.",
             "Fill in the two yellow cells under \"About you\" below, save the file under a new name (add your name or initials) and send it back."]
    for i, text in enumerate(steps, 1):
        put(2, f"{i}.")
        put(3, text, height=15 * math.ceil(len(text) / 95) + 3)
        row[0] += 1
    row[0] += 1
    put(2, "The three questions", bold=True, size=12)
    row[0] += 1
    for a, b in (("Q1  Would you give this text to a learner as it is?", "Yes = as it is.  Small fix first = good idea, but something needs changing.  No = not in this state."),
                 ("Q2  How natural does it read? (1 to 5)", "Use the scale below. Judge the wording and the sense, not the topic or the length. Using many of the practice words earns no credit."),
                 ("Q3  Main problem (if any)", "Pick the one thing that bothers you most, or \"No problem\".")):
        put(2, a, bold=True)
        put(3, b, height=15 * math.ceil(len(b) / 95) + 3)
        row[0] += 1
    row[0] += 1
    put(2, "The scale for Q2", bold=True, size=12)
    row[0] += 1
    for a, b in SCALE:
        put(2, a, bold=True).alignment = Alignment(horizontal="center", vertical="top")
        put(3, b, height=15 * math.ceil(len(b) / 95) + 3)
        row[0] += 1
    row[0] += 1
    put(2, "Example (made up)", bold=True, size=12)
    row[0] += 1
    put(2, "Text")
    put(3, "I am Tom. I have a dog. The dog is big. The dog likes the park, and the park likes the dog today.", height=30)
    row[0] += 1
    put(2, "Q1 / Q2 / Q3")
    put(3, "Small fix first  /  3  /  Unnatural wording")
    row[0] += 1
    put(2, "Comment")
    put(3, "\"the park likes the dog today\" is not something a person would say; the rest is fine for easy level.", height=30)
    row[0] += 2
    put(2, "Legend", bold=True, size=12)
    row[0] += 1
    put(2, "yellow cells").fill = fill_in
    put(3, "the cells you fill in; everything else is for reading")
    row[0] += 2
    put(2, "About you", bold=True, size=12)
    row[0] += 1
    put(2, "Name or initials")
    ws.cell(row=row[0], column=3).fill = fill_in
    row[0] += 1
    put(2, f"How well do you read {name}?")
    cell = ws.cell(row=row[0], column=3)
    cell.fill = fill_in
    validation = DataValidation(type="list", formula1='"Native,Fluent,Good,Intermediate"', allow_blank=True)
    ws.add_data_validation(validation)
    validation.add(cell)
    ws.cell(row=row[0] + 1, column=3, value="Native / Fluent / Good / Intermediate").font = Font(name="Arial", size=9, italic=True, color="777777")


def _story_sheet(ws, rows: list):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.properties import PageSetupProperties
    side = Side(style="thin", color="BBBBBB")
    box = Border(left=side, right=side, top=side, bottom=side)
    heads = ["ID", "Level", "Written as", "Practice words the writer was given", "Text", "Q1  Give it to a learner as it is?", "Q2  Natural? (1-5)", "Q3  Main problem",
             "Comment (copy the phrase that bothers you most)"]
    widths = [7, 22, 18, 30, 80, 20, 12, 28, 45]
    for i, (head, width) in enumerate(zip(heads, widths), 1):
        cell = ws.cell(row=1, column=i, value=head)
        cell.font = Font(name="Arial", bold=True, size=10)
        cell.fill = PatternFill("solid", fgColor="E8EEF7")
        cell.border = box
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center" if i in (1, 6, 7) else "left")
        ws.column_dimensions[cell.column_letter].width = width
    ws.row_dimensions[1].height = 45
    for n, s in enumerate(rows, 2):
        written = KIND_TEXT.get(s["kind"], s["kind"]).capitalize() + (f": {s['topic']}" if s["topic"] else "")
        values = [s["id"], LEVEL_TEXT.get(s["level"], s["level"]), written, ", ".join(s["words"]), s["text"], None, None, None, None]
        for i, value in enumerate(values, 1):
            cell = ws.cell(row=n, column=i, value=value)
            cell.font = Font(name="Arial", size=11 if i == 5 else 10, bold=(i == 1))
            cell.border = box
            cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="center" if i in (1, 6, 7) else "left")
            if i != 5:                                  # grey: for reading; yellow: for the labeler to fill in
                cell.fill = PatternFill("solid", fgColor="F5F5F5" if i <= 4 else "FFF8CC")
        ws.row_dimensions[n].height = max(80, 15.5 * _lines(s["text"], 78) + 8)
    last = len(rows) + 1
    d1 = DataValidation(type="list", formula1='"' + ",".join(Q1_ANSWERS) + '"', allow_blank=True)
    d2 = DataValidation(type="whole", operator="between", formula1="1", formula2="5", allow_blank=True, showErrorMessage=True, errorTitle="1 to 5",
                        error="Please enter a whole number from 1 to 5.")
    d3 = DataValidation(type="list", formula1='"' + ",".join(Q3_ANSWERS) + '"', allow_blank=True)
    for validation, column in ((d1, "F"), (d2, "G"), (d3, "H")):
        ws.add_data_validation(validation)
        validation.add(f"{column}2:{column}{last}")
    ws.freeze_panes = "B2"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


def readme_text(counts: dict) -> str:
    files = "\n".join(f"{language_name(code).lower()}_stories.xlsx   {n} {language_name(code)} texts (about {minutes_for(n)} minutes)" for code, n in counts.items())
    scale = "\n".join(f"{a}  {b}" for a, b in SCALE)
    return f"""STORY LABELING: please read me first
====================================

What this is
------------
I am building a language-learning website. One part of it uses AI to write short practice texts for learners. My automatic checks cannot reliably tell whether a text reads
naturally, so I need real readers. You are the measurement: there is no right answer I am hoping for.

What is in this folder
----------------------
{files}

Do the file(s) in the language(s) you read well. Open it in Excel, or upload it to Google Drive and open it with Google Sheets. The first tab ("Read me first") has these
instructions again; the second tab ("Stories") is where you answer.

How to label (one row per text)
-------------------------------
1. Read the text. It was written for a learner at the level shown (easy, medium or hard) and was asked to use some of the practice words in the row. Short, simple
   sentences are normal at easy level: judge whether it sounds right and makes sense for that level.
2. Fill in the yellow cells:
   Q1  Would you give this text to a learner as it is?   Yes / Small fix first / No
   Q2  How natural does it read, 1 to 5?  (the scale is below)
   Q3  The main problem, if any (pick one from the list, or "No problem")
   Comment  Copy the phrase or sentence that bothers you most, or what you liked. Optional, but the most useful part when you have the time.
3. If you cannot judge a text, leave it empty and say why in the comment.
4. Fill in "About you" on the first tab (your name or initials, how well you read the language), save the file under a new name with your initials added
   (for example english_stories_AB.xlsx) and send it back to me.

The scale for Q2
----------------
{scale}
Judge the wording and the sense, not the topic or the length. Using many of the practice words earns no credit.

Please
------
- Work alone, with your own reading. Do not use AI tools, translators or a dictionary to decide, and do not compare notes with anyone until you have sent the file back:
  I am comparing independent opinions.
- Be honest and critical. A polite 4 helps me less than an honest 2.
- Do not forward these files.

Thank you.
"""


def build(chosen: list, out_dir: str) -> dict:
    """Write the blind sheets, the README and the zip, and the private key next to them. Returns {'zip', 'key', 'files', 'counts'}."""
    openpyxl = _openpyxl()
    folder = os.path.join(out_dir, "story_labeling")
    os.makedirs(folder, exist_ok=True)
    counts = Counter(s["code"] for s in chosen)
    files = []
    for code in counts:
        rows = sorted((s for s in chosen if s["code"] == code), key=lambda s: s["id"])
        wb = openpyxl.Workbook()
        first = wb.active
        first.title = "Read me first"
        _instructions(first, language_name(code), len(rows))
        _story_sheet(wb.create_sheet("Stories"), rows)
        name = f"{language_name(code).lower()}_stories.xlsx"
        wb.save(os.path.join(folder, name))
        files.append(name)
    with open(os.path.join(folder, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(readme_text(dict(counts)))
    files.append("README.txt")
    key = os.path.join(out_dir, "label_key_PRIVATE.csv")
    with open(key, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(KEY_COLUMNS)
        for s in sorted(chosen, key=lambda s: s["id"]):
            writer.writerow([s["id"], language_name(s["code"]), s["source"], s["request"], s["method"], s["level"], s["kind"], s["topic"], s["pack"], s["why"], s["verdict"],
                             s["gpt"] if s["gpt"] is not None else "", s["qwen"] if s["qwen"] is not None else "", s["free"] if s["free"] is not None else "",
                             s["reviewed"] if s["reviewed"] is not None else "", len(s["text"].split()), "|".join(s["words"])])
    zip_path = os.path.join(out_dir, "story_labeling_set.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(os.path.join(folder, name), f"story_labeling/{name}")
    return {"zip": zip_path, "key": key, "files": files, "counts": dict(counts)}


# ------------------------------------------------------------------------------------------------------------------ reading the answers
AI_NAME = re.compile(r"\b(AI|ChatGPT|GPT|Claude|Gemini|LLM|language model|assistant)\b", re.I)


def is_ai(name: str) -> bool:
    """A labeler who says in the sheet that it is a model (the 16 Nov ChatGPT file wrote 'AI-assisted benchmark (ChatGPT)' in its name cell)."""
    return bool(AI_NAME.search(name or ""))


def labeler_of(path: str, about: Optional[str]) -> str:
    """Who filled in a file: the name or initials in its 'About you' cell, else what follows 'english_stories_' in the file name, else the file name."""
    if about and str(about).strip():
        return str(about).strip()
    stem = os.path.splitext(os.path.basename(path))[0]
    tail = re.sub(r"^[A-Za-z]+_stories[_\- ]*", "", stem)
    return tail or stem


def read_sheet(path: str) -> tuple:
    """(labeler, {id: {'q1', 'q2', 'q3', 'comment'}}) from one returned file. Rows with no answer at all are left out."""
    wb = _openpyxl().load_workbook(path, data_only=True)
    about = None
    if "Read me first" in wb.sheetnames:
        sheet = wb["Read me first"]
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.strip().lower().startswith("name or initials"):
                    about = sheet.cell(row=cell.row, column=cell.column + 1).value
    sheet = wb["Stories"]
    out = {}
    for r in range(2, sheet.max_row + 1):
        ident = sheet.cell(row=r, column=1).value
        q1, q2, q3, comment = (sheet.cell(row=r, column=k).value for k in (6, 7, 8, 9))
        if not ident or (q1 in (None, "") and q2 in (None, "")):
            continue
        try:
            q2 = int(q2) if q2 not in (None, "") else None
        except (TypeError, ValueError):
            q2 = None
        out[str(ident).strip()] = {"q1": q1 if q1 in Q1_VERDICT else None, "q2": q2 if q2 in (1, 2, 3, 4, 5) else None, "q3": q3, "comment": comment or ""}
    return labeler_of(path, about), out


def read_labels(paths: Iterable[str]) -> dict:
    """{labeler: {id: answer}} from files and folders (a folder: every .xlsx in it, one level down too). A person's English and Spanish files are merged."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in sorted(names) if n.lower().endswith(".xlsx") and not n.startswith("~$")]
        else:
            files.append(p)
    out = defaultdict(dict)
    for f in sorted(files):
        who, answers = read_sheet(f)
        if answers:                                       # a sheet nobody filled in is not a labeler
            out[who].update(answers)
    return dict(out)


def read_key(path: str) -> dict:
    """{id: key row} with the ratings and scores turned into numbers."""
    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    rows = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            r["gpt"], r["qwen"], r["free"], r["reviewed"] = (num(r.get(k)) for k in ("gpt_rating", "qwen_rating", "free_score", "reviewed_score"))
            rows[r["id"]] = r
    return rows


# ------------------------------------------------------------------------------------------------------------------ comparing
def _mean(values: list) -> Optional[float]:
    return sum(values) / len(values) if values else None


def compare(key: dict, labels: dict, humans_only: bool = False) -> dict:
    """Numbers only: how the labelers agree with each other, how the reviewers and the free score agree with them, and (for the texts picked as a method comparison)
    how the methods rate. `labels` is {labeler: {id: answer}} from read_labels. With `humans_only`, a labeler that says it is a model (is_ai) is left out."""
    excluded = sorted(w for w in labels if humans_only and is_ai(w))
    labels = {w: a for w, a in labels.items() if w not in excluded}
    who = sorted(labels)
    out = {"labelers": {}, "pairs": [], "reviewers": {}, "unanimous": {}, "methods": [], "paired": [], "excluded": excluded}
    for w in who:
        q2 = [a["q2"] for a in labels[w].values() if a["q2"] is not None]
        q1 = Counter(Q1_VERDICT[a["q1"]] for a in labels[w].values() if a["q1"])
        out["labelers"][w] = {"ai": is_ai(w), "texts": len(labels[w]), "q1": dict(q1), "q2_mean": _mean(q2), "q2_fail_share": (sum(x <= FAIL_AT for x in q2) / len(q2)) if q2 else None,
                              "q3": dict(Counter(a["q3"] for a in labels[w].values() if a["q3"]))}
    for i, a in enumerate(who):
        for b in who[i + 1:]:
            ids = [x for x in labels[a] if x in labels[b] and labels[a][x]["q2"] is not None and labels[b][x]["q2"] is not None]
            if not ids:
                continue
            qa, qb = [labels[a][x]["q2"] for x in ids], [labels[b][x]["q2"] for x in ids]
            same = [x for x in ids if labels[a][x]["q1"] and labels[b][x]["q1"]]
            out["pairs"].append({"a": a, "b": b, "texts": len(ids), "spearman": stats.spearman(qa, qb), "q2_identical": sum(x == y for x, y in zip(qa, qb)) / len(ids),
                                 "q2_within_one": sum(abs(x - y) <= 1 for x, y in zip(qa, qb)) / len(ids),
                                 "pass_fail_agree": sum((x <= FAIL_AT) == (y <= FAIL_AT) for x, y in zip(qa, qb)) / len(ids),
                                 "q1_identical": (sum(labels[a][x]["q1"] == labels[b][x]["q1"] for x in same) / len(same)) if same else None})
    human = {}                                        # id -> mean Q2 over the labelers who rated it
    for ident in key:
        values = [labels[w][ident]["q2"] for w in who if ident in labels[w] and labels[w][ident]["q2"] is not None]
        if values:
            human[ident] = _mean(values)
    for name, field in (("gpt rating", "gpt"), ("qwen rating", "qwen"), ("free score", "free"), ("reviewed score", "reviewed")):
        ids = [i for i in human if key[i].get(field) is not None]
        slot = {"texts": len(ids), "spearman": stats.spearman([key[i][field] for i in ids], [human[i] for i in ids]) if ids else None}
        if field in ("gpt", "qwen"):
            slot["pass_fail_agree"] = {w: _agree([i for i in ids if i in labels[w] and labels[w][i]["q2"] is not None], key, labels[w], field) for w in who}
            slot["mean_minus_labeler"] = {w: _mean([key[i][field] - labels[w][i]["q2"] for i in ids if i in labels[w] and labels[w][i]["q2"] is not None]) for w in who}
        out["reviewers"][name] = slot
    for kind in (verdicts.PASS, verdicts.SPLIT, verdicts.FAIL):
        ids = [i for i in human if key[i]["run_verdict"] == kind]
        tally = Counter()
        for i in ids:
            for w in who:
                if i in labels[w] and labels[w][i]["q1"]:
                    tally[Q1_VERDICT[labels[w][i]["q1"]]] += 1
        out["unanimous"][kind] = {"texts": len(ids), "labeler_answers": dict(tally),
                                  "any_labeler_disagrees": sum(any(i in labels[w] and labels[w][i]["q1"] and (Q1_VERDICT[labels[w][i]["q1"]] == opposite(kind)) for w in who) for i in ids)}
    methods = defaultdict(list)
    for i, row in key.items():
        if i in human and row["why_chosen"] in METHOD_SETS:
            methods[row["method"]].append(i)
    for m, ids in methods.items():
        answers = [labels[w][i] for i in ids for w in who if i in labels[w]]
        out["methods"].append({"method": m, "texts": len(ids), "q2_mean": _mean([human[i] for i in ids]),
                               "yes": sum(a["q1"] == "Yes" for a in answers), "fix": sum(a["q1"] == "Small fix first" for a in answers), "no": sum(a["q1"] == "No" for a in answers),
                               "answers": len(answers), "run_verdicts": dict(Counter(key[i]["run_verdict"] for i in ids))})
    by_request = defaultdict(dict)
    for i in human:
        if key[i]["why_chosen"] in METHOD_SETS:
            by_request[(key[i]["language"], key[i]["request"])][key[i]["method"]] = human[i]
    for (language, request), row in by_request.items():
        if "baseline" in row:
            out["paired"].append({"request": request, "language": language, "baseline": row["baseline"],
                                  "minus_baseline": {m: v - row["baseline"] for m, v in row.items() if m != "baseline"}})
    return out


def opposite(kind: str) -> Optional[str]:
    return {verdicts.PASS: verdicts.FAIL, verdicts.FAIL: verdicts.PASS}.get(kind)


def _agree(ids: list, key: dict, answers: dict, field: str) -> Optional[float]:
    return sum((key[i][field] <= FAIL_AT) == (answers[i]["q2"] <= FAIL_AT) for i in ids) / len(ids) if ids else None


def joined_rows(key: dict, labels: dict) -> list:
    """One row per text: the key, then each labeler's three answers and comment, for a spreadsheet."""
    who = sorted(labels)
    rows = []
    for i, k in key.items():
        row = {c: k.get(c, "") for c in KEY_COLUMNS if c != "practice_words"}
        for w in who:
            a = labels[w].get(i) or {}
            row.update({f"{w}_q1": a.get("q1"), f"{w}_q2": a.get("q2"), f"{w}_q3": a.get("q3"), f"{w}_comment": a.get("comment")})
        rows.append(row)
    return rows


def _p(x: Optional[float], digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def _pc(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def text_report(result: dict) -> str:
    out = ["Human labels against the model reviewers", ""]
    if result.get("excluded"):
        out += ["Left out (they say they are a model): " + ", ".join(result["excluded"]), ""]
    out.append("Each labeler")
    for w, s in result["labelers"].items():
        q1 = s["q1"]
        out.append(f"  {w}{' [says it is an AI]' if s.get('ai') else ''}: {s['texts']} texts; Yes/Small fix/No = {q1.get('pass', 0)}/{q1.get('split', 0)}/{q1.get('fail', 0)}; mean rating {_p(s['q2_mean'])}; rated 2 or less: {_pc(s['q2_fail_share'])}")
    if result["pairs"]:
        out += ["", "Two labelers on the same texts (rank correlation of the 1 to 5 ratings, ratings within one point, same pass/fail, same Q1 answer)"]
        for p in result["pairs"]:
            out.append(f"  {p['a']} and {p['b']}: {p['texts']} texts, {_p(p['spearman'])}, {_pc(p['q2_within_one'])}, {_pc(p['pass_fail_agree'])}, {_pc(p['q1_identical'])}")
    out += ["", "The reviewers and the free score against the labelers' mean rating (rank correlation)"]
    for name, s in result["reviewers"].items():
        extra = ""
        if "pass_fail_agree" in s:
            extra = "; same pass/fail as " + ", ".join(f"{w} {_pc(v)}" for w, v in s["pass_fail_agree"].items())
        out.append(f"  {name}: {_p(s['spearman'])} over {s['texts']} texts{extra}")
    out += ["", "When the reviewers agreed (run verdict), what the labelers answered"]
    for kind, s in result["unanimous"].items():
        a = s["labeler_answers"]
        out.append(f"  {kind:5} {s['texts']} texts: Yes {a.get('pass', 0)}, Small fix {a.get('split', 0)}, No {a.get('fail', 0)}"
                   + (f"; texts where a labeler said the opposite: {s['any_labeler_disagrees']}" if kind != verdicts.SPLIT else ""))
    if result["methods"]:
        out += ["", "The methods on the same requests (the labelers' mean rating; Yes / Small fix / No answers)"]
        for m in sorted(result["methods"], key=lambda m: -(m["q2_mean"] or 0)):
            out.append(f"  {m['method']:18} {m['texts']} texts  rating {_p(m['q2_mean'])}  {m['yes']}/{m['fix']}/{m['no']} of {m['answers']}")
        for p in result["paired"]:
            out.append(f"    {p['language']} {p['request']}: baseline {_p(p['baseline'], 1)}; " + ", ".join(f"{m} {v:+.1f}" for m, v in p["minus_baseline"].items()))
    return "\n".join(out) + "\n"
