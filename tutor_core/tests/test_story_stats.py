"""The small statistics behind the story report's ranges (scripts/story_eval/stats.py, 16 Nov 2026): values checked against worked examples."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from story_eval import stats  # noqa: E402


def test_the_t_value_follows_the_table_and_then_a_close_formula():
    assert stats.t95(1) == 12.706 and stats.t95(9) == 2.262 and stats.t95(30) == 2.042
    assert stats.t95(60) == pytest.approx(2.000, abs=0.002) and stats.t95(120) == pytest.approx(1.980, abs=0.002)
    with pytest.raises(ValueError):
        stats.t95(0)


def test_a_share_of_ten_is_a_wide_range():
    low, high = stats.wilson(4, 10)
    assert (round(low, 3), round(high, 3)) == (0.168, 0.687)
    low, high = stats.wilson(0, 10)
    assert low == 0.0 and round(high, 3) == 0.278
    low, high = stats.wilson(10, 10)
    assert round(low, 3) == 0.722 and high == 1.0
    assert stats.wilson(0, 0) is None
    assert stats.percent_range(4, 10) == "4 of 10 (17–69%)" and stats.percent_range(0, 0) == "–"
    assert stats.wilson(40, 100)[1] - stats.wilson(40, 100)[0] < stats.wilson(4, 10)[1] - stats.wilson(4, 10)[0]       # more stories, a narrower range


def test_the_range_of_a_mean_needs_two_values_and_is_wide_for_few():
    m, low, high = stats.mean_range([1, 2, 3])
    assert m == 2 and round(low, 3) == -0.484 and round(high, 3) == 4.484
    assert stats.mean_range([2]) is None and stats.mean_range([]) is None and stats.mean_range([None, 3]) is None
    same = stats.mean_range([1, 1, 1, 1, 1, 1])
    assert same == (1, 1, 1)


def test_the_sign_test_is_exact_and_five_pairs_can_never_be_enough():
    assert stats.sign_test(5, 0) == pytest.approx(0.0625) and stats.sign_test(6, 0) == pytest.approx(0.03125)
    assert stats.sign_test(8, 2) == pytest.approx(0.109375) and stats.sign_test(3, 3) == 1.0 and stats.sign_test(0, 0) == 1.0
    assert stats.sign_test(2, 8) == stats.sign_test(8, 2)
    assert stats.sign_test(stats.MIN_PAIRS - 1, 0) > 0.05 >= stats.sign_test(stats.MIN_PAIRS, 0)


def test_the_share_explained_by_a_grouping_is_taken_down_by_chance():
    assert stats.variance_share({"a": [1, 1], "b": [5, 5]}) == pytest.approx(1.0)
    assert stats.variance_share({"a": [1, 5], "b": [5, 1]}) == 0.0                 # the groups say nothing: not negative
    assert stats.variance_share({"a": [3, 3], "b": [3, 3]}) is None                   # nothing varies
    assert stats.variance_share({"a": [1, 2, 3]}) is None and stats.variance_share({"a": [1], "b": [2]}) is None
    # an uneven split: the adjusted share is below the plain share 1 - SSW/SST
    groups = {"a": [1, 2, 2], "b": [3, 4, 4], "c": [2, 3, 3]}
    values = [v for vs in groups.values() for v in vs]
    grand = sum(values) / len(values)
    plain = sum(len(vs) * (sum(vs) / len(vs) - grand) ** 2 for vs in groups.values()) / sum((v - grand) ** 2 for v in values)
    assert 0 < stats.variance_share(groups) < plain


def test_the_intraclass_correlation_tells_repeatable_from_random():
    assert stats.icc({"s1": [1, 1], "s2": [5, 5], "s3": [3, 3]}) == pytest.approx(1.0)
    assert stats.icc({"s1": [1, 5], "s2": [5, 1]}) == pytest.approx(-1.0)
    assert stats.icc({"s1": [2, 2, 3], "s2": [4, 4, 4], "s3": [2, 3, 2]}) > 0.6
    assert stats.icc({"only": [1, 2]}) is None and stats.icc({"a": [1], "b": [2]}) is None and stats.icc({"a": [3, 3], "b": [3, 3]}) is None
    assert stats.icc({"s1": [1, 1, 1], "s2": [5, 5]}) == pytest.approx(1.0)               # groups of different sizes
