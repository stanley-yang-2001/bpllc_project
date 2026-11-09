"""Spaced repetition for the learner's own words (9 Nov 2026). Pure Python: no database, no clock of its own (the caller passes `now`).

It is the SM-2 family that Anki made familiar, with four answers instead of two:

    1 Again   I did not remember it
    2 Hard    I remembered it, with effort
    3 Good    I remembered it
    4 Easy    it was easy

A card is in one of three phases:
    learning     never remembered yet: it climbs short steps (1 minute, then 10 minutes) and graduates to 1 day on Good (4 days on Easy)
    review       it rests for `interval_days`, then comes back; Good multiplies the rest by the card's ease (2.5 to start), Hard by 1.2,
                 Easy by ease x 1.3; late reviews get credit for the extra time the word survived
    relearning   a review card that was forgotten (Again): it goes back to short steps (10 minutes), loses 0.20 ease, and returns to
                 review at half its old rest (at least a day)

Practising a card early (before it is due) and remembering it does NOT move its schedule, so repeating a round cannot inflate it; only a
miss (Again) always counts. Intervals of 3+ days get a small fixed spread (+-5%, `fuzz`) so words learnt together do not all return together.

`box_of` keeps the five boxes of the first version for the progress card: box 4 and up is "known" (a rest of 7+ days).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Optional

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
GRADES = (AGAIN, HARD, GOOD, EASY)
LEARNING, REVIEW, RELEARNING = "learning", "review", "relearning"
LEARN_STEPS = (60, 600)                  # seconds
RELEARN_STEPS = (600,)
GRADUATE_DAYS, EASY_DAYS = 1, 4
START_EASE, MIN_EASE, MAX_EASE = 2.5, 1.3, 3.5
EASE_AGAIN, EASE_HARD, EASE_EASY = -0.20, -0.15, +0.15
HARD_FACTOR, EASY_BONUS, LAPSE_FACTOR = 1.2, 1.3, 0.5
MAX_INTERVAL_DAYS = 365
HARD_STEP_FACTOR = 1.5
FUZZ_FROM_DAYS, FUZZ_SHARE = 3, 0.05
LEARN_AHEAD_SECONDS = 20 * 60            # a learning card due within 20 minutes is shown now (the session would otherwise stop and wait)
KNOWN_DAYS = 7                           # a rest of this many days or more is "known" (box 4 of the first version)
LEECH_LAPSES = 8
DAY = 86400


@dataclass(frozen=True)
class Card:
    phase: str = LEARNING
    step: int = 0
    ease: float = START_EASE
    interval_days: float = 0.0           # in review: the rest it was given; in relearning: the rest it returns to
    reps: int = 0
    lapses: int = 0
    due_at: Optional[datetime] = None    # None: never practised


@dataclass(frozen=True)
class Outcome:
    card: Card
    counted: bool                        # False: practised early and remembered, so nothing moved
    delay_seconds: float                 # from now until the card is due again
    was_due: bool
    correct: bool                        # grade 2 or more


def is_due(card: Card, now: datetime) -> bool:
    return card.due_at is None or card.due_at <= now


def fuzz_factor(seed: int) -> float:
    """A fixed spread in [0.95, 1.05] from a seed (the word id and its repetition count), the same every time so a preview matches the result."""
    x = (seed * 2654435761) % 4294967296 / 4294967296.0
    return 1.0 + (x * 2 - 1) * FUZZ_SHARE


def _days(value: float, fuzz: float) -> int:
    value = value * fuzz if value >= FUZZ_FROM_DAYS else value
    return int(min(MAX_INTERVAL_DAYS, max(1, round(value))))


def _clamp_ease(ease: float) -> float:
    return round(min(MAX_EASE, max(MIN_EASE, ease)), 2)


def _steps(phase: str) -> tuple:
    return RELEARN_STEPS if phase == RELEARNING else LEARN_STEPS


def review(card: Card, grade: int, now: datetime, fuzz: float = 1.0) -> Outcome:
    """What one answer does to a card. `fuzz` is fuzz_factor(...) (1.0 = none)."""
    if grade not in GRADES:
        raise ValueError("grade must be 1 to 4")
    due = is_due(card, now)
    correct = grade >= HARD
    reps = card.reps + 1
    if card.phase in (LEARNING, RELEARNING):
        steps = _steps(card.phase)
        if grade == AGAIN:
            step, delay = 0, steps[0]
            return _done(replace(card, step=step, reps=reps), now, delay, due, correct)
        if grade == HARD:
            delay = steps[min(card.step, len(steps) - 1)] * HARD_STEP_FACTOR
            return _done(replace(card, reps=reps), now, delay, due, correct)
        last = card.step + 1 >= len(steps)
        if grade == GOOD and not last:
            return _done(replace(card, step=card.step + 1, reps=reps), now, steps[card.step + 1], due, correct)
        # graduates: Good on the last step, or Easy on any
        if card.phase == RELEARNING:
            days = _days(max(1.0, card.interval_days) * (EASY_BONUS if grade == EASY else 1.0), fuzz)
            days = max(days, 2) if grade == EASY else days
        else:
            days = _days(EASY_DAYS if grade == EASY else GRADUATE_DAYS, 1.0)
        return _done(replace(card, phase=REVIEW, step=0, interval_days=float(days), reps=reps), now, days * DAY, due, correct)
    # review phase
    if grade == AGAIN:
        lapse_rest = float(max(1, round(card.interval_days * LAPSE_FACTOR)))
        after = replace(card, phase=RELEARNING, step=0, ease=_clamp_ease(card.ease + EASE_AGAIN), interval_days=lapse_rest,
                        reps=reps, lapses=card.lapses + 1)
        return _done(after, now, RELEARN_STEPS[0], due, correct)
    if not due:                                              # practised early and remembered: the schedule stays
        remaining = max(0.0, (card.due_at - now).total_seconds())
        return Outcome(replace(card, reps=reps), False, remaining, False, correct)
    late = max(0.0, (now - card.due_at).total_seconds() / DAY) if card.due_at else 0.0
    interval = max(1.0, card.interval_days)
    hard = _days(max(interval * HARD_FACTOR, interval + 1), fuzz) if interval < 2 else _days(interval * HARD_FACTOR, fuzz)
    good = max(_days((interval + late / 2) * card.ease, fuzz), hard + 1)
    easy = max(_days((interval + late) * card.ease * EASY_BONUS, fuzz), good + 1)
    days = {HARD: hard, GOOD: good, EASY: min(MAX_INTERVAL_DAYS, easy)}[grade]
    days = min(MAX_INTERVAL_DAYS, days)
    ease = _clamp_ease(card.ease + {HARD: EASE_HARD, GOOD: 0.0, EASY: EASE_EASY}[grade])
    return _done(replace(card, ease=ease, interval_days=float(days), reps=reps), now, days * DAY, due, correct)


def _done(card: Card, now: datetime, delay: float, due: bool, correct: bool) -> Outcome:
    return Outcome(replace(card, due_at=now + timedelta(seconds=delay)), True, float(delay), due, correct)


def preview(card: Card, now: datetime, fuzz: float = 1.0) -> dict:
    """Seconds until the card is due again for each answer {1: ..., 4: ...}, so the buttons can say "10m", "1d", "4d"."""
    return {g: review(card, g, now, fuzz).delay_seconds for g in GRADES}


def box_of(card: Card) -> int:
    """The first version's boxes 1 to 5, derived: for the progress card and old exports."""
    if card.phase != REVIEW:
        return 1
    d = card.interval_days
    return 2 if d < 3 else 3 if d < KNOWN_DAYS else 4 if d < 21 else 5


