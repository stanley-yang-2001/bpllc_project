"""The numbers and the page for a story-methods run (7 Nov 2026). Works from the saved JSON alone, so a run can be re-scored or re-drawn
later with no model calls."""
from __future__ import annotations

import copy
import html

from tutor_core import difficulty as _d
from tutor_core.languages import LANGUAGES
from tutor_core.quality import score_story
from tutor_core.naturalness import combine as combine_ratings
from tutor_core.quality.score import merge_reviews
from tutor_core.quality.grammar import Hit

from . import fit, health, stats as st, verdicts

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


def review_counts(stories) -> dict:
    """Over every story and every reviewer: how many reviews there were, how many FAILED the story (a naturalness rating of 2 or less, too many mistakes, stuffing,
    anything the score fails a story for) and the mean 1 to 5 rating. The mean score alone misleads: a failed review roughly halves the score, so the mean mostly counts
    how many ratings fell on 2 instead of 3 (13 Nov Kaggle run: means 63.0 and 66.5, failed reviews 8 and 8)."""
    scores = [sc for e in stories if e.get("ok") for sc in (e.get("audit_scores") or {}).values()]
    ratings = [(r.get("naturalness") or {}).get("score") for e in stories if e.get("ok") for r in (e.get("audits") or {}).values()]
    return {"reviews": len(scores), "failed_reviews": sum(1 for sc in scores if verdicts.failed(sc)), "naturalness": _mean(ratings)}


def stats(data: dict, variant: str, code: str = None) -> dict:
    """Averages for one method (over one language, or all): score, pass rate, each part, calls and seconds, grammar mistakes found."""
    items = [e for _, e in entries(data, variant, code)]
    made = [e for e in items if e["ok"]]
    scored = [e["score"] for e in made if e["score"]]
    audited = [e for e in made if e.get("audit") and e["audit"].get("ok")]
    return {"requests": len(items), "stories": len(made), "score": _mean([s["score"] for s in scored]),
            "reviewed_score": _mean([verdicts.reviewed_score(e) for e in made]),
            "audit_score": _mean([(e.get("audit_union") or e["audit_score"])["score"] for e in audited if e.get("audit_union") or e.get("audit_score")]),
            "pass_rate": round(sum(1 for s in scored if passes(s)) / len(items), 3) if items else None,
            "parts": {k: _mean([s["parts"].get(k) for s in scored]) for k in PART_LABELS},
            "calls": _mean([e["calls"] for e in items]), "model_seconds": _mean([e["model_seconds"] for e in items]),
            "seconds": _mean([e["seconds"] for e in items]),
            "mistakes_found": _mean([len(e["audit"]["hits"]) for e in audited]) if audited else None,
            "own_words": _mean([(s.get("measured") or {}).get("own_words") for s in scored]), "words": _mean([(s.get("measured") or {}).get("length") for s in scored]),
            **review_counts(made)}


def _rescore_reviews(args, audits: dict):
    """(score by reviewer, score with every reviewer's findings together) for one text, from the saved reviews."""
    scores = {}
    for label, review in audits.items():
        nat = (review.get("naturalness") or {}).get("score")
        if review.get("ok") or nat is not None:
            scores[label] = score_story(*args, hits=[Hit(**h) for h in review.get("hits", [])] if review.get("ok") else None, naturalness=nat)
    union = None
    if len(scores) > 1:       # the findings of every reviewer together: each misses things the others find
        joined = merge_reviews(*([Hit(**h) for h in r.get("hits", [])] for r in audits.values() if r.get("ok")))
        union = score_story(*args, hits=joined, naturalness=combine_ratings([(r.get("naturalness") or {}).get("score") for r in audits.values()]))
    return scores, union


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
            entry["audit_scores"], entry["audit_union"] = _rescore_reviews(args, entry.get("audits") or {})
            draft = entry.get("draft")
            if draft and draft.get("changed") and draft.get("text"):          # the refine loop's first draft, scored and reviewed the same way
                draft_args = (draft["text"],) + args[1:]
                draft["score"] = score_story(*draft_args)
                if draft.get("audits"):
                    draft["audit_scores"], draft["audit_union"] = _rescore_reviews(draft_args, draft["audits"])
    return data


def _fmt(v, pct=False):
    if v is None:
        return "–"
    return f"{v * 100:.0f}%" if pct else f"{v:g}"


