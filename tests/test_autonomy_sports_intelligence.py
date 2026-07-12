"""MLB/UFC/all-sport intelligence and recursive simulation invariants."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.forecaster import EnsembleForecaster
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.scanner import WATCHLIST_SERIES, classify_vertical
from autonomy.signals.sports_intelligence import (
    BaseballIntelligenceSignal,
    TeamSportsIntelligenceSignal,
    UfcIntelligenceSignal,
    parse_sports_contract,
)
from autonomy.sports.baseball import BaseballRunModel, poisson_over_probability
from autonomy.sports.espn import EspnClient, Game, canonical_team, parse_scoreboard
from autonomy.sports.formula_one import F1Model, parse_f1_scoreboard
from autonomy.sports.simulation import (
    DESIGNATED_SPORTS_PREDICTION_TYPES,
    FORCED_COVERAGE_LANE,
    POLICY_LANE,
    RecursiveSportsLab,
    SportsEvidenceLedger,
    SportsGenome,
    SportsMonteCarloSimulator,
    SportsObservation,
    chronological_folds,
    curriculum_stage,
    evaluate_genome,
    forced_coverage_action,
    mutate_population,
    paper_action,
    paper_decision_explanation,
    paired_cluster_bootstrap,
    sports_coverage_assessment,
    unlocked_mutations,
)
from autonomy.sports.team_scores import TeamScoreModel
from autonomy.sports.ufc import UfcEspnClient, UfcModel, parse_ufc_scoreboard

NOW = datetime(2026, 7, 10, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker,
        title=title,
        vertical=Vertical.SPORTS,
        status="open",
        close_time=(NOW + timedelta(days=2)).isoformat(),
        yes_bid=44,
        yes_ask=46,
        no_bid=54,
        no_ask=56,
        volume=500,
        liquidity=1_000,
        raw=payload,
    )


def _mlb_game(status: str = "pre", home_score=None, away_score=None,
              current_period=None) -> Game:
    return Game(
        game_id="g1", league="mlb", home="TEX", away="HOU", status=status,
        home_won=(None if status != "post" else home_score > away_score),
        date="2026-07-10T20:05:00Z",
        home_pitcher_era=5.2, away_pitcher_era=2.5,
        home_pitcher="Home Starter", away_pitcher="Away Starter",
        home_score=home_score, away_score=away_score,
        home_first_inning_runs=(0 if status == "post" else None),
        away_first_inning_runs=(1 if status == "post" else None),
        current_period=current_period,
        venue="Test Park", home_name="Texas Rangers", away_name="Houston Astros",
    )


def test_real_kalshi_mlb_contract_families_parse():
    winner = parse_sports_contract(_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?",
        yes_sub_title="Houston",
    ))
    total = parse_sports_contract(_market(
        "KXMLBTOTAL-26JUL102005HOUTEX-9", "Houston vs Texas Total Runs?",
        floor_strike=8.5,
    ))
    rfi = parse_sports_contract(_market(
        "KXMLBRFI-26JUL102005HOUTEX", "Houston vs Texas First Inning Run?",
        floor_strike=1,
    ))
    assert (winner.sport, winner.market_type, winner.subject) == ("mlb", "winner", "HOU")
    assert total.market_type == "total_runs" and total.threshold == 8.5
    assert rfi.market_type == "yrfi"
    assert total.competitors == ("HOU", "TEX")


def test_exact_requested_sports_series_are_in_public_scanner_watchlist():
    required = {
        "KXMLBGAME", "KXMLBTOTAL", "KXMLBRFI", "KXMLBSPREAD",
        "KXNBAGAME", "KXNBATOTAL", "KXNFLGAME", "KXNFLTOTAL",
        "KXNCAAFGAME", "KXNCAAFTOTAL", "KXNHLGAME", "KXNHLTOTAL",
        "KXNCAAMBGAME", "KXNCAAMBTOTAL", "KXUFCFIGHT", "KXUFCROUNDS",
        "KXUFCDISTANCE", "KXF1RACE",
    }
    assert required <= set(WATCHLIST_SERIES)
    assert classify_vertical("KXF1RACE-BELGP26-VER") is Vertical.SPORTS
    assert classify_vertical("KXMLBSPREAD-26JUL112110AZLAD-AZ8") is Vertical.SPORTS


def test_scoreboard_retains_final_scores_and_first_inning():
    payload = {"events": [{
        "id": "g1", "date": "2026-07-09T16:35Z",
        "competitions": [{
            "status": {"type": {"state": "post"}},
            "venue": {"fullName": "PNC Park", "indoor": False},
            "competitors": [
                {"homeAway": "home", "winner": False, "score": "5",
                 "team": {"abbreviation": "PIT", "displayName": "Pittsburgh Pirates"},
                 "linescores": [{"period": 1, "value": 0}]},
                {"homeAway": "away", "winner": True, "score": "10",
                 "team": {"abbreviation": "ATL", "displayName": "Atlanta Braves"},
                 "linescores": [{"period": 1, "value": 1}]},
            ],
        }],
    }]}
    game = parse_scoreboard("mlb", payload)[0]
    assert (game.home_score, game.away_score) == (5, 10)
    assert (game.home_first_inning_runs, game.away_first_inning_runs) == (0, 1)
    assert game.home_name == "Pittsburgh Pirates"


def test_scoreboard_captures_live_score_and_inning():
    payload = {"events": [{
        "id": "g2", "date": "2026-07-12T20:05Z",
        "competitions": [{
            "status": {"type": {"state": "in"}, "period": 6},
            "venue": {"fullName": "Globe Life Field", "indoor": True},
            "competitors": [
                {"homeAway": "home", "score": "4",
                 "team": {"abbreviation": "TEX", "displayName": "Texas Rangers"}},
                {"homeAway": "away", "score": "1",
                 "team": {"abbreviation": "HOU", "displayName": "Houston Astros"}},
            ],
        }],
    }]}
    game = parse_scoreboard("mlb", payload)[0]
    assert game.status == "in"
    assert (game.home_score, game.away_score) == (4, 1)  # live scores captured
    assert game.current_period == 6
    # First-inning settlement facts stay None for an unfinished game.
    assert game.home_first_inning_runs is None


def test_baseball_model_learns_runs_and_first_inning_idempotently():
    model = BaseballRunModel()
    assert model.update(_mlb_game("post", 4, 7)) is True
    assert model.update(_mlb_game("post", 4, 7)) is False
    prediction = model.predict(_mlb_game())
    assert prediction.expected_total_runs > 0
    assert 0 < prediction.yrfi_probability < 1
    assert prediction.pitchers_available is True
    assert poisson_over_probability(10.0, 8.5) > 0.5


def test_baseball_signal_emits_isolated_winner_total_and_yrfi_challengers(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    client._cache[("mlb", "20260710")] = [_mlb_game()]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    markets = [
        _market("KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?"),
        _market("KXMLBTOTAL-26JUL102005HOUTEX-9", "Houston vs Texas Total Runs?", floor_strike=8.5),
        _market("KXMLBRFI-26JUL102005HOUTEX", "Houston vs Texas First Inning Run?"),
    ]
    signals = [source.generate(market) for market in markets]
    assert [signal.source for signal in signals] == [
        "mlb_structural_winner", "mlb_total_runs", "mlb_first_inning_run",
    ]
    assert all(signal.features["challenger_only"] is True for signal in signals)
    assert all(signal.features["promotion_eligible"] is False for signal in signals)


def test_kxmlbspread_parses_to_a_run_spread_contract():
    parsed = parse_sports_contract(_market(
        "KXMLBSPREAD-26JUL102005HOUTEX-TEX2", "Texas wins by over 1.5 runs?",
        floor_strike=1.5, strike_type="greater",
    ))
    assert parsed is not None
    assert parsed.sport == "mlb"
    assert parsed.market_type == "spread"
    assert parsed.subject == canonical_team("mlb", "TEX")
    assert parsed.threshold == 1.5


def test_poisson_spread_probability_is_monotone_and_bounded():
    from autonomy.sports.baseball import poisson_spread_probability
    # Strictly decreasing in the margin line for a fixed matchup.
    p_neg = poisson_spread_probability(4.8, 4.2, -1.5)   # win by over -1.5 (i.e. lose by <1.5)
    p_half = poisson_spread_probability(4.8, 4.2, 0.5)   # win outright by 1+
    p_one = poisson_spread_probability(4.8, 4.2, 1.5)    # win by 2+
    p_big = poisson_spread_probability(4.8, 4.2, 6.5)    # win by 7+
    assert p_neg > p_half > p_one > p_big
    assert all(0.005 <= p <= 0.995 for p in (p_neg, p_half, p_one, p_big))
    # A bigger favorite covers a given line more often than a coin-flip matchup.
    assert poisson_spread_probability(6.0, 3.0, 1.5) > poisson_spread_probability(4.5, 4.5, 1.5)
    # Pin the exact need=floor(margin)+1 mapping around zero via tie mass: for an
    # even matchup, P(win by >-0.5) counts wins+ties (need=0) and sits ABOVE 0.5,
    # while P(win by >0.5) is the strict win (need=1) and sits BELOW 0.5. An
    # off-by-one in `need` (floor(margin) or +2) breaks this.
    even_ge0 = poisson_spread_probability(4.5, 4.5, -0.5)  # need=0 -> win or tie
    even_gt0 = poisson_spread_probability(4.5, 4.5, 0.5)   # need=1 -> strict win
    assert even_gt0 < 0.5 < even_ge0
    assert even_ge0 - even_gt0 > 0.02  # the regulation tie mass, a real gap


def test_live_win_probability_reduces_to_pregame_at_start():
    from autonomy.sports.baseball import (
        poisson_live_win_probability, poisson_win_probability,
    )
    # Full-game means, no lead -> identical to the pre-game moneyline.
    live = poisson_live_win_probability(4.8, 4.2, 0)
    pre = poisson_win_probability(4.8, 4.2)
    assert abs(live - pre) < 1e-9


def test_live_win_probability_reflects_lead_and_time():
    from autonomy.sports.baseball import poisson_live_win_probability
    # A big lead with almost no baseball left -> near-certain.
    assert poisson_live_win_probability(0.5, 0.5, 4) > 0.98
    # Trailing by three with little left -> near-hopeless.
    assert poisson_live_win_probability(0.5, 0.5, -3) < 0.05
    # Monotonic in the lead for a fixed remaining-run environment.
    probs = [poisson_live_win_probability(2.4, 2.4, lead) for lead in (-3, -1, 0, 1, 3)]
    assert probs == sorted(probs)
    assert all(0.0005 <= p <= 0.9995 for p in probs)


def test_model_live_win_probability_matches_pregame_at_first_pitch(tmp_path):
    model = BaseballRunModel()
    game = _mlb_game()  # 0-0, pre-game
    prediction = model.predict(game)
    live_start = model.live_win_probability(prediction, 0, 0, remaining_innings=9)
    assert abs(live_start - prediction.home_win_probability) < 1e-9
    # Same game, home up 3 with 2 innings left -> well above the pre-game number.
    ahead = model.live_win_probability(prediction, 5, 2, remaining_innings=2)
    assert ahead > prediction.home_win_probability
    assert ahead > 0.8


def test_baseball_spread_probability_sides_are_coherent(tmp_path):
    model = BaseballRunModel()
    game = _mlb_game()  # home TEX, away HOU
    prediction = model.predict(game)
    home_cover = model.spread_probability(prediction, subject_is_home=True, margin=1.5)
    away_cover = model.spread_probability(prediction, subject_is_home=False, margin=1.5)
    # Both are valid probabilities and cannot both exceed 0.5 (only one side can
    # win by 2+ in a game); the stronger expected side covers more often.
    assert 0.005 <= home_cover <= 0.995 and 0.005 <= away_cover <= 0.995
    stronger_home = prediction.expected_home_runs >= prediction.expected_away_runs
    assert (home_cover >= away_cover) == stronger_home


def test_baseball_signal_emits_run_spread_challenger(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    client._cache[("mlb", "20260710")] = [_mlb_game()]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    home_spread = source.generate(_market(
        "KXMLBSPREAD-26JUL102005HOUTEX-TEX2", "Texas wins by over 1.5 runs?",
        floor_strike=1.5, strike_type="greater"))
    away_spread = source.generate(_market(
        "KXMLBSPREAD-26JUL102005HOUTEX-HOU2", "Houston wins by over 1.5 runs?",
        floor_strike=1.5, strike_type="greater"))
    assert home_spread.source == "mlb_run_spread"
    assert away_spread.source == "mlb_run_spread"
    assert home_spread.features["challenger_only"] is True
    assert home_spread.features["promotion_eligible"] is False
    assert home_spread.features["market_type"] == "spread"
    assert 0.005 <= home_spread.probability_yes <= 0.995
    # The away pitcher (2.5 ERA) is far better than the home pitcher (5.2), so the
    # away side is expected stronger and covers the same +1.5 line more often.
    assert away_spread.probability_yes > home_spread.probability_yes
    # Only one side can win by 2+, so the two YES probabilities cannot sum above 1.
    assert home_spread.probability_yes + away_spread.probability_yes <= 1.0


def test_remaining_innings_helper():
    from autonomy.sports.baseball import remaining_innings
    assert remaining_innings(1) == 9.0
    assert remaining_innings(9) == 1.0
    assert remaining_innings(5) == 5.0
    assert remaining_innings(11) == 0.5   # extras keep a small residual
    assert remaining_innings(None) == 9.0


def test_live_winner_signal_reprices_an_in_progress_game(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    # Home (TEX) up 5-2 in the 7th inning.
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=7)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    sig = source.generate(_market("KXMLBGAME-26JUL102005HOUTEX-TEX", "Houston vs Texas Winner?"))
    assert sig is not None
    assert sig.source == "mlb_live_winner"
    assert sig.features["live"] is True
    assert sig.features["current_period"] == 7
    # Leading late -> strong live win probability for TEX (the subject).
    assert sig.probability_yes > 0.85
    assert sig.features["challenger_only"] is True


def test_live_winner_away_subject_is_inverted(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    # Home (TEX) up 5-2 in the 7th -> the AWAY subject (HOU) should be the
    # complement and well below 0.5.
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=7)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    home_sig = source.generate(_market("KXMLBGAME-26JUL102005HOUTEX-TEX", "Winner?"))
    away_sig = source.generate(_market("KXMLBGAME-26JUL102005HOUTEX-HOU", "Winner?"))
    assert away_sig.source == "mlb_live_winner"
    assert away_sig.probability_yes < 0.15
    assert abs((home_sig.probability_yes + away_sig.probability_yes) - 1.0) < 1e-9


def test_live_winner_abstains_on_invalid_period(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=0)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    assert source.generate(_market("KXMLBGAME-26JUL102005HOUTEX-TEX", "Winner?")) is None


def test_live_winner_fails_closed_without_live_state(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    # In-progress but the payload lacks the inning -> abstain, never guess.
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=None)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    assert source.generate(
        _market("KXMLBGAME-26JUL102005HOUTEX-TEX", "Winner?")) is None


def test_live_game_abstains_on_non_winner_markets(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=7)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    # Totals are pre-game only for now; an in-progress game abstains.
    assert source.generate(_market(
        "KXMLBTOTAL-26JUL102005HOUTEX-9", "Total Runs?", floor_strike=8.5)) is None


def _ufc_payload(state: str = "pre", decision: bool = False):
    status = {
        "period": 3 if state == "post" else 0,
        "clock": 300 if decision else 95,
        "type": {"state": state},
    }
    return {"events": [{"competitions": [{
        "id": "fight-1", "date": "2026-07-11T21:00Z",
        "type": {"abbreviation": "Flyweight"},
        "status": status,
        "format": {"regulation": {"periods": 3}},
        "details": ([{"type": {"text": "Unofficial Winner Decision"}}] if decision else []),
        "competitors": [
            {"winner": state == "post", "athlete": {"displayName": "Alessandro Costa"},
             "records": [{"type": "total", "summary": "16-5-0"}]},
            {"winner": False, "athlete": {"displayName": "Cody Durden"},
             "records": [{"type": "total", "summary": "18-10-1"}]},
        ],
    }]}]}


def test_ufc_model_links_winner_round_total_and_distance():
    final = parse_ufc_scoreboard(_ufc_payload("post", decision=True))[0]
    assert final.went_distance is True and final.elapsed_minutes == 15.0
    model = UfcModel()
    assert model.update(final)
    upcoming = parse_ufc_scoreboard(_ufc_payload("pre"))[0]
    prediction = model.predict(upcoming)
    assert 0 < prediction.fighter_a_win_probability < 1
    assert prediction.before_round_probability(2) < prediction.before_round_probability(3)
    assert 0 < prediction.distance_probability < 1


def test_ufc_signal_routes_real_contract_shapes(tmp_path):
    client = UfcEspnClient(fetch_scoreboard=lambda _dates: _ufc_payload("pre"))
    source = UfcIntelligenceSignal(
        espn=client, model=UfcModel(), model_path=tmp_path / "ufc.json",
    )
    markets = [
        _market("KXUFCFIGHT-26JUL11COSDUR-COS", "Will Alessandro Costa win?",
                yes_sub_title="Alessandro Costa"),
        _market("KXUFCROUNDS-26JUL11COSDUR-3", "Will the Fight end before round 3?"),
        _market("KXUFCDISTANCE-26JUL11COSDUR-DIST", "Will the fight go the distance?"),
    ]
    signals = [source.generate(market) for market in markets]
    assert [signal.source for signal in signals] == [
        "ufc_fight_winner", "ufc_round_total", "ufc_fight_distance",
    ]
    assert all(signal.features["challenger_only"] for signal in signals)


def test_team_score_models_are_league_isolated_and_parse_college_markets(tmp_path):
    model = TeamScoreModel("ncaaf")
    game = Game(
        "c1", "ncaaf", "TEX", "OU", "post", True, "2026-10-01T00:00Z",
        home_score=35, away_score=21, home_name="Texas Longhorns", away_name="Oklahoma Sooners",
    )
    assert model.update(game)
    upcoming = Game(
        "c2", "ncaaf", "TEX", "OU", "pre", None, "2026-10-08T00:00Z",
        home_name="Texas Longhorns", away_name="Oklahoma Sooners",
    )
    prediction = model.predict(upcoming)
    assert prediction.league == "ncaaf" and prediction.expected_total > 0
    total_market = _market(
        "KXNCAAFTOTAL-26OCT08TEXOU-55", "Texas Longhorns vs Oklahoma Sooners Total Points",
        floor_strike=54.5,
    )
    parsed = parse_sports_contract(total_market)
    assert parsed.sport == "ncaaf" and parsed.market_type == "total"

    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    client._cache[("ncaaf", "20261008")] = [upcoming]
    models = {league: TeamScoreModel(league) for league in ("nba", "ncaamb", "nfl", "ncaaf", "nhl")}
    models["ncaaf"] = model
    source = TeamSportsIntelligenceSignal(espn=client, models=models, model_dir=tmp_path)
    signal = source.generate(total_market)
    assert signal is not None and signal.source == "ncaaf_game_total"


def _f1_payload(state: str):
    return {"events": [{
        "id": "bel-2026", "name": "Belgian Grand Prix", "date": "2026-07-26T13:00Z",
        "competitions": [{
            "id": "race-1", "date": "2026-07-26T13:00Z",
            "type": {"abbreviation": "Race"}, "status": {"type": {"state": state}},
            "competitors": [
                {"order": 1, "winner": state == "post", "athlete": {"displayName": "Max Verstappen"}},
                {"order": 2, "winner": False, "athlete": {"displayName": "Oscar Piastri"}},
                {"order": 3, "winner": False, "athlete": {"displayName": "George Russell"}},
                {"order": 4, "winner": False, "athlete": {"displayName": "Lando Norris"}},
                {"order": 5, "winner": False, "athlete": {"displayName": "Charles Leclerc"}},
            ],
        }],
    }]}


def test_formula_one_model_normalizes_one_race_winner_distribution():
    final = parse_f1_scoreboard(_f1_payload("post"))[0]
    model = F1Model()
    assert model.update(final)
    upcoming = parse_f1_scoreboard(_f1_payload("pre"))[0]
    prediction = model.predict(upcoming)
    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)
    assert prediction.probabilities["max verstappen"] > prediction.probabilities["charles leclerc"]


def _observation(index: int, probability: float = 0.75, result: bool | None = True):
    return SportsObservation(
        observation_id=f"o{index}", cycle_id="c", ticker=f"T{index}",
        event_cluster=f"E{index}", sport="mlb", market_type="winner", source="model",
        model_probability=probability, uncertainty=0.08, market_probability=0.5,
        yes_ask=51, no_ask=51, observed_at=f"2026-01-{index % 28 + 1:02d}T00:00:00Z",
        event_start=f"2026-02-{index % 28 + 1:02d}T00:00:00Z", sample_size=20,
        result_yes=result,
    )


def test_simulator_is_deterministic_and_genomes_are_bounded():
    first = SportsMonteCarloSimulator.simulate(0.7, 0.10, scenarios=1000, seed=9)
    second = SportsMonteCarloSimulator.simulate(0.7, 0.10, scenarios=1000, seed=9)
    assert first == second
    assert first.lower_95 < first.upper_95
    for genome in mutate_population(SportsGenome(), population=20, seed=4):
        assert 0.60 <= genome.probability_temperature <= 1.6
        assert 0 <= genome.market_blend <= 0.75
        assert 55 <= genome.maximum_entry_price <= 90


def test_game_engine_arenas_and_skill_tree_are_evidence_gated():
    arenas = SportsMonteCarloSimulator.simulate_arena(
        0.70, 0.10, scenarios=300, seed=13,
    )
    assert set(arenas["arenas"]) == {
        "REGULATION", "FOG_OF_WAR", "META_SHIFT", "BOSS_CHAOS",
    }
    assert arenas["deterministic_replay"] is True
    assert curriculum_stage(10, 5) == "ROOKIE"
    assert curriculum_stage(50, 25) == "VETERAN"
    assert curriculum_stage(120, 50) == "ELITE"
    assert curriculum_stage(300, 100) == "BOSS"
    assert "minimum_edge" not in unlocked_mutations("VETERAN")
    assert "minimum_edge" in unlocked_mutations("ELITE")


def test_cold_participant_history_blocks_even_a_large_apparent_edge():
    cold = _observation(99)
    cold = SportsObservation(**{**cold.__dict__, "sample_size": 0})
    decision = paper_action(cold, SportsGenome())
    assert decision["eligible"] is False
    assert decision["blocker"] == "insufficient participant history"


def test_forced_coverage_action_trades_but_never_counts_toward_promotion():
    cold = SportsObservation(**{**_observation(99).__dict__, "sample_size": 0})

    decision = forced_coverage_action(cold, SportsGenome())
    explanation = paper_decision_explanation(
        cold, decision, "cold model rationale", lane=FORCED_COVERAGE_LANE,
    )

    assert decision["action"].startswith("PAPER_FORCE_")
    assert decision["policy_eligible"] is False
    assert decision["forced"] is True
    assert decision["counts_toward_promotion"] is False
    assert "insufficient participant history" in decision["coverage_reason"]
    assert "Excluded from promotion" in explanation


def test_designated_sports_types_are_complete_and_tennis_remains_excluded():
    scopes = set(DESIGNATED_SPORTS_PREDICTION_TYPES)
    assert scopes == {
        ("mlb", "winner"), ("mlb", "total_runs"), ("mlb", "yrfi"),
        ("nba", "winner"), ("nba", "total"),
        ("nfl", "winner"), ("nfl", "total"),
        ("ncaaf", "winner"), ("ncaaf", "total"),
        ("nhl", "winner"), ("nhl", "total"),
        ("ncaamb", "winner"), ("ncaamb", "total"),
        ("ufc", "winner"), ("ufc", "before_round"), ("ufc", "distance"),
        ("f1", "winner"),
    }
    assert all(sport != "tennis" for sport, _market_type in scopes)


def test_nfl_winner_remains_explicit_gap_even_with_listed_paper_markets():
    assessment = sports_coverage_assessment("nfl", "winner", 58)

    assert assessment["status"] == "TRACKING_FORCED_PAPER_COVERAGE_GAP"
    assert assessment["is_coverage_gap"] is True
    assert "58 real listed" in assessment["explanation"]
    assert "forced paper capture alone do not close" in assessment["coverage_gap_reason"]


def test_normal_observed_scope_is_not_a_coverage_gap():
    assessment = sports_coverage_assessment("mlb", "yrfi", 18)

    assert assessment["status"] == "TRACKING_FORCED_PAPER"
    assert assessment["is_coverage_gap"] is False
    assert assessment["coverage_gap_reason"] is None


def test_walk_forward_never_splits_an_event_cluster():
    rows = [_observation(index) for index in range(30)]
    for train, test in chronological_folds(rows, folds=4):
        assert {row.event_cluster for row in train}.isdisjoint(
            {row.event_cluster for row in test}
        )


def test_recursive_lab_is_fail_closed_without_forward_evidence(tmp_path):
    lab = RecursiveSportsLab(tmp_path / "champions.json", tmp_path / "history.jsonl")
    report = lab.run([_observation(index) for index in range(10)], seed=3)
    scope = report["scopes"]["mlb:winner"]
    assert scope["status"] == "INSUFFICIENT_FORWARD_EVIDENCE"
    assert report["execution_authority"] is False
    assert report["recursive_code_rewrite"] is False


def test_paired_cluster_bootstrap_detects_consistent_brier_improvement():
    champion = {"cluster_brier": {f"E{i}": 0.25 for i in range(25)}}
    candidate = {"cluster_brier": {f"E{i}": 0.15 for i in range(25)}}
    result = paired_cluster_bootstrap(champion, candidate, samples=500, seed=2)
    assert result["lower_95"] > 0


def test_evidence_ledger_keeps_earliest_point_in_time_row(tmp_path):
    ledger = SportsEvidenceLedger(tmp_path / "sports.db")
    try:
        market = _market("KXMLBRFI-26JUL102005HOUTEX", "First inning run?")
        signal = Signal(
            "mlb_first_inning_run", market.ticker, 0.60, 0.12, "reason",
            {"event_start": "2026-07-10T20:05:00Z", "challenger_only": True},
            created_at="2026-07-10T10:00:00Z",
        )
        assert ledger.record("c1", market, signal, "mlb", "yrfi") is not None
        later = Signal(
            signal.source, signal.market_ticker, 0.65, signal.uncertainty, "later",
            signal.features, created_at="2026-07-10T11:00:00Z",
        )
        ledger.record("c2", market, later, "mlb", "yrfi")
        rows = ledger.rows()
        assert len(rows) == 1 and rows[0].model_probability == 0.60
    finally:
        ledger.close()


def test_sports_paper_ledger_freezes_lanes_and_settles_pnl(tmp_path):
    ledger = SportsEvidenceLedger(tmp_path / "sports.db")
    observation = _observation(7, probability=0.75, result=None)
    policy = paper_action(observation, SportsGenome())
    forced = forced_coverage_action(observation, SportsGenome())
    try:
        assert policy["eligible"] is True
        assert ledger.record_paper_decision(
            observation,
            policy,
            paper_decision_explanation(
                observation, policy, "policy rationale", lane=POLICY_LANE,
            ),
            lane=POLICY_LANE,
        ) is True
        assert ledger.record_paper_decision(
            observation,
            forced,
            paper_decision_explanation(
                observation, forced, "coverage rationale", lane=FORCED_COVERAGE_LANE,
            ),
            lane=FORCED_COVERAGE_LANE,
        ) is True
        assert ledger.record_paper_decision(
            observation, forced, "later rewrite", lane=FORCED_COVERAGE_LANE,
        ) is False

        assert ledger.settle_paper_decisions(observation.ticker, True) == 2
        summary = ledger.paper_decision_summary()
        rows = ledger.recent_paper_decisions(status="SETTLED")

        assert summary["decisions"] == 2
        assert summary["settled_decisions"] == 2
        assert summary["wins"] == 2
        assert summary["net_pnl_cents"] > 0
        assert summary["forced_coverage_counts_toward_promotion"] is False
        assert {row["lane"] for row in rows} == {POLICY_LANE, FORCED_COVERAGE_LANE}
        assert all(row["counts_toward_promotion"] == (row["lane"] == POLICY_LANE) for row in rows)
    finally:
        ledger.close()


def test_challenger_only_signals_cannot_enter_execution_forecast():
    class Ledger:
        def get_weight(self, _source, default=1.0):
            return default

    market = _market("KXMLBRFI-26JUL102005HOUTEX", "First inning run?")
    challenger = Signal(
        "mlb_first_inning_run", market.ticker, 0.90, 0.05, "",
        {"challenger_only": True},
    )
    assert EnsembleForecaster(Ledger()).fuse(market, [challenger]) is None


def test_simulation_metrics_use_settled_outcomes_only():
    rows = [
        _observation(1, probability=0.8, result=True),
        _observation(2, probability=0.2, result=False),
        _observation(3, result=None),
    ]
    result = evaluate_genome(rows, SportsGenome())
    assert result["observations"] == 2
    assert 0 <= result["ece"] <= 1
    assert 0 <= result["mce"] <= 1
    assert result["auc"] == 1.0
    assert result["sharpness"] > 0
