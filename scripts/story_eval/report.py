"""The numbers and the page for a story-methods run (7 Nov 2026). Works from the saved JSON alone, so a run can be re-scored or re-drawn
later with no model calls."""
from __future__ import annotations

import copy
import html

from tutor_core import difficulty as _d
from tutor_core.languages import LANGUAGES
from tutor_core.quality import score_story
from tutor_core.quality.score import merge_reviews
from tutor_core.quality.grammar import Hit

PART_LABELS = {"length": "Length", "own_words": "Your words", "uncommon": "Uncommon words", "sentence_length": "Sentence length",
               "grammar": "Grammar, fluency", "language_format": "Language, format"}
PASS_PART = 80.0        # a story passes when it is not gated and every measured part is at least this


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def passes(score) -> bool:
    if not score or score.get("gated"):
        return False
    return all(v >= PASS_PART for v in score["parts"].values() if v is not None)


def entries(data: dict, variant: str, code: str = None):
    by_id = {r["id"]: r for r in data["requests"]}
    for rid, row in data["results"].items():
        if variant in row and (code is None or by_id[rid]["code"] == code):
            yield by_id[rid], row[variant]


def stats(data: dict, variant: str, code: str = None) -> dict:
    """Averages for one method (over one language, or all): score, pass rate, each part, calls and seconds, grammar mistakes found."""
    items = [e for _, e in entries(data, variant, code)]
    made = [e for e in items if e["ok"]]
    scored = [e["score"] for e in made if e["score"]]
    audited = [e for e in made if e.get("audit") and e["audit"].get("ok")]
    return {"requests": len(items), "stories": len(made), "score": _mean([s["score"] for s in scored]),
            "audit_score": _mean([(e.get("audit_union") or e["audit_score"])["score"] for e in audited if e.get("audit_union") or e.get("audit_score")]),
            "pass_rate": round(sum(1 for s in scored if passes(s)) / len(items), 3) if items else None,
            "parts": {k: _mean([s["parts"].get(k) for s in scored]) for k in PART_LABELS},
            "calls": _mean([e["calls"] for e in items]), "model_seconds": _mean([e["model_seconds"] for e in items]),
            "seconds": _mean([e["seconds"] for e in items]),
            "mistakes_found": _mean([len(e["audit"]["hits"]) for e in audited]) if audited else None}


def rescore(data: dict) -> dict:
    """The same run with every story scored again by the current score (and the saved model review's findings). No model calls."""
    data = copy.deepcopy(data)
    by_id = {r["id"]: r for r in data["requests"]}
    for rid, row in data["results"].items():
        r = by_id[rid]
        for entry in row.values():
            if not entry.get("ok") or not entry.get("text"):
                continue
            args = (entry["text"], r["code"], r["words"], _d.resolve(r["tier"]), r.get("story_type"))
            entry["score"] = score_story(*args)
            hits = [Hit(**h) for h in (entry.get("audit") or {}).get("hits", [])]
            entry["audit_score"] = score_story(*args, hits=hits) if entry.get("audit", {}) and entry["audit"].get("ok") else None
            entry["audit_scores"] = {}
            for label, review in (entry.get("audits") or {}).items():
                if review.get("ok"):
                    entry["audit_scores"][label] = score_story(*args, hits=[Hit(**h) for h in review.get("hits", [])])
            entry["audit_union"] = None
            if len(entry["audit_scores"]) > 1:       # the findings of every reviewer together: each misses things the others find
                joined = merge_reviews(*([Hit(**h) for h in r.get("hits", [])] for r in entry["audits"].values() if r.get("ok")))
                entry["audit_union"] = score_story(*args, hits=joined)
    return data


def _fmt(v, pct=False):
    if v is None:
        return "–"
    return f"{v * 100:.0f}%" if pct else f"{v:g}"


def _bars(sc):
    if not sc:
        return ""
    rows = []
    for key, label in PART_LABELS.items():
        v = sc["parts"].get(key)
        rows.append(f"<tr><td>{label}</td><td class=bar><i style='width:{0 if v is None else v}%'></i></td><td class=n>{'–' if v is None else f'{v:g}'}</td></tr>")
    return f"<table class=parts>{''.join(rows)}</table>"


