from datetime import date, timedelta

from tutor_core import rewards as r

T = date(2026, 11, 13)


def ago(*n):
    return [T - timedelta(days=k) for k in n]


def test_plain_streak_and_today_still_open():
    assert r.streak_of(ago(0, 1, 2, 3), T)["days"] == 4
    s = r.streak_of(ago(1, 2, 3), T)
    assert s["days"] == 3 and s["alive"] and not s["practised_today"]
    assert r.streak_of([], T)["days"] == 0


def test_a_single_missed_day_is_forgiven_once_a_week():
    s = r.streak_of(ago(0, 1, 3, 4), T)                      # day 2 missed
    assert s["days"] == 4 and s["rest_used_on"] == T - timedelta(days=2) and s["rest_available"] is False
    assert r.streak_of(ago(0, 1, 2, 3, 4, 5), T)["rest_available"] is True


def test_two_rests_in_one_week_end_the_streak():
    assert r.streak_of(ago(0, 2, 4, 5), T)["days"] == 2                 # 1 and 3 both missed: the second rest is not forgiven
    assert r.streak_of(ago(0, 2, 3), T)["days"] == 3


def test_a_rest_is_available_again_after_a_week():
    days = ago(0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11)           # day 9 missed, then 7 days straight
    s = r.streak_of(days, T)
    assert s["days"] == 11 and s["rest_available"] is True


def test_yesterday_missed_keeps_it_alive_until_today_ends_but_two_days_does_not():
    s = r.streak_of(ago(2, 3, 4), T)
    assert s["alive"] and s["days"] == 3 and s["rest_used_on"] == T - timedelta(days=1) and s["rest_available"] is False
    assert r.streak_of(ago(3, 4, 5), T) == {"days": 0, "alive": False, "practised_today": False, "rest_available": True, "rest_used_on": None}


def test_best_streak():
    days = ago(30, 29, 28, 27, 26, 25, 24, 10, 9, 0)
    assert r.best_streak(days) == 7 and r.best_streak([]) == 0


def test_goal():
    assert r.clamp_goal(1) == 5 and r.clamp_goal(500) == 100 and r.clamp_goal(20) == 20
    assert r.goal_state(10, 4) == {"target": 10, "done": 4, "reached": False, "left": 6}
    assert r.goal_state(10, 12)["reached"] is True and r.goal_state(10, 12)["left"] == 0


def test_badges_and_the_next_one():
    items = r.badges({"answers": 5, "known_words": 30, "best_streak": 2, "stories": 0})
    got = {b["id"]: b for b in items}
    assert got["first_answer"]["earned"] and got["known_10"]["earned"] and not got["known_50"]["earned"]
    assert got["known_50"]["have"] == 30 and got["known_50"]["target"] == 50
    nxt = r.next_badge(items)
    assert nxt["id"] == "streak_3"                                          # 2 of 3 days is further along than 30 of 50 words
    assert r.next_badge([b | {"earned": True} for b in items]) is None


def test_comeback_needs_a_break_of_three_days():
    from datetime import date
    from tutor_core.rewards import comeback
    t = date(2026, 11, 14)
    assert comeback([], t) is None
    assert comeback([date(2026, 11, 13)], t) is None
    assert comeback([date(2026, 11, 11)], t) == {"days_away": 3, "returned": False}
    assert comeback([t, date(2026, 11, 8)], t) == {"days_away": 6, "returned": True}
    assert comeback([t, date(2026, 11, 13)], t) is None
    assert comeback([t], t) is None


def test_longest_run_ends_at_again():
    from tutor_core.rewards import longest_run
    assert longest_run([3, 4, 1, 2, 2, 2, 1]) == 3 and longest_run([]) == 0 and longest_run([1, 1]) == 0


def test_words_in_stories_matches_whole_words_and_cjk_substrings():
    from tutor_core.rewards import words_in_stories
    assert words_in_stories(["Cat", "dog", "catalog", ""], ["The cat sat.", "A catalogue."]) == 1
    assert words_in_stories(["猫", "犬"], ["私は猫が好きです。"]) == 1
    assert words_in_stories(["a b"], ["x a b y"]) == 1


def test_the_weekly_challenge_rotates_and_reports_progress():
    from datetime import date
    from tutor_core.rewards import CHALLENGES, weekly_challenge
    seen = set()
    for w in range(4):
        monday = date(2026, 11, 2).replace(day=2 + 7 * w) if w < 4 else None
        seen.add(weekly_challenge(monday, {})["id"])
    assert seen == {c[0] for c in CHALLENGES}
    t = date(2026, 11, 14)                                  # a Saturday; the week ran Monday 9 to Sunday 15 November
    c = weekly_challenge(t, {"words_learned": 4, "days": 2, "answers": 40, "stories": 1})
    assert c["ends_on"] == date(2026, 11, 15) and c["done"] is False and c["have"] < c["target"]
    done = weekly_challenge(t, {"words_learned": 99, "days": 7, "answers": 999, "stories": 9})
    assert done["done"] is True and done["have"] == done["target"]


def test_story_counts_counts_stories_not_mentions_and_matches_whole_words():
    from tutor_core.rewards import story_counts
    stories = ["The cat sat. The cat ran.", "A cathedral. Au revoir, cat!", "你好，朋友"]
    got = story_counts(["cat", "Au revoir", "dog", "你好", "朋友", "art"], stories)
    assert got == {"cat": 2, "au revoir": 1, "dog": 0, "你好": 1, "朋友": 1, "art": 0}
    assert story_counts([], stories) == {} and story_counts(["cat"], []) == {"cat": 0}