def _trace(e) -> str:
    """The refine loop, phase by phase (patch 0073): what each tool saw, which sentences were flagged, what the model sent back, and why a rewrite was kept or thrown away."""
    steps = e.get("trace") or []
    if not steps:
        return ""
    out = []
    for t in steps:
        ph = t["phase"]
        if ph == "observe":
            tools = "; ".join(f"{html.escape(x['tool'])}: {x['found']}" + (f" (error: {html.escape(str(x['error'])[:60])})" if x.get("error") else "") for x in t["tools"])
            hits = "".join(f"<li>“{html.escape(h['wrong'])}” → “{html.escape(h['fix'])}” <i>{html.escape(h['note'])}</i></li>" for h in t["hits"])
            gates = f" · free checks failed: {html.escape(', '.join(t['gates']))}" if t["gates"] else ""
            rated = t.get("naturalness") or {}
            nat = f" · naturalness {rated['score']:g}/5" if rated.get("ok") else ""
            out.append(f"<li><b>Observe ({html.escape(t['label'])})</b>: score {t['score']['score']:g}; {tools}{nat}{gates}" + (f"<ul>{hits}</ul>" if hits else "") + "</li>")
        elif ph == "code fix":
            out.append(f"<li><b>Code fix</b>: {len(t['changes'])} certain mistake(s) fixed with no model call</li>")
        elif ph == "plan":
            fl = "".join(f"<li>sentence {f['sentence']}: {html.escape(f['text'])}<br><i>{html.escape('; '.join(f['problems']))}</i></li>" for f in t["flagged"])
            wt = "".join(f"<li>{html.escape(r)}</li>" for r in t["whole_text"])
            out.append(f"<li><b>Plan, round {t['round']}</b>: {len(t['flagged'])} sentence(s) flagged, {len(t['whole_text'])} whole-text need(s){' (measured, left alone)' if t.get('whole_text_repaired') is False else ''}<ul>{fl}{wt}</ul></li>")
        elif ph == "repair":
            body = html.escape(t.get("error") or "") or f"<div class=text>{html.escape(t.get('reply') or '')}</div>"
            out.append(f"<li><b>Repair, round {t['round']}</b> (one model call){'' if t.get('error') else ': the model sent back'}{body}</li>")
        elif ph == "verify":
            verdict = "KEPT" if t.get("kept") else "THROWN AWAY"
            why = f" ({html.escape(t['reason'])})" if t.get("reason") else ""
            nums = f", score {t['before']:g} → {t['after']:g}" if "after" in t else ""
            if t.get("naturalness_before") is not None and t.get("naturalness_after") is not None:
                nums += f", naturalness {t['naturalness_before']:g} → {t['naturalness_after']:g}"
            share = f", {round(t['unchanged_share'] * 100)}% of the other sentences untouched" if "unchanged_share" in t else ""
            still = f", still in the text: {html.escape('; '.join(t['findings_still_in_text']))}" if t.get("findings_still_in_text") else ""
            out.append(f"<li><b>Verify, round {t['round']}</b>: {verdict}{why}{nums}{share}{still}</li>")
    return f"<details open><summary>Pipeline detail: {len(steps)} step(s)</summary><ol>{''.join(out)}</ol></details>"


def _bars(sc):
    if not sc:
        return ""
    rows = []
    for key, label in PART_LABELS.items():
        v = sc["parts"].get(key)
        rows.append(f"<tr><td>{label}</td><td class=bar><i style='width:{0 if v is None else v}%'></i></td><td class=n>{'–' if v is None else f'{v:g}'}</td></tr>")
    return f"<table class=parts>{''.join(rows)}</table>"


def _verdict_text(v) -> str:
    who, bad = v["reviewers"], v["failed"]
    ok = [x for x in who if x not in bad]
    if v["kind"] == verdicts.PASS:
        return "passed by " + (f"all {len(who)} reviewers" if len(who) > 2 else "both reviewers" if len(who) == 2 else who[0])
    if v["kind"] == verdicts.FAIL:
        return "failed by " + (f"all {len(who)} reviewers" if len(who) > 2 else "both reviewers" if len(who) == 2 else who[0])
    return f"failed by {', '.join(bad)}; passed by {', '.join(ok)}"