def _card(variant: dict, e: dict, best: bool) -> str:
    sc, au = e.get("score"), e.get("audit_union") or e.get("audit_score")
    if sc is None:
        big = "<div class=score>–</div>"
    elif sc["gated"]:
        big = f"<div class='score zero'>0 <small>gate: {html.escape(sc['gated'])}</small></div>"
    else:
        extra = f" · with model review {au['score']:g}" if au else ""
        big = f"<div class=score>{sc['score']:g}<small> / 100{extra}</small></div>"
    badge = " <span class=win>highest</span>" if best else ""
    bad = "" if e["ok"] else f"<p class=bad>No story ({html.escape(str(e['reason']))}). {html.escape(e.get('error') or '')}</p>"
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in e.get("notes") or [])
    found = ""
    if e.get("audit") and e["audit"].get("ok"):
        hits = e["audit"]["hits"]
        lis = "".join(f"<li>“{html.escape(h['wrong'])}” → “{html.escape(h['fix'])}” <i>{html.escape(h['note'])}</i></li>" for h in hits)
        found = f"<details><summary>Model review: {len(hits)} mistake(s)</summary><ul>{lis}</ul></details>"
    elif e.get("audit"):
        found = f"<p class=num>Model review gave no usable answer ({html.escape(e['audit'].get('error') or '')[:80]}).</p>"
    for label, review in list((e.get("audits") or {}).items())[1:]:
        if review.get("ok"):
            lis = "".join(f"<li>“{html.escape(h['wrong'])}” → “{html.escape(h['fix'])}” <i>{html.escape(h['note'])}</i></li>" for h in review["hits"])
            found += f"<details><summary>Review by {html.escape(label)}: {len(review['hits'])} mistake(s)</summary><ul>{lis}</ul></details>"
    first = next(iter(e.get("audits") or {}), None)
    if first and len(e["audits"]) > 1:
        found = found.replace("Model review:", f"Review by {html.escape(first)}:", 1)
    gate = e.get("gate")
    if gate is not None:
        found += (f"<p class=num>Free checks: {'passed' if gate['passed'] else 'FAILED ' + html.escape(', '.join(gate['failed']))}"
                  f" (own words {gate['limits']['own_min']}–{gate['limits']['own_max']})</p>")
    if e["ok"] and not e.get("audit"):
        found += "<p class=num>Grammar not reviewed by a model: the score cannot see most mistakes.</p>"
    rules = ""
    if sc and sc.get("grammar_hits"):
        lis = "".join(f"<li>“{html.escape(h['wrong'])}” → “{html.escape(h['fix'])}” <i>{html.escape(h['rule'])}</i></li>" for h in sc["grammar_hits"])
        rules = f"<details><summary>Rules found {len(sc['grammar_hits'])} mistake(s)</summary><ul>{lis}</ul></details>"
    tr = (f"<details><summary>English translation (machine, a rough guide)</summary><div class=text>{html.escape(e['translation'])}</div></details>"
          if e.get("translation") else "")
    return (f"<div class=card><h4>{html.escape(variant['label'])}{badge}</h4>{big}<div class=text>{html.escape(e['text'])}</div>{bad}{tr}{rules}{found}"
            f"{_bars(sc)}<p class=num>{e['calls']} call(s) · {e['model_seconds']} s in the model · {e['seconds']} s in all (waiting {e['wait_seconds']} s)</p>"
            f"{'<ul class=notes>' + notes + '</ul>' if notes else ''}</div>")


CSS = ("body{font:16px/1.5 system-ui,sans-serif;max-width:1400px;margin:1.5rem auto;padding:0 1rem;color:#1c1c1c;background:#fff}"
       "nav{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0;border-bottom:1px solid #ccc;padding-bottom:.6rem}"
       "nav button{font:inherit;padding:.4rem .9rem;border:1px solid #bbb;border-radius:6px;background:#f4f4f1;cursor:pointer}"
       "nav button[aria-selected=true]{background:#1c1c1c;color:#fff;border-color:#1c1c1c}"
       ".row{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1rem;margin-bottom:1.6rem}.card{border:1px solid #ccc;border-radius:8px;padding:1rem}"
       ".card h4{margin:.1rem 0 .3rem}.score{font-size:2rem;font-weight:700}.score small{font-size:.8rem;font-weight:400;color:#555}.score.zero{color:#a00}"
       ".text{white-space:pre-wrap;background:#f7f7f4;padding:.8rem;border-radius:6px;margin:.5rem 0}.num{font-size:.85rem;color:#555;margin:.4rem 0}"
       ".bad{color:#a00}.win{font-size:.75rem;background:#d9f0df;color:#145a2a;padding:.1rem .45rem;border-radius:99px;margin-left:.4rem}"
       "table.parts{width:100%;border-collapse:collapse;font-size:.85rem}.parts td{padding:.1rem .3rem}.parts .bar{width:50%;background:#ececE6;border-radius:4px}"
       ".parts .bar i{display:block;height:.6rem;background:#2f7d4f;border-radius:4px}.parts .n{text-align:right;width:4rem}"
       "table.sum{border-collapse:collapse;width:100%;margin:.6rem 0 1.4rem}.sum th,.sum td{border:1px solid #ccc;padding:.35rem .6rem;text-align:left}"
       ".notes,details ul{font-size:.8rem;color:#555}details summary{cursor:pointer;font-size:.85rem;color:#444}.panel[hidden]{display:none}")
