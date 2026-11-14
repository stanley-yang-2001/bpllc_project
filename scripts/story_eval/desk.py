"""The data behind the Story Test Desk page (11 Nov 2026): reads what a story test leaves on disk and turns it into one JSON-able dict.

Reads, without changing anything:
  test-reports/overnight-<stamp>/SUMMARY.txt and 01-story-test.log   (what run-overnight.bat writes; the log is live while the test runs)
  the results JSON of a run: scripts/overnight_<stamp>.json or a copy in the report folder (the runner saves it after every story)
  key_status.json from scripts/key_status.py, when it exists
A run is "running" while its SUMMARY has no Finished line and its log was written within the last RUNNING_SECONDS."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

RUNNING_SECONDS = 15 * 60
ENTRY = re.compile(r"^\[(\d+)/(\d+)\] (\S+) (\S+)\s+(\S+)\s+score ([\d.]+)\s+calls (\d+)\s+([\d.]+)s \(model ([\d.]+)s\)")
KEY_FAMILIES = {"GROQ_API_KEY": "story writer and gpt reviewer", "GROQ_QWEN_API_KEY": "qwen reviewer",
                "GROQ_JUDGE_API_KEY": "judge (picks and rates candidates)", "GROQ_AUDIT_API_KEY": "grammar and naturalness review"}


def _seconds(text: str):
    m = re.search(r"(\d+):(\d+):(\d+)", text or "")
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) if m else None


def parse_summary(lines, step: int = 1) -> dict:
    """`step` is the story test to read (1 the cascade test, 2 the refine test of run-overnight.bat 2.3)."""
    out = {"start": None, "storyStart": None, "storyEnd": None, "exit": None, "checksEnd": None, "finished": None, "dockerFailed": False}
    for line in lines:
        if line.startswith("Overnight run started"):
            out["start"] = _seconds(line)
        elif re.match(rf"Step {step}.*started", line):
            out["storyStart"] = _seconds(line)
        elif re.match(rf"Step {step}.*exit code", line):
            m = re.search(r"exit code\s*(\d*)\s*(?:\(.*?\))?\s*at\s+(\S+)", line)
            if m:
                out["exit"] = int(m[1]) if m[1] else None
                out["storyEnd"] = _seconds(m[2])
        elif re.match(r"Step \d run-checks", line):
            out["checksEnd"] = _seconds(line.split(" at ")[-1])
        elif line.startswith("Finished"):
            out["finished"] = _seconds(line)
        elif line.startswith("Docker did not start"):
            out["dockerFailed"] = True
    return out


def parse_log(lines) -> dict:
    """Entries so far, the pacing and rate-limit lines, and what the run says it will do (`total` results)."""
    out = {"entries": [], "pacing": {"count": 0, "seconds": 0}, "limits": [], "waits": [], "keys": None, "total": None, "last": ""}
    pending = []
    for line in lines:
        if line.strip():
            out["last"] = line.strip()[:200]
        m = re.match(r"(\d+) requests x (\d+) methods", line)
        if m:
            out["total"] = int(m[1]) * int(m[2])
            continue
        m = ENTRY.match(line)
        if m:
            e = {"i": int(m[1]), "of": int(m[2]), "id": m[3], "tier": m[4], "variant": m[5], "offline": float(m[6]), "calls": int(m[7]), "seconds": float(m[8]), "model": float(m[9])}
            out["entries"].append(e)
            for ev in pending:
                ev["before"] = f"{e['id']} {e['variant']}"
            pending = []
            continue
        m = re.match(r"\s+pacing: waiting (\d+)s", line)
        if m:
            out["pacing"]["count"] += 1
            out["pacing"]["seconds"] += int(m[1])
            continue
        m = re.match(r"\s+(\S+) is rate limited(?: \(try again in (\d+)s\))?(?: \[(\w+)\])?", line)
        if m:
            ev = {"key": m[1], "hint": int(m[2]) if m[2] else None, "kind": m[3], "to": None, "before": None}
            out["limits"].append(ev)
            pending.append(ev)
            continue
        m = re.match(r"\s+switching key (\S+) -> (\S+)", line)
        if m and out["limits"]:
            out["limits"][-1]["to"] = m[2]
            continue
        m = re.match(r"\s+rate limited: waiting (\d+)s \(try (\d+)/(\d+)\)", line)
        if m:
            ev = {"wait": int(m[1]), "try": int(m[2]), "of": int(m[3]), "before": None}
            out["waits"].append(ev)
            pending.append(ev)
            continue
        m = re.match(r"Keys per family.*?: (.*?)(?:;|$)", line)
        if m:
            out["keys"] = {k: int(n) for k, n in re.findall(r"(\w+) x(\d+)", m[1])}
    return out


def _read(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").replace("\r", "").splitlines()
    except OSError:
        return []


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def trace_lines(trace) -> list[str]:
    """The refine loop (story_refine.py) as one plain line per phase, for the page. The full records stay in the run JSON and the HTML report."""
    out = []
    for t in trace or []:
        ph = t.get("phase")
        if ph == "observe":
            seen = ", ".join(f"{x['tool']} {x['found']}" for x in t.get("tools", []))
            rated = t.get("naturalness") or {}
            out.append(f"Observe ({t.get('label')}): score {t['score']['score']:g}; findings: {seen}" + (f"; naturalness {rated['score']:g}/5" if rated.get("ok") else "")
                       + (f"; free checks failed: {', '.join(t['gates'])}" if t.get("gates") else ""))
        elif ph == "code fix":
            out.append(f"Code fix: {len(t.get('changes', []))} certain mistake(s), no model call")
        elif ph == "plan":
            out.append(f"Plan, round {t['round']}: {len(t.get('flagged', []))} sentence(s) flagged, {len(t.get('whole_text', []))} whole-text need(s)" + (" (measured, left alone)" if t.get("whole_text_repaired") is False else ""))
        elif ph == "repair":
            out.append(f"Repair, round {t['round']}: " + (t["error"] if t.get("error") else f"one model call, {len(t.get('reply') or '')} characters back"))
        elif ph == "verify":
            verdict = "kept" if t.get("kept") else "thrown away"
            nums = f", score {t['before']:g} to {t['after']:g}" if "after" in t else ""
            if t.get("naturalness_before") is not None and t.get("naturalness_after") is not None:
                nums += f", naturalness {t['naturalness_before']:g} to {t['naturalness_after']:g}"
            out.append(f"Verify, round {t['round']}: {verdict}" + (f" ({t['reason']})" if t.get("reason") else "") + nums)
    return out


def results_of(path: Path) -> Optional[dict]:
    """Stories, methods and one cell per story and method, from a saved run JSON (partial runs too)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    labels = {v["name"]: v for v in data.get("variants", [])}
    stories = [{"id": r["id"], "lang": r["code"], "tier": r.get("tier"), "kind": r.get("story_type"), "topic": r.get("topic"), "words": len(r.get("words", []))} for r in data.get("requests", [])]
    cells = []
    for rid, row in (data.get("results") or {}).items():
        for name, e in row.items():
            score = e.get("score") or {}
            reviews = e.get("audit_scores") or {}
            nat = {k: (s.get("parts") or {}).get("naturalness") for k, s in reviews.items()}
            judged = [int(x) for x in re.findall(r"naturalness (\d)/5", " ".join(e.get("notes") or []))]
            cells.append({"story": rid, "variant": name, "offline": score.get("score"), "reviewed": (e.get("audit_union") or {}).get("score"),
                          "gpt": (reviews.get("gpt") or {}).get("score"), "qwen": (reviews.get("qwen") or {}).get("score"),
                          "natGpt": nat.get("gpt"), "natQwen": nat.get("qwen"),
                          "hitsGpt": len(((e.get("audits") or {}).get("gpt") or {}).get("hits", [])) if "gpt" in reviews else None,
                          "hitsQwen": len(((e.get("audits") or {}).get("qwen") or {}).get("hits", [])) if "qwen" in reviews else None,
                          "judgeNat": judged, "trace": trace_lines(e.get("trace")), "repair": next((n for n in (e.get("notes") or []) if n.startswith("repair")), None),
                          "calls": e.get("calls"), "seconds": e.get("seconds"), "model": e.get("model_seconds"), "wait": e.get("wait_seconds"),
                          "offlineNat": (score.get("parts") or {}).get("naturalness")})
    by_variant = []
    for name, v in labels.items():
        cs = [c for c in cells if c["variant"] == name]
        by_variant.append({"variant": name, "label": v.get("label", name), "offline": _mean([c["offline"] for c in cs]), "reviewed": _mean([c["reviewed"] for c in cs]),
                           "gpt": _mean([c["gpt"] for c in cs]), "qwen": _mean([c["qwen"] for c in cs]), "natGpt": _mean([c["natGpt"] for c in cs]),
                           "natQwen": _mean([c["natQwen"] for c in cs]), "calls": _mean([c["calls"] for c in cs]), "seconds": _mean([c["seconds"] for c in cs]), "n": len(cs)})
    return {"stories": stories, "variants": [{"name": n, "label": v.get("label", n), "note": v.get("note", "")} for n, v in labels.items()], "cells": cells,
            "byVariant": by_variant, "meta": {k: str(v)[:200] for k, v in (data.get("meta") or {}).items()}, "created": data.get("created")}