def _card(variant: dict, e: dict, best: bool) -> str:
    sc = e.get("score")
    shown, v = verdicts.reviewed_score(e), verdicts.verdict(e)
    if sc is None:
        big = "<div class=score>–</div>"
    elif sc["gated"]:
        big = f"<div class='score zero'>0 <small>gate: {html.escape(sc['gated'])}</small></div>"
    elif shown is not None and v is not None:
        big = (f"<div class=score>{shown:g}<small> / 100 with model review</small></div>"
               f"<p class=num><span class='chip v-{v['kind']}'>{html.escape(_verdict_text(v))}</span> free checks alone: {sc['score']:g}</p>")
    else:
        big = f"<div class=score>{sc['score']:g}<small> / 100 · free checks only, not reviewed</small></div>"
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
    ratings = [(l, r["naturalness"]) for l, r in (e.get("audits") or {}).items() if (r.get("naturalness") or {}).get("ok")]
    if ratings:
        found += "<p class=num>Naturalness: " + "; ".join(f"{html.escape(l)} {n['score']:g}/5" + (f" ({html.escape(n['reason'])})" if n.get("reason") else "") for l, n in ratings) + "</p>"
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
    return (f"<div class=card><h4>{html.escape(variant['label'])}{badge}</h4>{big}<div class=text>{html.escape(e['text'])}</div>{bad}{tr}{rules}{found}{_trace(e)}"
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
       ".chip{font-size:.78rem;padding:.1rem .5rem;border-radius:99px}.v-pass{background:#d9f0df;color:#145a2a}.v-split{background:#fdecc8;color:#6b4300}.v-fail{background:#fbdcdc;color:#8a1111}"
       ".grid td{text-align:center}.warnbox{border:2px solid #b42318;padding:.6rem 1rem;margin:1rem 0}"
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
    head = "<tr><th>Reviewer</th><th>Stories reviewed</th><th>Mistakes per story</th><th>Stories with a mistake</th><th>Naturalness (1-5)</th><th>Score with its review</th><th>Seconds per review</th><th>No usable answer</th></tr>"
    rows = []
    for l in labels:
        rs = [e["audits"][l] for e in allx if l in (e.get("audits") or {})]
        good = [r for r in rs if r.get("ok")]
        rows.append(f"<tr><td><b>{html.escape(l)}</b></td><td>{len(good)}</td><td>{_fmt(_mean([len(r['hits']) for r in good]))}</td>"
                    f"<td>{_fmt(round(sum(1 for r in good if r['hits']) / len(good), 3) if good else None, True)}</td>"
                    f"<td>{_fmt(_mean([(e['audits'][l].get('naturalness') or {}).get('score') for e in allx if l in (e.get('audits') or {})]))}</td>"
                    f"<td>{_fmt(_mean([e['audit_scores'][l]['score'] for e in allx if l in (e.get('audit_scores') or {})]))}</td>"
                    f"<td>{_fmt(_mean([r.get('seconds') for r in rs]))}</td><td>{len(rs) - len(good)}</td></tr>")
    if len(labels) > 1:
        rows.append(f"<tr><td><b>both together</b></td><td></td><td></td><td></td><td></td><td>{_fmt(_mean([e['audit_union']['score'] for e in allx if e.get('audit_union')]))}</td><td></td><td></td></tr>")
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
    if len(labels) > 1:
        pairs = _pairs(data)
        fl = "".join(f"<tr><td>{html.escape(v['label'])}</td>" + "".join(
            f"<td>{verdicts.decided(pairs[v['name']])['failed_by'].get(l, (0, 0))[1]} of {verdicts.decided(pairs[v['name']])['failed_by'].get(l, (0, 0))[0]}</td>" for l in labels) + "</tr>" for v in data["variants"])
        cross += ("<h3>Failed reviews, by method and reviewer</h3><table class=sum><tr><th>Method</th>" + "".join(f"<th>{html.escape(l)}</th>" for l in labels) + f"</tr>{fl}</table>")
    return f"<h3>Reviewers compared</h3><table class=sum>{head}{''.join(rows)}</table>{agree}{cross}"


_headline = verdicts.reviewed_score


def refine_pairs(data: dict) -> str:
    """For a method that rewrites its own draft (refine): the draft against its result, same story, same reviewers, by level. A draft the loop left alone is the
    result, so it counts as equal. This replaces the comparison with another method's story, which is a different sample and mostly measures chance."""
    by_id = {r["id"]: r for r in data["requests"]}
    out = []
    for v in data["variants"]:
        pairs = [(by_id[rid], row[v["name"]]) for rid, row in data["results"].items() if rid in by_id and v["name"] in row and row[v["name"]].get("ok") and row[v["name"]].get("draft")]
        reviewed = [(r, e) for r, e in pairs if (e["draft"].get("audits") or not e["draft"].get("changed")) and e.get("audits")]
        if not reviewed:
            continue
        tiers = list(dict.fromkeys(r["tier"] for r, _ in reviewed))
        for label, group in [("all", reviewed)] + [(t, [(r, e) for r, e in reviewed if r["tier"] == t]) for t in tiers if len(tiers) > 1]:
            before = [dict(ok=True, **e["draft"]) if e["draft"].get("changed") else e for _, e in group]
            after = [e for _, e in group]
            b, a = review_counts(before), review_counts(after)
            out.append(f"<tr><td>{html.escape(v['label'])}</td><td>{html.escape(label)}</td><td>{len(group)}</td><td>{sum(1 for _, e in group if e['draft'].get('changed'))}</td>"
                       f"<td>{b['failed_reviews']} of {b['reviews']}</td><td>{a['failed_reviews']} of {a['reviews']}</td><td>{_fmt(b['naturalness'])}</td><td>{_fmt(a['naturalness'])}</td>"
                       f"<td>{_fmt(_mean([_headline(x) for x in before]))}</td><td>{_fmt(_mean([_headline(x) for x in after]))}</td></tr>")
    if not out:
        return ""
    head = ("<tr><th>Method</th><th>Level</th><th>Stories</th><th>Changed</th><th>Failed reviews, draft</th><th>Failed reviews, result</th><th>Naturalness, draft</th>"
            "<th>Naturalness, result</th><th>Score with review, draft</th><th>Score with review, result</th></tr>")
    return ("<h3>The draft against its own repair</h3><p class=num>The same story reviewed before and after the loop touched it (a draft left unchanged counts as equal). "
            f"This is the fair test of a repair step.</p><table class=sum>{head}{''.join(out)}</table>")


def _completeness(data: dict) -> str:
    """First thing on the page: finished or not, why it stopped, what is missing, and whether every reviewer answered. A partial file must not look like a whole one."""
    c = health.completeness(data)
    state = health.state(data)
    colour = "#1a7f37" if c["complete"] else "#b42318"
    per = ", ".join(f"{html.escape(p['label'])} {p['done']}/{p['total']}" for p in c["variants"])
    out = [f"<div style='border:2px solid {colour};padding:.6rem 1rem;margin:1rem 0'><b style='color:{colour}'>{html.escape(state)}</b>: {c['done']} of {c['total']} stories made ({per}).<br>"]
    if c["stopped"]:
        out.append(f"<b>Why it stopped:</b> {html.escape(str(c['stopped']))}<br>")
    if c["next"]:
        out.append(f"Next to make: {html.escape(c['next'][0])} with {html.escape(c['next'][1])}. Run the same command again with --resume and this file's .json.<br>")
    bad = [f"{p['label']}: {', '.join(p['failed'])}" for p in c["variants"] if p["failed"]]
    if bad:
        out.append(f"Stories that could not be written: {html.escape('; '.join(bad))}<br>")
    for label, slot in c["reviews"].items():
        why = ("; " + "; ".join(f"{k} ×{n}" for k, n in slot["why"].items())) if slot["why"] else ""
        short = slot["audit_ok"] < slot["asked"] or slot["rating_ok"] < slot["asked"]
        out.append(f"Reviewer <b>{html.escape(label)}</b>: {slot['audit_ok']} of {slot['asked']} reviews and {slot['rating_ok']} ratings worked"
                   + (f" <b style='color:#b42318'>(some are missing{html.escape(why)})</b>" if short else "") + "<br>")
    for p in (data.get("meta") or {}).get("preflight") or []:
        if not p.get("ok"):
            out.append(f"<b style='color:#b42318'>Preflight problem:</b> {html.escape(str(p['channel']))}: {html.escape(str(p['why']))}<br>")
    out.append("</div>")
    return "".join(out)


def _run_record(data: dict) -> str:
    meta = data.get("meta") or {}
    run, log = meta.get("run") or {}, meta.get("log") or []
    if not run and not log:
        return ""
    facts = "".join(f"<li>{html.escape(k)}: {html.escape(str(run.get(k)))}</li>" for k in ("started", "last_save", "command", "commit", "python", "platform", "kaggle") if run.get(k))
    settings = ", ".join(f"{k}={v}" for k, v in (run.get("settings") or {}).items())
    earlier = "".join(f"<li>{html.escape(str(e.get('started')))} to {html.escape(str(e.get('last_save')))}: {html.escape(str(e.get('stopped') or 'no reason recorded'))}</li>" for e in run.get("earlier") or [])
    return ("<h3>This run</h3><ul class=num>" + facts + (f"<li>settings: {html.escape(settings)}</li>" if settings else "") + "</ul>"
            + (f"<p class=num>Earlier runs of this file:</p><ul class=num>{earlier}</ul>" if earlier else "")
            + (f"<details><summary>Run log (last {len(log)} lines)</summary><pre>{html.escape(chr(10).join(log))}</pre></details>" if log else ""))


def _signed(v) -> str:
    return "–" if v is None else f"{v:+.1f}"


def _points(v) -> str:
    """A change in the share of stories passed (a verdict is 1, a split 0.5, a fail 0), as percentage points: +0.25 is +25."""
    return "–" if v is None else f"{v * 100:+.0f}"


def _own_reviewers(data: dict, pairs: dict, labels: list) -> list:
    """The reviewers that run on the model that wrote the stories: they may rate their own kind of writing higher."""
    meta = data.get("meta") or {}
    default = meta.get("story model")                 # a story written by the default model is recorded as "default": that is the run's story model
    writers = {default if w in (None, "default") else w for ps in pairs.values() for _, e in ps for w in [(e.get("models") or {}).get("story")]}
    return [l for l in labels if meta.get(f"{l} model") and meta.get(f"{l} model") in writers]


def _pairs(data: dict) -> dict:
    return {v["name"]: list(entries(data, v["name"])) for v in data["variants"]}


def _labels(data: dict) -> list:
    return list(dict.fromkeys(l for row in data["results"].values() for e in row.values() for l in (e.get("audits") or {})))


def _decided_table(data: dict, pairs: dict, labels: list) -> str:
    head = ("<tr><th>Method</th><th>What it adds</th><th>Stories reviewed</th><th>Passed by every reviewer (95% range)</th><th>Split</th><th>Failed by every reviewer</th>"
            "<th>Failed reviews</th>" + "".join(f"<th>Rating by {html.escape(l)} (1-5)</th>" for l in labels) + "<th>Score with review</th><th>Mistakes listed per story</th>"
            "<th>Learner words used</th><th>Words per story</th><th>Model calls per story</th><th>Seconds in model per story</th></tr>")
    rows = []
    for v in data["variants"]:
        d, s = verdicts.decided(pairs[v["name"]]), stats(data, v["name"])
        rows.append(f"<tr><td><b>{html.escape(v['label'])}</b></td><td>{html.escape(v['note'])}</td><td>{d['stories']}/{s['requests']}</td>"
                    f"<td>{st.percent_range(d[verdicts.PASS], d['stories'])}</td><td>{d[verdicts.SPLIT]}</td><td>{d[verdicts.FAIL]}</td>"
                    f"<td>{d['failed_reviews']} of {d['reviews']}</td>" + "".join(f"<td>{_fmt(None if d['rating'].get(l) is None else round(d['rating'][l], 1))}</td>" for l in labels)
                    + f"<td>{_fmt(s['reviewed_score'])}</td><td>{_fmt(s['mistakes_found'])}</td><td>{_fmt(s['own_words'])}</td><td>{_fmt(s['words'])}</td><td>{_fmt(s['calls'])}</td><td>{_fmt(s['model_seconds'])}</td></tr>")
    return (f"<h3>What the reviewers decided</h3><table class=sum>{head}{''.join(rows)}</table>"
            "<p class=num>A reviewer fails a story when it rates it 2 of 5 or lower, finds too many mistakes or finds it stuffed. A failed review multiplies the score by 0.6, "
            "so “Score with review” mostly follows the failed count: read the left side of this table first. A method that passes more stories by using fewer of your learner words "
            "has traded one for the other: read “Learner words used” beside the verdicts.</p>")


def _notes(data: dict, pairs: dict, labels: list) -> str:
    flat = [(r, name, e) for name, ps in pairs.items() for r, e in ps]
    out = []
    high = [verdicts.verdict(e)["kind"] for _, _, e in flat if verdicts.verdict(e) and (verdicts.free_score(e) or 0) >= 90]
    if high:
        out.append(f"{len(high)} of the {sum(1 for _, _, e in flat if verdicts.verdict(e))} reviewed stories scored 90 or more on the free checks; the reviewers passed {high.count(verdicts.PASS)} of "
                   f"those, split on {high.count(verdicts.SPLIT)} and failed {high.count(verdicts.FAIL)}. A high free score does not mean the story reads well: it checks the brief, not the writing.")
    counts = verdicts.rating_counts(flat)
    if counts:
        out.append("Ratings given: " + ", ".join(f"{k:g} × {n}" for k, n in counts.items()) + ". A rating of 2 or less fails the story, so one point between two reviews of the same text can flip the verdict.")
    moves = verdicts.what_moves(flat)
    if moves:
        out.append("Share of the variation in ratings that each explains (adjusted for how many groups it has): " + ", ".join(f"{k} {v * 100:.0f}%" for k, v in sorted(moves.items(), key=lambda kv: -kv[1]))
                   + ". What is left is the reviewers' own noise and the story itself.")
    same, both = verdicts.agreement(flat)
    if both:
        out.append(f"Two reviewers judged the same way (pass or fail) on {same} of {both} stories.")
    own = _own_reviewers(data, pairs, labels)
    if own and len(labels) > 1:
        out.append(f"{', '.join(own)} reviews stories its own model wrote. A model may rate its own kind of writing higher, so trust a gain only when the other reviewer shows it too.")
    out += _noise_notes(data, pairs)
    most = max((len(ps) for ps in pairs.values()), default=0)
    if most and most < 30:
        out.append(f"Each method has {most} request(s). The ranges show what that many can tell; a gap inside its range is not a difference.")
    return "<h3>How far to trust this</h3><ul class=num>" + "".join(f"<li>{html.escape(x)}</li>" for x in out) + "</ul>" if out else ""


def _noise_notes(data: dict, pairs: dict) -> list:
    """What running the same method twice moved, read from a method that repeats another (`replicate_of`). Without one the file cannot say how much a single run varies."""
    variants = data.get("variants") or []
    by_name = {v["name"]: v for v in variants}
    out, found = [], False
    for v in variants:
        first = by_name.get(v.get("replicate_of") or "")
        if first is None or first["name"] not in pairs or v["name"] not in pairs:
            continue
        found = True
        c = verdicts.paired_verdicts(pairs[first["name"]], pairs[v["name"]])
        if not c["requests"]:
            continue
        need = f"; to see a gain of {c['wanted'] * 100:.0f} points at this spread it takes about {c['needed']} requests" if c["needed"] else ""
        out.append(f"{v['label']} is {first['label']} made again for the same {c['requests']} requests. The passed stories moved by {_points(c['change'])} points "
                   f"({_points(c['low'])} to {_points(c['high'])}), {c['up']} better, {c['same']} the same, {c['down']} worse. That is the noise of one run: a gap between two methods "
                   f"inside this range is not a difference{need}.")
    if not found and len(variants) > 1:
        out.append("No method is made twice in this file, so how much one run varies is not measured here. Add the baseline again (--variants baseline,baseline_b) to measure it in the same run.")
    return out


def _passed_table(data: dict, pairs: dict) -> str:
    """Each method against the first on what the reviewers decided (verdict_pairs): the comparison the app cares about, with each reviewer alone and the requests it would take."""
    names = [v["name"] for v in data["variants"]]
    if len(names) < 2:
        return ""
    rows = []
    for v in data["variants"][1:]:
        c = verdicts.paired_verdicts(pairs[names[0]], pairs[v["name"]])
        if not c["requests"]:
            continue
        rng = "" if c["low"] is None else f" ({_points(c['low'])} to {_points(c['high'])})"
        own = " · ".join(f"{html.escape(l)} {_points(x)}" for l, x in c["by_reviewer"].items())
        tag = " <i>(the same method again: this is noise)</i>" if v.get("replicate_of") == names[0] else ""
        need = f"about {c['needed']}" if c["needed"] else "–"
        rows.append(f"<tr><td><b>{html.escape(v['label'])}</b>{tag}</td><td>{c['requests']}</td><td>{_points(c['change'])}{rng}</td><td>{c['up']} / {c['same']} / {c['down']}</td>"
                    f"<td>{c['p']:.3f}</td><td>{own}</td><td><b>{html.escape(c['reading'])}</b></td><td>{need}</td></tr>")
    if not rows:
        return ""
    head = ("<tr><th>Method</th><th>Requests compared</th><th>Change in stories passed, points (95% range)</th><th>Better / same / worse</th><th>Sign test p</th>"
            f"<th>Each reviewer alone, points</th><th>Reading</th><th>Requests to see {verdicts.WANTED_GAP * 100:.0f} points</th></tr>")
    return (f"<h3>Passed stories: each method against {html.escape(data['variants'][0]['label'])}, request by request</h3><table class=sum>{head}{''.join(rows)}</table>"
            "<p class=num>The same request with both methods. A story every reviewer passes counts 1, a split 0.5 and a failed story 0; the change is that average in points "
            "(+25 means one story in four moved from fail to pass). “Each reviewer alone” is the change in the share of stories that reviewer passed: a gain only one of them "
            "sees is not counted as clear. The last column is how many requests it would take to see a gain of "
            f"{verdicts.WANTED_GAP * 100:.0f} points at the spread of these changes.</p>")


def _fit_table(data: dict, pairs: dict) -> str:
    """Does each method write the sentence length its level asks for? From the free measurement; no model."""
    got = [(v, fit.by_method(pairs[v["name"]])) for v in data["variants"]]
    got = [(v, b) for v, b in got if b]
    if not got:
        return ""
    tiers = [t for t in fit.SENTENCE_RANGE if any(t in b["tiers"] for _, b in got)]
    head = ("<tr><th>Method</th><th>Stories</th><th>Mean sentence in the asked range (95% range)</th><th>Too short</th><th>Too long</th>"
            + "".join(f"<th>{html.escape(t.capitalize())} ({fit.asked(t)} words)</th>" for t in tiers) + "</tr>")
    rows = []
    for v, b in got:
        cells = "".join(f"<td>{b['tiers'][t][fit.IN]} of {sum(b['tiers'][t].values())}</td>" if t in b["tiers"] else "<td>–</td>" for t in tiers)
        rows.append(f"<tr><td><b>{html.escape(v['label'])}</b></td><td>{b['stories']}</td><td>{st.percent_range(b[fit.IN], b['stories'])}</td><td>{b[fit.SHORT]}</td><td>{b[fit.LONG]}</td>{cells}</tr>")
    on = any(v.get("range_prompt") for v in data["variants"])
    note = ("A method that is not told the range (the baseline: STORY_RANGE_PROMPT is off in the app) writes one sentence length at every level, so it misses on both sides. "
            if on else "")
    return ("<h3>Does the story fit its level?</h3><table class=sum>" + head + "".join(rows) + "</table>"
            f"<p class=num>The mean sentence of each story against the range the level note asks the writer for. {note}Chinese and Japanese are left out (their sentences are counted in characters). "
            "The free score has one ruler for every level, so it cannot show this.</p>")


def _reviewer_table(data: dict, pairs: dict, labels: list) -> str:
    """How many stories each reviewer passed on its own, per method. Two reviewers from two model families are two independent opinions; one of them may be the writer's own model."""
    if len(labels) < 2:
        return ""
    own = _own_reviewers(data, pairs, labels)
    head = "<tr><th>Method</th>" + "".join(f"<th>Passed by {html.escape(l)}{' (also the writer)' if l in own else ''}</th>" for l in labels) + "</tr>"
    rows = []
    for v in data["variants"]:
        d = verdicts.decided(pairs[v["name"]])
        cells = []
        for l in labels:
            reviews, bad = d["failed_by"].get(l, (0, 0))
            cells.append(f"<td>{st.percent_range(reviews - bad, reviews)}</td>")
        rows.append(f"<tr><td><b>{html.escape(v['label'])}</b></td>{''.join(cells)}</tr>")
    return ("<h3>Each reviewer on its own</h3><table class=sum>" + head + "".join(rows) + "</table>"
            "<p class=num>The share of stories each reviewer passed. A reviewer from another model family than the writer cannot favour the writer, so a gain it sees is the one to trust; "
            "a gain only the writer's own model sees may be its taste for its own kind of writing.</p>")


def _paired_table(data: dict, pairs: dict) -> str:
    names = [v["name"] for v in data["variants"]]
    if len(names) < 2:
        return ""
    rows = []
    for v in data["variants"][1:]:
        c = verdicts.paired(pairs[names[0]], pairs[v["name"]])
        if not c["requests"]:
            continue
        rng = "–" if c["low"] is None else f" ({_signed(c['low'])} to {_signed(c['high'])})"
        own = " · ".join(f"{html.escape(l)} {_signed(x)}" for l, x in c["by_reviewer"].items())
        rows.append(f"<tr><td><b>{html.escape(v['label'])}</b></td><td>{c['requests']}</td><td>{_signed(c['change'])}{rng}</td><td>{c['up']} / {c['same']} / {c['down']}</td>"
                    f"<td>{c['p']:.2f}</td><td>{own}</td><td><b>{html.escape(c['reading'])}</b></td></tr>")
    if not rows:
        return ""
    head = ("<tr><th>Method</th><th>Requests compared</th><th>Mean rating change (95% range)</th><th>Better / same / worse</th><th>Sign test p</th>"
            "<th>Change by reviewer</th><th>Reading</th></tr>")
    return (f"<h3>Each method against {html.escape(data['variants'][0]['label'])}, request by request</h3><table class=sum>{head}{''.join(rows)}</table>"
            "<p class=num>The same comparison on the 1 to 5 ratings. A rating moves by a fraction of a point and sees less than the passed or failed line the app works with, so read the table "
            "of passed stories above first. A clear change needs the range to leave zero, the sign test to agree "
            f"and no reviewer to go the other way; with fewer than {st.MIN_PAIRS} requests nothing can be clear.</p>")


def _group_tables(data: dict, pairs: dict) -> str:
    out = []
    for key, title in (("pack", "word pack"), ("tier", "level"), ("story_type", "story type")):
        grid = verdicts.by_group(pairs, key)
        if not grid:
            continue
        names = [v for v in data["variants"]]
        rows = []
        for g, row in grid.items():
            k = sum(x[0] for x in row.values())
            n = sum(x[1] for x in row.values())
            rows.append(f"<tr><td><b>{html.escape(str(g))}</b></td>" + "".join(f"<td>{row[v['name']][0]} of {row[v['name']][1]}</td>" if v["name"] in row else "<td>–</td>" for v in names)
                        + f"<td>{k} of {n} ({k * 100 // n if n else 0}%)</td></tr>")
        out.append(f"<h3>Failed reviews by {title}</h3><table class=sum><tr><th>{title.capitalize()}</th>" + "".join(f"<th>{html.escape(v['label'])}</th>" for v in names) + f"<th>All methods</th></tr>{''.join(rows)}</table>")
    return "".join(out)


def _request_grid(data: dict, pairs: dict, labels: list) -> str:
    mark = {verdicts.PASS: "✓", verdicts.SPLIT: "~", verdicts.FAIL: "✗"}
    word = {verdicts.PASS: "passed", verdicts.SPLIT: "split", verdicts.FAIL: "failed"}
    rows = []
    for r in data["requests"]:
        row = data["results"].get(r["id"]) or {}
        cells = []
        for v in data["variants"]:
            e = row.get(v["name"])
            vd = verdicts.verdict(e)
            if vd is None:
                cells.append("<td>–</td>")
                continue
            got = verdicts.ratings(e)
            cells.append(f"<td class='v-{vd['kind']}' title='{word[vd['kind']]}'>{mark[vd['kind']]} " + " · ".join(f"{got[l]:g}" if l in got else "?" for l in labels) + "</td>")
        if any("v-" in c for c in cells):
            rows.append(f"<tr><td>{html.escape(r['id'])}</td><td>{html.escape(str(r.get('tier', '')))}</td><td>{html.escape(str(r.get('pack', '')))}</td>" + "".join(cells) + "</tr>")
    if not rows:
        return ""
    return (f"<h3>Ratings by request</h3><p class=num>Ratings in the order {html.escape(' · '.join(labels))}; ✓ passed, ~ split, ✗ failed. A request that fails in every column is the request's doing, not the method's.</p>"
            "<table class='sum grid'><tr><th>Request</th><th>Level</th><th>Word pack</th>" + "".join(f"<th>{html.escape(v['label'])}</th>" for v in data["variants"]) + f"</tr>{''.join(rows)}</table>")


def _free_table(data: dict, reviewed: bool) -> str:
    variants = data["variants"]
    base = stats(data, variants[0]["name"]) if variants else {}
    head = ("<tr><th>Method</th><th>Stories</th><th>Free score</th><th>vs first</th><th>Pass rate (free checks)</th>" + "".join(f"<th>{l}</th>" for l in PART_LABELS.values())
            + "<th>Calls</th><th>Seconds in model</th><th>Seconds in all</th></tr>")
    rows = []
    for v in variants:
        s = stats(data, v["name"])
        delta = None if s["score"] is None or base.get("score") is None else round(s["score"] - base["score"], 1)
        rows.append(f"<tr><td><b>{html.escape(v['label'])}</b></td><td>{s['stories']}/{s['requests']}</td><td>{_fmt(s['score'])}</td><td>{'–' if delta is None else f'{delta:+g}'}</td>"
                    f"<td>{_fmt(s['pass_rate'], True)}</td>" + "".join(f"<td>{_fmt(s['parts'][k])}</td>" for k in PART_LABELS)
                    + f"<td>{_fmt(s['calls'])}</td><td>{_fmt(s['model_seconds'])}</td><td>{_fmt(s['seconds'])}</td></tr>")
    meta = data.get("meta") or {}
    return ("<h3>Brief fit and cost (free checks)</h3>" + ("<p class=num>These need no model: words used, length, level, sentence length and the built-in grammar rules. They say nothing about whether a story reads well.</p>" if reviewed else "")
            + f"<table class=sum>{head}{''.join(rows)}</table><p class=num>Score version {meta.get('score_version', '?')}; a story passes the free checks when it is not gated and every part is at least {PASS_PART:g}. "
            "“Seconds in model” is time inside model calls; “seconds in all” also counts waiting for the free tier’s rate limit.</p>")


def _language_table(data: dict, reviewed: bool) -> str:
    variants = data["variants"]
    codes = list(dict.fromkeys(r["code"] for r in data["requests"]))

    def cell(v, c):
        s = stats(data, v["name"], c)
        if reviewed and s["reviewed_score"] is not None:
            return f"{_fmt(s['reviewed_score'])} ({s['failed_reviews']} of {s['reviews']} reviews failed)"
        return _fmt(s["score"]) + (" (free checks)" if reviewed else "")
    head = "<tr><th>Language</th>" + "".join(f"<th>{html.escape(v['label'])}</th>" for v in variants) + "</tr>"
    rows = "".join(f"<tr><td>{html.escape(LANGUAGES[c].name)}</td>" + "".join(f"<td>{cell(v, c)}</td>" for v in variants) + "</tr>" for c in codes)
    return f"<h3>Mean score by language{' (with model review)' if reviewed else ' (free checks only)'}</h3><table class=sum>{head}{rows}</table>"


def _summary(data: dict) -> str:
    pairs, labels = _pairs(data), _labels(data)
    reviewed = any(verdicts.verdict(e) for ps in pairs.values() for _, e in ps)
    meta = data.get("meta") or {}
    models = ", ".join(f"{k}: {v}" for k, v in meta.items() if v and k != "stopped" and isinstance(v, (str, int, float)))
    out = ["<h2>Summary</h2>", _completeness(data)]
    if models:
        out.append(f"<p class=num>{html.escape(models)}</p>")
    if reviewed:
        out += [_decided_table(data, pairs, labels), _notes(data, pairs, labels), _passed_table(data, pairs), _paired_table(data, pairs), _fit_table(data, pairs),
                _reviewer_table(data, pairs, labels), _group_tables(data, pairs), _request_grid(data, pairs, labels)]
    else:
        out.append("<div class=warnbox><b style='color:#b42318'>No model review in this file.</b> The score below only checks the brief (the words, the length, the level and the rules "
                   "that need no model). It cannot see unnatural writing, events that do not follow or most grammar mistakes, so it is not a measure of quality. "
                   "Run with <code>--audit-models gpt,qwen</code> to have the stories reviewed.</div>")
    out += [refine_pairs(data), reviewer_table(data), _free_table(data, reviewed), _language_table(data, reviewed), _run_record(data)]
    return "".join(out)


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
            use_review = any(verdicts.reviewed_score(e) is not None for e in row.values())

            def key(e):
                return (verdicts.reviewed_score(e) if use_review else (e.get("score") or {}).get("score")) or -1
            top = max((key(e) for e in row.values()), default=-1)
            cards = "".join(_card(v, row[v["name"]], key(row[v["name"]]) == top and top > 0) for v in variants if v["name"] in row)
            body.append(f"<h3>{html.escape(r['id'])}: {r['tier']} · {r['story_type']} · {html.escape(r['topic'])}</h3>"
                        f"<p class=num>Words: {html.escape(', '.join(r['words']))}</p><div class=row>{cards}</div>")
        tabs.append((code, LANGUAGES[code].name))
        panels.append((code, "".join(body)))
    nav = "".join(f"<button role=tab aria-selected={'true' if i == 0 else 'false'} data-tab='{html.escape(c)}'>{html.escape(t)}</button>" for i, (c, t) in enumerate(tabs))
    sections = "".join(f"<section class=panel id='p-{html.escape(c)}'>{b}</section>" for c, b in panels)
    return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Story methods compared</title>"
            f"<style>{CSS}</style><h1>Story methods compared</h1><p>The same requests (words, level, kind, topic) made with each method. Model reviewers, not the free checks, decide whether a story reads well. "
            f"A column is one method; each adds one thing to the one before it.</p><nav role=tablist>{nav}</nav>{sections}{JS}")
