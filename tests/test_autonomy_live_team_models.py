"""League-specific live-state challenger tests (zero network)."""
from __future__ import annotations

import pytest

from autonomy.sports.live_team_models import (
    FootballOvertimeState,
    NcaafLiveModel,
    NcaambLiveModel,
    NflLiveModel,
    compound_poisson_points,
    football_minutes_remaining,
    ncaamb_minutes_remaining,
    parse_clock_minutes,
    parse_football_overtime_state,
)


def test_live_clock_parsers_use_league_specific_game_shapes():
    assert parse_clock_minutes("07:30", 15.0) == pytest.approx(7.5)
    assert football_minutes_remaining(2, "07:30") == pytest.approx(37.5)
    assert football_minutes_remaining(5, "10:00") is None  # OT abstains
    assert ncaamb_minutes_remaining(1, "12:00") == pytest.approx(32.0)
    assert ncaamb_minutes_remaining(2, "12:00") == pytest.approx(12.0)
    assert ncaamb_minutes_remaining(3, "04:30") == pytest.approx(4.5)
    assert parse_clock_minutes("15:01", 15.0) is None
    assert parse_clock_minutes("bad", 15.0) is None


def test_compound_poisson_points_preserves_mass_and_target_mean():
    pmf = compound_poisson_points(24.0, {3: 0.35, 7: 0.65})
    assert sum(pmf.values()) == pytest.approx(1.0)
    assert sum(points * mass for points, mass in pmf.items()) == pytest.approx(24.0, abs=0.01)
    assert compound_poisson_points(0.0, {3: 1.0}) == {0: 1.0}


def test_nfl_live_model_collapses_to_observed_score_at_expiry():
    model = NflLiveModel()
    forecast = model.forecast(24.0, 21.0, home_score=20, away_score=17, minutes_remaining=0.0)
    assert forecast.expected_home_score == pytest.approx(20.0)
    assert forecast.expected_away_score == pytest.approx(17.0)
    assert forecast.home_win_probability == pytest.approx(0.9995)
    assert forecast.cover_probability(True, 2.5) == pytest.approx(0.9995)
    assert forecast.cover_probability(True, 3.5) == pytest.approx(0.0005)
    assert forecast.total_probability(36.5) == pytest.approx(0.9995)


def test_nfl_live_winner_and_spread_share_one_margin_distribution():
    forecast = NflLiveModel().forecast(
        27.0, 20.0, home_score=14, away_score=10, minutes_remaining=22.0)
    assert forecast.cover_probability(True, 0.5) <= forecast.home_win_probability
    assert forecast.cover_probability(True, 6.5) <= forecast.cover_probability(True, 2.5)
    assert forecast.expected_total > 24.0


def test_ncaaf_is_a_separate_scoring_model_not_an_nfl_alias():
    nfl = NflLiveModel().forecast(31.0, 28.0, 14, 14, 30.0)
    ncaaf = NcaafLiveModel().forecast(31.0, 28.0, 14, 14, 30.0)
    assert nfl.model_version != ncaaf.model_version
    assert nfl.margin_pmf != ncaaf.margin_pmf
    assert nfl.home_win_probability != pytest.approx(ncaaf.home_win_probability)


def test_football_live_probability_responds_to_score_and_clock():
    model = NflLiveModel()
    early = model.forecast(24.0, 24.0, 21, 14, 45.0)
    late = model.forecast(24.0, 24.0, 21, 14, 2.0)
    assert late.home_win_probability > early.home_win_probability


def test_ncaamb_uses_40_minute_remainder_and_own_sigmas():
    model = NcaambLiveModel()
    forecast = model.forecast(
        expected_home_score=74.0,
        expected_away_score=70.0,
        margin_sigma=10.5,
        total_sigma=17.0,
        home_score=38,
        away_score=35,
        minutes_remaining=20.0,
    )
    assert forecast.expected_home_score == pytest.approx(75.0)
    assert forecast.expected_away_score == pytest.approx(70.0)
    assert forecast.expected_total == pytest.approx(145.0)
    assert forecast.margin_sigma_remaining == pytest.approx(10.5 / 2**0.5)
    assert forecast.cover_probability(True, 2.5) < forecast.home_win_probability


def test_ncaamb_late_score_dominates_pregame_strength():
    model = NcaambLiveModel()
    trailing_early = model.forecast(80.0, 60.0, 10.5, 17.0, 40, 50, 20.0)
    trailing_late = model.forecast(80.0, 60.0, 10.5, 17.0, 40, 50, 1.0)
    assert trailing_early.home_win_probability > trailing_late.home_win_probability
    assert trailing_late.home_win_probability < 0.01


def test_parse_nfl_overtime_state_requires_current_possession_and_counts_drives():
    summary = {"drives": {
        "previous": [{
            "team": {"abbreviation": "BUF"},
            "start": {"period": {"number": 5}},
        }],
        "current": {"team": {"abbreviation": "KC"}},
    }}
    state = parse_football_overtime_state(
        summary, league="nfl", period=5, display_clock="6:30")
    assert state == FootballOvertimeState(5, "KC", ("BUF",), 6.5)
    assert parse_football_overtime_state(
        {"drives": {}}, league="nfl", period=5, display_clock="6:30") is None


def test_parse_ncaaf_overtime_state_counts_only_current_round():
    summary = {"drives": {
        "previous": [
            {"team": {"abbreviation": "UGA"}, "start": {"period": {"number": 5}}},
            {"team": {"abbreviation": "ALA"}, "start": {"period": {"number": 6}}},
        ],
        "current": {"team": {"abbreviation": "UGA"}},
    }}
    state = parse_football_overtime_state(
        summary, league="ncaaf", period=6, display_clock="0:00")
    assert state == FootballOvertimeState(6, "UGA", ("ALA",), None)


def test_nfl_overtime_forecast_is_possession_aware_and_coherent():
    model = NflLiveModel()
    first = model.forecast_overtime(
        27.0, 24.0, 24, 24, "KC", "BUF",
        FootballOvertimeState(5, "KC", (), 9.5))
    second = model.forecast_overtime(
        27.0, 24.0, 24, 24, "KC", "BUF",
        FootballOvertimeState(5, "KC", ("BUF",), 5.0))
    assert first is not None and second is not None
    assert first.overtime and first.possession_team == "KC"
    assert second.home_win_probability > first.home_win_probability
    assert sum(second.margin_pmf.values()) == pytest.approx(1.0)
    assert sum(second.total_pmf.values()) == pytest.approx(1.0)
    assert second.cover_probability(True, 0.5) <= second.home_win_probability


def test_ncaaf_third_overtime_uses_two_point_outcomes():
    forecast = NcaafLiveModel().forecast_overtime(
        31.0, 28.0, 35, 35, "UGA", "ALA",
        FootballOvertimeState(7, "UGA", (), None))
    assert forecast is not None and forecast.overtime
    assert all(total >= 70 for total in forecast.total_pmf)
    assert all((total - 70) % 2 == 0 for total in forecast.total_pmf)
