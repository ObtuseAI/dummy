from __future__ import annotations

from autonomy.sports.mlb_pa_sim import LEAGUE, log5, PA_OUTCOMES, plate_appearance_distribution
from autonomy.sports.statsapi import BatterRates, PitcherRates


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


def _batter(k, bb, obp, slg, iso):
    return BatterRates(player_id=1, k_pct=k, bb_pct=bb, obp=obp, slg=slg, iso=iso)


def _pitcher(k, bb, hr9):
    return PitcherRates(player_id=2, k_pct=k, bb_pct=bb, hr9=hr9)


def test_distribution_sums_to_one_and_covers_all_outcomes():
    dist = plate_appearance_distribution(
        _batter(0.20, 0.09, 0.34, 0.45, 0.18),
        _pitcher(0.24, 0.07, 1.1),
    )
    assert set(dist) == set(PA_OUTCOMES)
    assert abs(sum(dist.values()) - 1.0) < 1e-9
    assert all(0.0 <= p <= 1.0 for p in dist.values())


def test_none_rates_fall_back_to_league_average():
    dist = plate_appearance_distribution(None, None)
    # With no player data the distribution should be close to LEAGUE.
    assert abs(dist["k"] - LEAGUE["k"]) < 0.03
    assert abs(sum(dist.values()) - 1.0) < 1e-9


def test_high_strikeout_pitcher_raises_k_share():
    weak_k = plate_appearance_distribution(_batter(0.22, 0.08, 0.32, 0.40, 0.15),
                                           _pitcher(0.18, 0.08, 1.2))
    high_k = plate_appearance_distribution(_batter(0.22, 0.08, 0.32, 0.40, 0.15),
                                           _pitcher(0.33, 0.08, 1.2))
    assert high_k["k"] > weak_k["k"]


def test_park_hr_factor_increases_home_run_share():
    neutral = plate_appearance_distribution(_batter(0.20, 0.09, 0.34, 0.50, 0.22),
                                            _pitcher(0.22, 0.08, 1.3), park_hr_factor=1.0)
    hitter = plate_appearance_distribution(_batter(0.20, 0.09, 0.34, 0.50, 0.22),
                                           _pitcher(0.22, 0.08, 1.3), park_hr_factor=1.3)
    assert hitter["hr"] > neutral["hr"]


def test_platoon_advantage_raises_offensive_share():
    b = _batter(0.20, 0.09, 0.34, 0.45, 0.18)
    p = _pitcher(0.22, 0.08, 1.2)
    favored = plate_appearance_distribution(b, p, platoon=1.07)
    neutral = plate_appearance_distribution(b, p, platoon=1.0)
    off = lambda d: d["bb"] + d["hr"] + d["single"] + d["double"] + d["triple"]
    assert off(favored) > off(neutral)  # platoon>1 lifts the batter's offense
    assert abs(sum(favored.values()) - 1.0) < 1e-9


def test_higher_slugging_raises_hit_share():
    low = plate_appearance_distribution(_batter(0.20, 0.09, 0.34, 0.38, 0.10),
                                        _pitcher(0.22, 0.08, 1.2))
    high = plate_appearance_distribution(_batter(0.20, 0.09, 0.34, 0.58, 0.10),
                                         _pitcher(0.22, 0.08, 1.2))
    hits = lambda d: d["single"] + d["double"] + d["triple"]
    assert hits(high) > hits(low)  # slugging drives on-contact hit quality


def test_extreme_rates_keep_distribution_valid():
    # A very high K + BB + HR combo drives the pre-normalization remainder to zero;
    # the distribution must still sum to 1 with every value in [0,1].
    d = plate_appearance_distribution(
        _batter(0.40, 0.20, 0.45, 0.70, 0.35),
        _pitcher(0.38, 0.14, 2.5), park_hr_factor=1.5, platoon=1.1,
    )
    assert abs(sum(d.values()) - 1.0) < 1e-9
    assert all(0.0 <= v <= 1.0 for v in d.values())