def run_of(folder: Path, scripts_dir: Path, now: float, step: int = 1, last: bool = True) -> dict:
    """One story test in an overnight folder. `last` is True for the test the checks step follows (the checks bar is drawn after it only)."""
    stamp = folder.name.split("-", 1)[1]
    name, prefix = ("01-story-test.log", "overnight_") if step == 1 else ("02-refine-test.log", "refine_")
    run = {"id": stamp if step == 1 else stamp + "-refine", "kind": "cascade" if step == 1 else "refine", "stamp": stamp,
           **parse_summary(_read(folder / "SUMMARY.txt"), step), **parse_log(_read(folder / name))}
    if not last:
        run["checksEnd"] = None
    log = folder / name
    run["updated"] = log.stat().st_mtime if log.exists() else None
    run["running"] = bool(run["finished"] is None and run["updated"] and now - run["updated"] < RUNNING_SECONDS and run["exit"] is None)
    run["ageSeconds"] = round(now - run["updated"]) if run["updated"] else None
    candidates = [scripts_dir / f"{prefix}{stamp}.json", folder / f"{prefix}{stamp}.json"]
    run["jsonPath"] = next((str(p) for p in candidates if p.exists()), None)
    run["json"] = run["jsonPath"] is not None
    return run


def key_evidence(runs) -> dict:
    out: dict = {}
    for r in runs:
        for ev in r["limits"]:
            k = out.setdefault(ev["key"], {"limited": 0, "runs": [], "hints": [], "kinds": [], "switchedTo": []})
            k["limited"] += 1
            k["runs"] = sorted(set(k["runs"]) | {r["id"]})
            k["hints"].append(ev["hint"])
            if ev.get("kind"):
                k["kinds"].append(ev["kind"])
            if ev["to"] and ev["to"] not in k["switchedTo"]:
                k["switchedTo"].append(ev["to"])
    return out


