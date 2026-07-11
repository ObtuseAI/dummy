from __future__ import annotations

from autonomy.sports.mlb_pa_sim import LEAGUE, log5


def test_league_baseline_sums_to_one():
    total = sum(LEAGUE[k] for k in ("k", "bb", "hbp", "hr", "single", "double", "triple", "out"))
    assert abs(total - 1.0) < 1e-9


def test_log5_neutral_returns_league():
    # A league-average batter vs a league-average pitcher yields the league rate.
    assert abs(log5(0.22, 0.22, 0.22) - 0.22) < 1e-9


def test_log5_monotonic_and_bounded():
    league = 0.22
    # A high-K batter vs a high-K pitcher strikes out more than either alone vs average.
    both_high = log5(0.30, 0.28, league)
    one_high = log5(0.30, league, league)
    assert both_high > one_high > league
    # Always within [0, 1].
    assert 0.0 <= log5(0.99, 0.99, 0.22) <= 1.0
    assert 0.0 <= log5(0.01, 0.01, 0.22) <= 1.0
