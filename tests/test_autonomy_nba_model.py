"""NBA pace x efficiency engine (WS-2): unit math + signal integration.

Zero network: all boxscore/game fixtures are hand-built in-memory (mirroring
tests/test_autonomy_nfl_margin.py's pattern) rather than fetched live -- NBA
is offseason at build time (see autonomy/sports/nba_model.py's module
docstring for the build-time scoreboard probe that recorded the live
period/clock field names).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
from autonomy.sports.boxscores import BoxscoreStore, TeamBoxscore
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.nba_model import (
    B2B_ADJUSTMENT,
    MIN_GAMES_FOR_ENGINE,
    NbaModel,
    NbaTeamState,
    REST_BONUS,
    REST_STACK_CAP,
    THREE_IN_FOUR_ADJUSTMENT,
    clamp_margin,
    game_pace,
    heteroskedastic_sigmas,
    is_warm,
    live_win_probability,
    minutes_remaining_in_game,
    possessions,
    rest_adjustment,
    spread_cover_probability,
    win_probability_from_margin,
)
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

NOW = datetime(2026, 1, 12, 16, 0, tzinfo=timezone.utc)


def _box(team: str, opponent: str, is_home: bool, fga: float, orb: float,
         to: float, fta: float, game_id: str = "g1") -> TeamBoxscore:
    return TeamBoxscore(
        game_id=game_id, league="nba", team=team, opponent=opponent, is_home=is_home,
        stats={
            "fieldGoalsAttempted": fga, "offensiveRebounds": orb,
            "turnovers": to, "freeThrowsAttempted": fta,
        },
    )


# ---------------------------------------------------------------- pace math


def test_possessions_formula_matches_the_brief():
    # FGA - ORB + TO + 0.44*FTA
    assert possessions(90.0, 10.0, 14.0, 20.0) == pytest.approx(90 - 10 + 14 + 0.44 * 20, abs=1e-9)


def test_game_pace_averages_both_teams_possession_estimates():
    home = _box("LAL", "BOS", True, fga=90.0, orb=10.0, to=14.0, fta=20.0)
    away = _box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0)
    # possessions_home = 90-10+14+8.8 = 102.8; possessions_away = 88-12+12+7.92 = 95.92
    assert game_pace(home, away) == pytest.approx(99.36, abs=1e-9)


def test_game_pace_missing_stat_key_is_none():
    home = TeamBoxscore(game_id="g1", league="nba", team="LAL", opponent="BOS",
                         is_home=True, stats={})
    away = _box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0)
    assert game_pace(home, away) is None


# ---------------------------------------------------------- heteroskedastic


def test_heteroskedastic_sigma_ratio_pace_105_vs_94():
    total_105, margin_105 = heteroskedastic_sigmas(105.0)
    total_94, margin_94 = heteroskedastic_sigmas(94.0)
    expected_ratio = math.sqrt(105.0 / 94.0)
    assert total_105 / total_94 == pytest.approx(expected_ratio, abs=1e-12)
    assert margin_105 / margin_94 == pytest.approx(expected_ratio, abs=1e-12)
    # Absolute values pin the calibration constants themselves.
    assert total_105 == pytest.approx(19.5 * math.sqrt(105.0 / 99.5), abs=1e-9)
    assert margin_105 == pytest.approx(11.5 * math.sqrt(105.0 / 99.5), abs=1e-9)
    # Faster pace -> wider dispersion.
    assert total_105 > total_94
    assert margin_105 > margin_94


# ------------------------------------------------------------- garbage time


def test_garbage_time_clamp_35_point_blowout_updates_as_25():
    # Home wins 100-65 (margin 35); effective margin clamps to 25.
    effective_home, effective_away = clamp_margin(100.0, 65.0)
    total = 165.0
    assert effective_home == pytest.approx((total + 25.0) / 2.0, abs=1e-9)
    assert effective_away == pytest.approx((total - 25.0) / 2.0, abs=1e-9)
    assert effective_home - effective_away == pytest.approx(25.0, abs=1e-9)


def test_garbage_time_clamp_is_noop_under_the_cap():
    effective_home, effective_away = clamp_margin(100.0, 92.0)  # margin 8
    assert effective_home == pytest.approx(100.0, abs=1e-9)
    assert effective_away == pytest.approx(92.0, abs=1e-9)


def test_garbage_time_clamp_handles_away_blowout_too():
    effective_home, effective_away = clamp_margin(65.0, 100.0)  # margin -35
    total = 165.0
    assert effective_away == pytest.approx((total + 25.0) / 2.0, abs=1e-9)
    assert effective_home == pytest.approx((total - 25.0) / 2.0, abs=1e-9)


def test_update_applies_garbage_time_clamp_before_learning():
    model = NbaModel()
    home = _box("LAL", "BOS", True, fga=90.0, orb=10.0, to=14.0, fta=20.0)
    away = _box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0)
    game = Game("g1", "nba", "LAL", "BOS", "post", True, "2026-01-12T20:00Z",
                home_score=140, away_score=105)  # 35-pt blowout
    assert model.update(game, home, away) is True
    pace = game_pace(home, away)
    lal = model.teams["LAL"]
    # Effective home score used for the ORTG update must be capped at a
    # 25-pt margin, NOT the real 35-pt margin.
    effective_home, _ = clamp_margin(140.0, 105.0)
    expected_ortg = effective_home / pace * 100.0
    from autonomy.sports.nba_model import EWMA_ALPHA, PRIOR_RATING
    assert lal.ortg_ewma == pytest.approx(
        EWMA_ALPHA * expected_ortg + (1 - EWMA_ALPHA) * PRIOR_RATING, abs=1e-9)


# -------------------------------------------------------------- rest engine


def test_b2b_adjustment_applied_and_logged():
    adjustment, days = rest_adjustment(["2026-01-11"], "2026-01-12")
    assert days == 1
    assert adjustment == pytest.approx(B2B_ADJUSTMENT, abs=1e-9)


def test_three_in_four_stacks_with_b2b_but_caps_at_stack_limit():
    adjustment, days = rest_adjustment(
        ["2026-01-09", "2026-01-10", "2026-01-11"], "2026-01-12")
    assert days == 1  # still a b2b
    # b2b (-1.5) + 3-in-4 (-1.0) = -2.5, capped at REST_STACK_CAP (-2.0).
    assert B2B_ADJUSTMENT + THREE_IN_FOUR_ADJUSTMENT < REST_STACK_CAP
    assert adjustment == pytest.approx(REST_STACK_CAP, abs=1e-9)


def test_rest_bonus_for_three_plus_days():
    adjustment, days = rest_adjustment(["2026-01-05"], "2026-01-12")
    assert days == 7
    assert adjustment == pytest.approx(REST_BONUS, abs=1e-9)


def test_rest_adjustment_no_history_is_a_noop():
    adjustment, days = rest_adjustment([], "2026-01-12")
    assert adjustment == 0.0
    assert days is None


def test_predict_applies_rest_adjustment_to_expected_scores():
    model = NbaModel()
    model.teams["LAL"] = NbaTeamState(
        games=30, pace_ewma=99.5, ortg_ewma=114.0, drtg_ewma=114.0,
        recent_dates=["2026-01-11"],  # b2b for LAL
    )
    model.teams["BOS"] = NbaTeamState(games=30, pace_ewma=99.5, ortg_ewma=114.0, drtg_ewma=114.0)
    game = Game("g2", "nba", "LAL", "BOS", "pre", None, "2026-01-12T20:00Z")
    prediction = model.predict(game)
    assert prediction.rest_days_home == 1
    assert prediction.rest_adjustment_home == pytest.approx(B2B_ADJUSTMENT, abs=1e-9)
    assert prediction.rest_days_away is None
    assert prediction.rest_adjustment_away == 0.0
    # Symmetric matchup except for LAL's b2b: expected_home should trail a
    # rest-neutral matchup by exactly the b2b penalty.
    neutral_game = Game("g3", "nba", "LAL", "BOS", "pre", None, "2026-01-01T20:00Z")
    model.teams["LAL"].recent_dates = []
    neutral = model.predict(neutral_game)
    assert prediction.expected_home_score == pytest.approx(
        neutral.expected_home_score + B2B_ADJUSTMENT, abs=1e-9)


# ------------------------------------------------------- winner/ladder coherence


def test_winner_equals_p_margin_greater_than_zero_consistent_with_half_rung():
    margin, sigma = 4.2, 11.5
    winner = win_probability_from_margin(margin, sigma)
    cover_zero = spread_cover_probability(margin, sigma, 0.0)
    assert winner == pytest.approx(cover_zero, abs=1e-12)
    # Coherent with the actual traded 0.5 rung: crossing a positive line
    # costs probability under the SAME distribution.
    cover_half = spread_cover_probability(margin, sigma, 0.5)
    assert winner >= cover_half


# -------------------------------------------------------------- live Brownian


def test_live_win_probability_hand_value_lead_10_twelve_minutes_zero_drift():
    result = live_win_probability(
        lead=10.0, minutes_remaining=12.0, margin_sigma=11.5, expected_margin=0.0)
    sigma_live = 11.5 / math.sqrt(48.0)
    z = 10.0 / (sigma_live * math.sqrt(12.0))
    expected = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    assert result == pytest.approx(expected, abs=1e-12)
    # Sanity: denominator is exactly 5.75 (11.5 * sqrt(12/48) == 11.5*0.5).
    assert sigma_live * math.sqrt(12.0) == pytest.approx(5.75, abs=1e-9)


def test_live_win_probability_increases_with_lead():
    small = live_win_probability(lead=2.0, minutes_remaining=12.0, margin_sigma=11.5)
    big = live_win_probability(lead=15.0, minutes_remaining=12.0, margin_sigma=11.5)
    assert big > small


def test_minutes_remaining_parses_period_and_clock():
    # End of Q1, 12 minutes gone -> 3 quarters (36 min) + the clock itself.
    assert minutes_remaining_in_game(1, "5:30") == pytest.approx(3 * 12 + 5.5, abs=1e-9)
    # Q4 with 2:00 left -> just the clock.
    assert minutes_remaining_in_game(4, "2:00") == pytest.approx(2.0, abs=1e-9)
    assert minutes_remaining_in_game(None, "5:30") is None
    assert minutes_remaining_in_game(1, None) is None
    assert minutes_remaining_in_game(1, "0.0") is None  # final-game display, unparseable as MM:SS


# --------------------------------------------------------- settlement invariant


def test_update_refuses_non_post_status():
    model = NbaModel()
    home = _box("LAL", "BOS", True, fga=90.0, orb=10.0, to=14.0, fta=20.0)
    away = _box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0)
    for status in ("pre", "in"):
        game = Game("g1", "nba", "LAL", "BOS", status, None, "2026-01-12T20:00Z",
                    home_score=100, away_score=90)
        assert model.update(game, home, away) is False
    assert model.games_seen == 0
    assert "LAL" not in model.teams


def test_update_refuses_missing_boxscores_or_scores():
    model = NbaModel()
    home = _box("LAL", "BOS", True, fga=90.0, orb=10.0, to=14.0, fta=20.0)
    game = Game("g1", "nba", "LAL", "BOS", "post", True, "2026-01-12T20:00Z",
                home_score=100, away_score=90)
    assert model.update(game, home, None) is False
    assert model.update(game, None, home) is False
    no_score = Game("g1", "nba", "LAL", "BOS", "post", True, "2026-01-12T20:00Z")
    assert model.update(no_score, home, home) is False


def test_update_is_idempotent_by_game_id():
    model = NbaModel()
    home = _box("LAL", "BOS", True, fga=90.0, orb=10.0, to=14.0, fta=20.0)
    away = _box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0)
    game = Game("g1", "nba", "LAL", "BOS", "post", True, "2026-01-12T20:00Z",
                home_score=100, away_score=90)
    assert model.update(game, home, away) is True
    assert model.update(game, home, away) is False
    assert model.games_seen == 1


# ----------------------------------------------------------------- persistence


def test_save_and_load_round_trips_state(tmp_path):
    model = NbaModel()
    home = _box("LAL", "BOS", True, fga=90.0, orb=10.0, to=14.0, fta=20.0)
    away = _box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0)
    game = Game("g1", "nba", "LAL", "BOS", "post", True, "2026-01-12T20:00Z",
                home_score=100, away_score=90)
    model.update(game, home, away)
    path = tmp_path / "nba_pace_model.json"
    model.save(path)
    reloaded = NbaModel.load(path)
    assert reloaded.teams["LAL"].games == 1
    assert reloaded.teams["LAL"].pace_ewma == pytest.approx(model.teams["LAL"].pace_ewma, abs=1e-12)
    assert reloaded.games_seen == 1
    assert "g1" in reloaded.processed_game_ids


def test_load_missing_file_returns_fresh_model(tmp_path):
    model = NbaModel.load(tmp_path / "does_not_exist.json")
    assert model.teams == {}
    assert model.games_seen == 0


# --------------------------------------------------------------- warm gating


def _warm_store(tmp_path, team: str, n: int = MIN_GAMES_FOR_ENGINE) -> BoxscoreStore:
    store = BoxscoreStore("nba", path=tmp_path / f"boxscores_{team}.json")
    store.ingest([
        _box(team, "XXX", True, fga=90.0, orb=10.0, to=14.0, fta=20.0, game_id=f"g{i}")
        for i in range(n)
    ])
    return store


def test_is_warm_requires_min_games_for_both_teams(tmp_path):
    store = BoxscoreStore("nba", path=tmp_path / "boxscores_nba.json")
    store.ingest([
        _box("LAL", "BOS", True, fga=90.0, orb=10.0, to=14.0, fta=20.0, game_id=f"g{i}")
        for i in range(MIN_GAMES_FOR_ENGINE)
    ])
    assert is_warm(store, "LAL", "BOS") is False  # BOS has 0 games
    store.ingest([
        _box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0, game_id=f"h{i}")
        for i in range(MIN_GAMES_FOR_ENGINE - 1)
    ])
    assert is_warm(store, "LAL", "BOS") is False  # BOS still one short
    store.ingest([_box("BOS", "LAL", False, fga=88.0, orb=12.0, to=12.0, fta=18.0, game_id="hlast")])
    assert is_warm(store, "LAL", "BOS") is True


# ============================================================ signal wiring


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


class _AlwaysActive:
    def active(self, _league):
        return True


def _cold_signal(tmp_path, game: Game):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("nba", "20260112")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
    )
    return signal, models


def test_cold_nba_matchup_falls_back_to_team_score_model_wholesale(tmp_path):
    game = Game("g1", "nba", "LAL", "BOS", "pre", None, "2026-01-12T20:25Z",
                home_name="Los Angeles Lakers", away_name="Boston Celtics")
    signal, models = _cold_signal(tmp_path, game)

    spread = signal.generate(_market(
        "KXNBASPREAD-26JAN12LALBOS-LAL7",
        "Los Angeles Lakers vs Boston Celtics Spread", floor_strike=6.5))
    assert spread is not None
    assert spread.source == "nba_spread"
    assert "margin_model_version" not in spread.features
    assert spread.features["nba_model_fallback"] is True

    # Byte-identical to calling the generic TeamScoreModel directly: replay
    # the exact same formula the pre-WS2 code used.
    reference = TeamScoreModel("nba")
    reference_prediction = reference.predict(game)
    sigma = LEAGUE_SCORE_CONFIGS["nba"].margin_sigma
    subject_margin = reference_prediction.expected_home_score - reference_prediction.expected_away_score
    z = (6.5 - subject_margin) / max(0.25, sigma)
    expected_probability = min(0.995, max(0.005, 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))))
    assert spread.probability_yes == pytest.approx(expected_probability, abs=1e-12)
    assert spread.uncertainty == pytest.approx(
        min(0.44, reference_prediction.winner_uncertainty + 0.02), abs=1e-12)

    winner = signal.generate(_market("KXNBAGAME-26JAN12LALBOS-LAL", "Lakers vs Celtics Winner?"))
    assert winner is not None
    assert winner.features["nba_model_fallback"] is True
    assert "margin_model_version" not in winner.features
    assert winner.probability_yes == pytest.approx(reference_prediction.home_win_probability, abs=1e-12)

    total = signal.generate(_market(
        "KXNBATOTAL-26JAN12LALBOS", "Los Angeles Lakers vs Boston Celtics Total Points",
        floor_strike=220.5))
    assert total is not None
    assert total.features["nba_model_fallback"] is True
    assert "margin_model_version" not in total.features
    assert total.probability_yes == pytest.approx(
        reference.total_probability(reference_prediction, 220.5), abs=1e-12)


def test_cold_nba_live_market_abstains_no_live_path_on_fallback(tmp_path):
    game = Game("g1", "nba", "LAL", "BOS", "in", None, "2026-01-12T20:25Z",
                home_name="Los Angeles Lakers", away_name="Boston Celtics",
                home_score=50, away_score=48, current_period=2, current_clock="5:00")
    signal, _models = _cold_signal(tmp_path, game)
    result = signal.generate(_market("KXNBAGAME-26JAN12LALBOS-LAL", "Lakers vs Celtics Winner?"))
    assert result is None


def _warm_signal(tmp_path, game: Game):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("nba", "20260112")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    store = BoxscoreStore("nba", path=tmp_path / "boxscores_nba.json")
    store.ingest([
        _box("LAL", "BOS", True, fga=92.0, orb=9.0, to=13.0, fta=19.0, game_id=f"gh{i}")
        for i in range(MIN_GAMES_FOR_ENGINE)
    ])
    store.ingest([
        _box("BOS", "LAL", False, fga=90.0, orb=11.0, to=15.0, fta=17.0, game_id=f"ga{i}")
        for i in range(MIN_GAMES_FOR_ENGINE)
    ])
    nba_model = NbaModel()
    nba_model.teams["LAL"] = NbaTeamState(games=10, pace_ewma=101.0, ortg_ewma=117.0, drtg_ewma=112.0)
    nba_model.teams["BOS"] = NbaTeamState(games=10, pace_ewma=98.0, ortg_ewma=115.0, drtg_ewma=113.0)
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
        nba_boxscores=store, nba_model=nba_model,
    )
    return signal, nba_model


def test_warm_nba_matchup_prices_from_the_pace_efficiency_engine(tmp_path):
    game = Game("g1", "nba", "LAL", "BOS", "pre", None, "2026-01-12T20:25Z",
                home_name="Los Angeles Lakers", away_name="Boston Celtics")
    signal, nba_model = _warm_signal(tmp_path, game)
    prediction = nba_model.predict(game)

    winner = signal.generate(_market("KXNBAGAME-26JAN12LALBOS-LAL", "Lakers vs Celtics Winner?"))
    assert winner is not None
    assert winner.source == "nba_structural_winner"
    assert winner.features["margin_model_version"] == "nba_pace_efficiency_v1"
    assert winner.features["nba_model_fallback"] is False
    assert winner.probability_yes == pytest.approx(prediction.home_win_probability, abs=1e-9)

    spread = signal.generate(_market(
        "KXNBASPREAD-26JAN12LALBOS-LAL7",
        "Los Angeles Lakers vs Boston Celtics Spread", floor_strike=3.5))
    assert spread is not None
    assert spread.source == "nba_spread"
    assert spread.features["margin_model_version"] == "nba_pace_efficiency_v1"
    assert spread.probability_yes == pytest.approx(
        nba_model.cover_probability(prediction, True, 3.5), abs=1e-9)

    total = signal.generate(_market(
        "KXNBATOTAL-26JAN12LALBOS", "Los Angeles Lakers vs Boston Celtics Total Points",
        floor_strike=225.5))
    assert total is not None
    assert total.features["margin_model_version"] == "nba_pace_efficiency_v1"
    assert total.probability_yes == pytest.approx(
        nba_model.total_probability(prediction, 225.5), abs=1e-9)
    # Winner/ladder coherence at the signal level too.
    cover_05 = signal.generate(_market(
        "KXNBASPREAD-26JAN12LALBOS-LAL1",
        "Los Angeles Lakers vs Boston Celtics Spread", floor_strike=0.5))
    assert cover_05 is not None
    assert winner.probability_yes >= cover_05.probability_yes


def test_warm_nba_uses_structural_uncertainty_for_all_market_types(tmp_path):
    """Regression: the lone warm engine must not report generic uncertainty."""
    game = Game("g1", "nba", "LAL", "BOS", "pre", None, "2026-01-12T20:25Z",
                home_name="Los Angeles Lakers", away_name="Boston Celtics")
    signal, nba_model = _warm_signal(tmp_path, game)
    prediction = nba_model.predict(game)

    winner = signal.generate(_market(
        "KXNBAGAME-26JAN12LALBOS-LAL", "Lakers vs Celtics Winner?"))
    spread = signal.generate(_market(
        "KXNBASPREAD-26JAN12LALBOS-LAL7",
        "Los Angeles Lakers vs Boston Celtics Spread", floor_strike=3.5))
    total = signal.generate(_market(
        "KXNBATOTAL-26JAN12LALBOS", "Los Angeles Lakers vs Boston Celtics Total Points",
        floor_strike=225.5))

    assert winner is not None and spread is not None and total is not None
    assert winner.uncertainty == pytest.approx(prediction.winner_uncertainty)
    assert spread.uncertainty == pytest.approx(
        min(0.44, prediction.winner_uncertainty + 0.02))
    assert total.uncertainty == pytest.approx(prediction.total_uncertainty)


def test_warm_nba_live_game_prices_from_brownian_diffusion(tmp_path):
    game = Game("g1", "nba", "LAL", "BOS", "in", None, "2026-01-12T20:25Z",
                home_name="Los Angeles Lakers", away_name="Boston Celtics",
                home_score=60, away_score=50, current_period=3, current_clock="6:00")
    signal, nba_model = _warm_signal(tmp_path, game)
    prediction = nba_model.predict(game)
    minutes_remaining = minutes_remaining_in_game(3, "6:00")

    winner = signal.generate(_market("KXNBAGAME-26JAN12LALBOS-LAL", "Lakers vs Celtics Winner?"))
    assert winner is not None
    assert winner.source == "nba_live_winner"
    assert winner.features["live"] is True
    expected = nba_model.live_win_probability_for(prediction, 60, 50, minutes_remaining)
    assert winner.probability_yes == pytest.approx(expected, abs=1e-9)
    # Home is up 10 with plenty of time left -- should be a big favorite.
    assert winner.probability_yes > 0.9

    total = signal.generate(_market(
        "KXNBATOTAL-26JAN12LALBOS", "Los Angeles Lakers vs Boston Celtics Total Points",
        floor_strike=225.5))
    assert total is not None
    assert total.source == "nba_live_total"
    assert total.probability_yes == pytest.approx(
        nba_model.live_total_probability_for(prediction, 110, 225.5, minutes_remaining), abs=1e-9)


def test_warm_nba_live_missing_period_abstains(tmp_path):
    game = Game("g1", "nba", "LAL", "BOS", "in", None, "2026-01-12T20:25Z",
                home_name="Los Angeles Lakers", away_name="Boston Celtics",
                home_score=60, away_score=50, current_period=None)
    signal, _model = _warm_signal(tmp_path, game)
    result = signal.generate(_market("KXNBAGAME-26JAN12LALBOS-LAL", "Lakers vs Celtics Winner?"))
    assert result is None
