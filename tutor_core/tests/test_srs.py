"""The spaced repetition scheduler (srs.py): learning steps, review intervals, lapses, early practice, previews and the hardest-word score."""
from datetime import datetime, timedelta, timezone

import pytest

from tutor_core import srs
from tutor_core.srs import AGAIN, EASY, GOOD, HARD, Card

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
DAY = 86400


def graduate(now=NOW):
    """A new card answered Good twice: in review, resting 1 day."""
    a = srs.review(Card(), GOOD, now)
    return srs.review(a.card, GOOD, now + timedelta(seconds=600)).card


def test_a_new_card_climbs_the_learning_steps():
    a = srs.review(Card(), GOOD, NOW)
    assert a.card.phase == srs.LEARNING and a.card.step == 1 and a.delay_seconds == 600 and a.counted and a.was_due
    b = srs.review(a.card, GOOD, NOW + timedelta(minutes=10))
    assert b.card.phase == srs.REVIEW and b.card.interval_days == 1 and b.delay_seconds == DAY
    assert srs.review(Card(), EASY, NOW).card.interval_days == 4
    again = srs.review(a.card, AGAIN, NOW)
    assert again.card.step == 0 and again.delay_seconds == 60
    assert srs.review(Card(), HARD, NOW).delay_seconds == 90 and srs.review(Card(), HARD, NOW).card.phase == srs.LEARNING


def test_review_intervals_grow_by_ease_and_answers_are_ordered():
    card = graduate()
    due = card.due_at
    ordered = [srs.review(card, g, due).card.interval_days for g in (HARD, GOOD, EASY)]
    assert ordered[0] < ordered[1] < ordered[2]
    good = srs.review(card, GOOD, due).card
    assert good.interval_days == 3 and good.ease == 2.5                    # 1 day x 2.5 = 2.5 -> but never below hard + 1
    assert srs.review(card, HARD, due).card.ease == 2.35 and srs.review(card, EASY, due).card.ease == 2.65
    again = srs.review(good, GOOD, good.due_at).card
    assert again.interval_days >= 7                                         # 3 x 2.5 = 7.5


def test_a_late_review_gets_credit_and_the_interval_has_a_ceiling():
    card = srs.review(srs.review(Card(), GOOD, NOW).card, GOOD, NOW).card
    on_time = srs.review(card, GOOD, card.due_at).card.interval_days
    late = srs.review(card, GOOD, card.due_at + timedelta(days=6)).card.interval_days
    assert late > on_time
    huge = Card(phase=srs.REVIEW, ease=3.5, interval_days=300, reps=9, due_at=NOW)
    assert srs.review(huge, EASY, NOW).card.interval_days == srs.MAX_INTERVAL_DAYS


def test_a_miss_in_review_is_a_lapse_and_comes_back_after_relearning():
    card = Card(phase=srs.REVIEW, ease=2.5, interval_days=20, reps=5, due_at=NOW)
    miss = srs.review(card, AGAIN, NOW)
    assert miss.card.phase == srs.RELEARNING and miss.card.lapses == 1 and miss.card.ease == 2.3 and miss.card.interval_days == 10
    assert miss.delay_seconds == 600 and not miss.correct
    back = srs.review(miss.card, GOOD, NOW + timedelta(minutes=10)).card
    assert back.phase == srs.REVIEW and back.interval_days == 10
    floor = srs.review(Card(phase=srs.REVIEW, ease=1.35, interval_days=1, reps=2, due_at=NOW), AGAIN, NOW).card
    assert floor.ease == srs.MIN_EASE and floor.interval_days == 1


def test_practising_early_and_remembering_moves_nothing_but_a_miss_always_counts():
    card = Card(phase=srs.REVIEW, ease=2.5, interval_days=10, reps=4, due_at=NOW + timedelta(days=5))
    for grade in (HARD, GOOD, EASY):
        out = srs.review(card, grade, NOW)
        assert not out.counted and out.card.due_at == card.due_at and out.card.interval_days == 10 and out.card.ease == 2.5 and out.correct
        assert out.card.reps == 5 and not out.was_due
    assert srs.review(card, AGAIN, NOW).card.phase == srs.RELEARNING


def test_fuzz_spreads_long_intervals_only_and_is_repeatable():
    assert srs.fuzz_factor(7) == srs.fuzz_factor(7) and all(0.95 <= srs.fuzz_factor(i) <= 1.05 for i in range(200))
    assert len({srs.fuzz_factor(i) for i in range(50)}) > 30
    card = Card(phase=srs.REVIEW, ease=2.5, interval_days=20, reps=4, due_at=NOW)
    days = {srs.review(card, GOOD, NOW, srs.fuzz_factor(i)).card.interval_days for i in range(40)}
    assert len(days) > 3 and all(47 <= d <= 53 for d in days)
    short = Card(phase=srs.REVIEW, ease=2.5, interval_days=1, reps=2, due_at=NOW)
    assert len({srs.review(short, GOOD, NOW, srs.fuzz_factor(i)).card.interval_days for i in range(40)}) == 1


def test_preview_matches_what_each_answer_does_and_formats_for_buttons():
    card = graduate()
    p = srs.preview(card, card.due_at)
    assert p[AGAIN] == 600 and p[HARD] < p[GOOD] < p[EASY]
    for g in srs.GRADES:
        assert p[g] == srs.review(card, g, card.due_at).delay_seconds
    assert [srs.format_delay(s) for s in (30, 60, 600, 7200, DAY, 3 * DAY, 21 * DAY, 90 * DAY)] == ["<1m", "1m", "10m", "2h", "1d", "3d", "3w", "3mo"]
    with pytest.raises(ValueError):
        srs.review(card, 5, NOW)


def test_boxes_status_and_leech():
    assert srs.box_of(Card()) == 1 and srs.status_of(Card()) == "new"
    r = lambda d: Card(phase=srs.REVIEW, interval_days=d, reps=3, due_at=NOW)
    assert [srs.box_of(r(d)) for d in (1, 3, 7, 21, 60)] == [2, 3, 4, 5, 5]
    assert srs.is_known(r(7)) and not srs.is_known(r(6)) and srs.status_of(r(30)) == "mature" and srs.status_of(r(2)) == "young"
    assert srs.is_leech(Card(lapses=8)) and not srs.is_leech(Card(lapses=7))
    assert srs.status_of(Card(phase=srs.RELEARNING, reps=3, due_at=NOW)) == "relearning"


def test_difficulty_ranks_missed_slow_lapsed_words_above_easy_ones_and_names_why():
    hard = srs.difficulty(reviews=8, again=5, lapses=4, ease=1.7, avg_think_ms=9000, typical_think_ms=3000)
    easy = srs.difficulty(reviews=8, again=0, lapses=0, ease=2.7, avg_think_ms=2500, typical_think_ms=3000)
    assert hard["score"] > 60 > 15 > easy["score"] - 1 and easy["reasons"] == []
    assert set(hard["reasons"]) == {"often_missed", "slow", "lapses", "low_ease"}
    one = srs.difficulty(reviews=1, again=1, lapses=1, ease=2.3, avg_think_ms=None, typical_think_ms=None)
    assert one["score"] < hard["score"] and "slow" not in one["reasons"]
    assert "leech" in srs.difficulty(20, 12, 9, 1.3, 5000, 4000)["reasons"]