def collect(reports_dir: Path, scripts_dir: Path, run_id: Optional[str] = None, now: Optional[float] = None) -> dict:
    now = time.time() if now is None else now
    folders = sorted(p for p in reports_dir.glob("overnight-*") if p.is_dir()) if reports_dir.exists() else []
    runs = []
    for f in folders:
        refine = (f / "02-refine-test.log").exists()
        runs.append(run_of(f, scripts_dir, now, 1, last=not refine))
        if refine:
            runs.append(run_of(f, scripts_dir, now, 2))
    chosen = next((r for r in runs if r["id"] == run_id), None) or next((r for r in reversed(runs) if r["json"]), None)
    results = results_of(Path(chosen["jsonPath"])) if chosen else None
    status = None
    for place in (scripts_dir / "key_status.json", reports_dir / "key_status.json"):
        if place.exists():
            try:
                status = json.loads(place.read_text(encoding="utf-8"))
                break
            except (OSError, ValueError):
                pass
    families = {k: {"role": role, "keys": (next((r["keys"] for r in reversed(runs) if r["keys"]), {}) or {}).get(k, 1)} for k, role in KEY_FAMILIES.items()}
    meta = (results or {}).get("meta", {})
    for k, field in (("GROQ_API_KEY", "story model"), ("GROQ_QWEN_API_KEY", "qwen model"), ("GROQ_JUDGE_API_KEY", "judge model"), ("GROQ_AUDIT_API_KEY", "review model")):
        families[k]["model"] = meta.get(field, "")
    for r in runs:
        r.pop("jsonPath", None)
    return {"live": True, "now": now, "runs": runs, "results": results, "resultsRun": chosen["id"] if chosen else None, "keyEvidence": key_evidence(runs),
            "keyStatus": status, "families": families}
