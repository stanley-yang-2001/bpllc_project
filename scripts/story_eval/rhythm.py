"""How stiff a method's stories read, from the free checks (20 Nov 2026). No model call, so it is in every report, with or without reviewers.

tutor_core/story_diagnose.py counts, for each story, flat rhythm, a repeated opener and filler time words; this module sums them for one method. In the 19 Nov round the
mean findings of a story went with its rating (0 findings 3.42, 3 or more 2.82), so a method that lowers them is doing something to the stories the reviewers see.
It is a signal, not a verdict: the reviewers' pass rate stays the measure of quality, and a rise in sentence-length spread that comes with run-on sentences would show in the
reviewers' grammar findings, not here."""
from __future__ import annotations

import statistics as st
from typing import Iterable, Optional

from tutor_core import story_diagnose


def of_story(request: dict, entry: Optional[dict]) -> Optional[dict]:
    if not entry or not entry.get("ok") or not entry.get("text"):
        return None
    return story_diagnose.signal(entry["text"], request["code"], request.get("words") or (), request.get("story_type"))


def by_method(pairs: Iterable) -> Optional[dict]:
    """{"stories", "mean_findings", "two_or_more", "mean_sd", "flat", "mean_opener", "filler"} over the stories that can be judged, or None when none can."""
    got = [s for s in (of_story(r, e) for r, e in pairs) if s]
    if not got:
        return None
    return {"stories": len(got), "mean_findings": st.mean(s["findings"] for s in got), "two_or_more": sum(s["findings"] >= story_diagnose.REPAIR_AT for s in got),
            "mean_sd": st.mean(s["sd"] for s in got), "flat": sum("flat_rhythm" in s["codes"] for s in got), "mean_opener": st.mean(s["opener_share"] for s in got),
            "filler": sum("filler" in s["codes"] for s in got)}