def is_known(card: Card) -> bool:
    return card.phase == REVIEW and card.interval_days >= KNOWN_DAYS


def status_of(card: Card) -> str:
    """new / learning / relearning / young / mature, for display."""
    if card.due_at is None and card.reps == 0:
        return "new"
    if card.phase != REVIEW:
        return card.phase
    return "mature" if card.interval_days >= 21 else "young"


def is_leech(card: Card) -> bool:
    return card.lapses >= LEECH_LAPSES


def format_delay(seconds: float) -> str:
    """"<1m"-style text for a delay: 1m, 10m, 2h, 1d, 3w, 4mo."""
    s = max(0.0, seconds)
    if s < 60:
        return "<1m"
    if s < 3600:
        return f"{round(s / 60)}m"
    if s < DAY:
        return f"{round(s / 3600)}h"
    d = s / DAY
    if d < 14:
        return f"{round(d)}d"
    if d < 60:
        return f"{round(d / 7)}w"
    return f"{round(d / 30)}mo"


# ---------------------------------------------------------------- which words are hardest

SLOW_RATIO = 1.5
OFTEN_MISSED = 0.4
MANY_LAPSES = 3
LOW_EASE = 1.8


def difficulty(reviews: int, again: int, lapses: int, ease: float, avg_think_ms: Optional[float], typical_think_ms: Optional[float]) -> dict:
    """How hard one word is for this learner, 0 to 100, from their own history, with the reasons in plain words.
    miss rate (50%, smoothed so one miss in one try is not 100%), time taken compared with their own typical time (20%), lapses (20%) and
    ease (10%). A word needs two reviews before it can be called hard."""
    miss = (again + 0.5) / (reviews + 1)
    slow_ratio = (avg_think_ms / typical_think_ms) if avg_think_ms and typical_think_ms else None
    slow = 0.0 if slow_ratio is None else min(1.0, max(0.0, (slow_ratio - 1.0) / 2.0))
    lapse = min(1.0, lapses / 5.0)
    low = min(1.0, max(0.0, (START_EASE - ease) / (START_EASE - MIN_EASE)))
    score = round(100 * (0.5 * miss + 0.2 * slow + 0.2 * lapse + 0.1 * low))
    reasons = []
    if reviews >= 2 and miss >= OFTEN_MISSED:
        reasons.append("often_missed")
    if slow_ratio is not None and reviews >= 3 and slow_ratio >= SLOW_RATIO:
        reasons.append("slow")
    if lapses >= MANY_LAPSES:
        reasons.append("lapses")
    if ease <= LOW_EASE:
        reasons.append("low_ease")
    if lapses >= LEECH_LAPSES:
        reasons.append("leech")
    return {"score": score, "reasons": reasons, "miss_rate": round(again / reviews, 2) if reviews else 0.0,
            "slow_ratio": None if slow_ratio is None else round(slow_ratio, 2)}