JS = ("<script>(function(){var b=document.querySelectorAll('nav button'),p=document.querySelectorAll('.panel');"
      "function show(k){b.forEach(function(x){x.setAttribute('aria-selected',x.dataset.tab===k?'true':'false')});"
      "p.forEach(function(x){x.hidden=x.id!=='p-'+k});history.replaceState(null,'','#'+k)}"
      "b.forEach(function(x){x.addEventListener('click',function(){show(x.dataset.tab)})});"
      "var h=location.hash.slice(1);show(document.getElementById('p-'+h)?h:'summary')})();</script>")


def reviewer_table(data: dict) -> str:
    """Reviewers side by side: how many mistakes each finds, the score with its findings, its time, and how often two reviewers agree
    that a story has (or has no) mistake. Empty when no run used --audit-models."""
    labels = list(dict.fromkeys(l for row in data["results"].values() for e in row.values() for l in (e.get("audits") or {})))
    if not labels:
        return ""
    allx = [e for row in data["results"].values() for e in row.values() if e.get("ok")]
    head = "<tr><th>Reviewer</th><th>Stories reviewed</th><th>Mistakes per story</th><th>Stories with a mistake</th><th>Score with its review</th><th>Seconds per review</th><th>No usable answer</th></tr>"
    rows = []
    for l in labels:
        rs = [e["audits"][l] for e in allx if l in (e.get("audits") or {})]
        good = [r for r in rs if r.get("ok")]
        rows.append(f"<tr><td><b>{html.escape(l)}</b></td><td>{len(good)}</td><td>{_fmt(_mean([len(r['hits']) for r in good]))}</td>"
                    f"<td>{_fmt(round(sum(1 for r in good if r['hits']) / len(good), 3) if good else None, True)}</td>"
                    f"<td>{_fmt(_mean([e['audit_scores'][l]['score'] for e in allx if l in (e.get('audit_scores') or {})]))}</td>"
                    f"<td>{_fmt(_mean([r.get('seconds') for r in rs]))}</td><td>{len(rs) - len(good)}</td></tr>")
    if len(labels) > 1:
        rows.append(f"<tr><td><b>both together</b></td><td></td><td></td><td></td><td>{_fmt(_mean([e['audit_union']['score'] for e in allx if e.get('audit_union')]))}</td><td></td><td></td></tr>")
    agree = ""
    if len(labels) > 1:
        a, b = labels[0], labels[1]
        both = [e for e in allx if all((e.get("audits") or {}).get(x, {}).get("ok") for x in (a, b))]
        same = sum(1 for e in both if bool(e["audits"][a]["hits"]) == bool(e["audits"][b]["hits"]))
        agree = f"<p class=num>{html.escape(a)} and {html.escape(b)} agree on whether a story has any mistake in {same} of {len(both)} stories.</p>"
    cross = ""
    names = [v["name"] for v in data["variants"]]
    if len(labels) > 1:
        lines = "".join(f"<tr><td>{html.escape(v['label'])}</td>" + "".join(
            f"<td>{_fmt(_mean([len(e['audits'][l]['hits']) for _, e in entries(data, v['name']) if e.get('ok') and (e.get('audits') or {}).get(l, {}).get('ok')]))}</td>"
            for l in labels) + "</tr>" for v in data["variants"] if v["name"] in names)
        cross = ("<h3>Mistakes found per story, by method and reviewer</h3><table class=sum><tr><th>Method</th>"
                 + "".join(f"<th>{html.escape(l)}</th>" for l in labels) + f"</tr>{lines}</table>")
    return f"<h3>Reviewers compared</h3><table class=sum>{head}{''.join(rows)}</table>{agree}{cross}"


