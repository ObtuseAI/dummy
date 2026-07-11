"""Tests for `autonomy.sports.mlb_matchups` (Task 5: rivalry/divisional awareness)."""
from __future__ import annotations

from autonomy.sports.mlb_matchups import DIVISIONS, RIVALRIES, is_divisional, is_rivalry


def test_divisions_table_has_exactly_thirty_teams():
    assert len(DIVISIONS) == 30
    assert len(set(DIVISIONS.values())) == 6  # 6 divisions


def test_divisions_table_has_six_teams_per_division():
    from collections import Counter
    counts = Counter(DIVISIONS.values())
    assert len(counts) == 6
    assert all(count == 5 for count in counts.values())


def test_athletics_key_matches_ballpark_table():
    # The ballpark table (autonomy/sports/ballpark_weather.py) keys the
    # Athletics as "ATH", not "OAK" or "ATH2025" -- the divisions table must
    # match so callers can key off either table interchangeably.
    assert "ATH" in DIVISIONS
    assert "OAK" not in DIVISIONS


def test_divisions_table_keys_match_ballpark_table():
    from autonomy.sports.ballpark_weather import BALLPARKS
    assert set(DIVISIONS) == set(BALLPARKS)


def test_is_divisional_true_for_same_division_teams():
    assert is_divisional("NYY", "BOS") is True  # both AL East
    assert is_divisional("LAD", "SF") is True  # both NL West


def test_is_divisional_false_for_cross_division_teams():
    assert is_divisional("NYY", "LAD") is False  # AL East vs NL West


def test_is_divisional_symmetric():
    assert is_divisional("NYY", "BOS") == is_divisional("BOS", "NYY")
    assert is_divisional("NYY", "LAD") == is_divisional("LAD", "NYY")


def test_is_divisional_unknown_team_is_false():
    assert is_divisional("NYY", "ZZZ") is False
    assert is_divisional("ZZZ", "YYY") is False


def test_is_rivalry_true_for_known_pairs():
    assert is_rivalry("NYY", "BOS") is True
    assert is_rivalry("LAD", "SF") is True
    assert is_rivalry("CHC", "STL") is True


def test_is_rivalry_symmetric():
    assert is_rivalry("NYY", "BOS") == is_rivalry("BOS", "NYY")


def test_is_rivalry_false_for_unrelated_teams():
    assert is_rivalry("MIA", "SEA") is False


def test_is_rivalry_unknown_team_is_false():
    assert is_rivalry("NYY", "ZZZ") is False


def test_rivalries_table_has_real_pairs_and_is_reasonably_sized():
    assert 8 <= len(RIVALRIES) <= 12
    assert all(isinstance(pair, frozenset) and len(pair) == 2 for pair in RIVALRIES)
    # Every team named in a rivalry pair must be a real DIVISIONS team.
    for pair in RIVALRIES:
        for team in pair:
            assert team in DIVISIONS