def _summary(data: dict) -> str:
    variants = data["variants"]
    base = stats(data, variants[0]["name"]) if variants else {}
    head = ("<tr><th>Method</th><th>What it adds</th><th>Stories</th><th>Mean score</th><th>vs first</th><th>With model review</th><th>Pass rate</th>"
            + "".join(f"<th>{l}</th>" for l in PART_LABELS.values()) + "<th>Calls</th><th>Seconds in model</th><th>Seconds in all</th><th>Mistakes found</th></tr>")
    rows = []
    for v in variants:
        s = stats(data, v["name"])
        delta = None if s["score"] is None or base.get("score") is None else round(s["score"] - base["score"], 1)
        rows.append(f"<tr><td><b>{html.escape(v['label'])}</b></td><td>{html.escape(v['note'])}</td><td>{s['stories']}/{s['requests']}</td><td>{_fmt(s['score'])}</td>"
                    f"<td>{'–' if delta is None else f'{delta:+g}'}</td><td>{_fmt(s['audit_score'])}</td><td>{_fmt(s['pass_rate'], True)}</td>"
                    + "".join(f"<td>{_fmt(s['parts'][k])}</td>" for k in PART_LABELS)
                    + f"<td>{_fmt(s['calls'])}</td><td>{_fmt(s['model_seconds'])}</td><td>{_fmt(s['seconds'])}</td><td>{_fmt(s['mistakes_found'])}</td></tr>")
    codes = list(dict.fromkeys(r["code"] for r in data["requests"]))
    lang_head = "<tr><th>Language</th>" + "".join(f"<th>{html.escape(v['label'])}</th>" for v in variants) + "</tr>"
    lang_rows = "".join(f"<tr><td>{html.escape(LANGUAGES[c].name)}</td>" + "".join(f"<td>{_fmt(stats(data, v['name'], c)['score'])}</td>" for v in variants) + "</tr>" for c in codes)
    meta = data.get("meta") or {}
    models = ", ".join(f"{k}: {v}" for k, v in meta.items() if v)
    return ("<h2>Summary</h2><p>Mean story score 0 to 100 (score version "
            f"{meta.get('score_version', '?')}), pass rate (not gated and every part at least {PASS_PART:g}), average model calls and seconds per story. "
            "“Seconds in model” is time inside model calls; “seconds in all” also counts waiting for the free tier’s rate limit. "
            "The model review column appears only when the run used --audit: an independent model lists grammar mistakes in each final story, and the score is "
            "computed again with them.</p>" + (f"<p class=num>{html.escape(models)}</p>" if models else "")
            + f"<table class=sum>{head}{''.join(rows)}</table>{reviewer_table(data)}<h3>Mean score by language</h3><table class=sum>{lang_head}{lang_rows}</table>")


def render(data: dict) -> str:
    variants = data["variants"]
    codes = list(dict.fromkeys(r["code"] for r in data["requests"]))
    tabs, panels = [("summary", "Summary")], [("summary", _summary(data))]
    for code in codes:
        body = [f"<h2>{html.escape(LANGUAGES[code].name)}</h2>"]
        for r in (r for r in data["requests"] if r["code"] == code):
            row = data["results"].get(r["id"], {})
            if not row:
                continue
            top = max((((e.get("score") or {}).get("score") or -1) for e in row.values()), default=-1)
            cards = "".join(_card(v, row[v["name"]], ((row[v["name"]].get("score") or {}).get("score") or -1) == top and top > 0)
                            for v in variants if v["name"] in row)
            body.append(f"<h3>{html.escape(r['id'])}: {r['tier']} · {r['story_type']} · {html.escape(r['topic'])}</h3>"
                        f"<p class=num>Words: {html.escape(', '.join(r['words']))}</p><div class=row>{cards}</div>")
        tabs.append((code, LANGUAGES[code].name))
        panels.append((code, "".join(body)))
    nav = "".join(f"<button role=tab aria-selected={'true' if i == 0 else 'false'} data-tab='{html.escape(c)}'>{html.escape(t)}</button>" for i, (c, t) in enumerate(tabs))
    sections = "".join(f"<section class=panel id='p-{html.escape(c)}'>{b}</section>" for c, b in panels)
    return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Story methods compared</title>"
            f"<style>{CSS}</style><h1>Story methods compared</h1><p>The same requests (words, level, kind, topic) made with each method, scored 0 to 100. "
            f"A column is one method; each adds one thing to the one before it.</p><nav role=tablist>{nav}</nav>{sections}{JS}")
