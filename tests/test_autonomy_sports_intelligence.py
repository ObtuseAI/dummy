"""MLB/all-sport intelligence and recursive simulation invariants."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


from autonomy.forecaster import EnsembleForecaster
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.scanner import WATCHLIST_SERIES, classify_vertical
from autonomy.signals.sports_intelligence import (
    BaseballIntelligenceSignal,
    PowerRatingsSignal,
    TeamSportsIntelligenceSignal,
    parse_sports_contract,
)
from autonomy.sports.baseball import BaseballRunModel, poisson_over_probability
from autonomy.sports.espn import EspnClient, Game, canonical_team, parse_scoreboard
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
        "KXNCAAMBGAME", "KXNCAAMBTOTAL",
    }
    assert required <= set(WATCHLIST_SERIES)
    # UFC and Formula One retired 2026-07-12: no longer scanned, classified,
    # or parsed as sports contracts.
    retired = {"KXUFCFIGHT", "KXUFCROUNDS", "KXUFCDISTANCE", "KXF1RACE"}
    assert not retired & set(WATCHLIST_SERIES)
    assert classify_vertical("KXF1RACE-BELGP26-VER") is Vertical.OTHER
    assert classify_vertical("KXUFCFIGHT-26JUL11COSDUR-COS") is Vertical.OTHER
    assert parse_sports_contract(_market(
        "KXUFCFIGHT-26JUL11COSDUR-COS", "Will Alessandro Costa win?")) is None
    assert parse_sports_contract(_market(
        "KXF1RACE-BELGP26-VER", "Belgian Grand Prix winner?")) is None
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
    assert all(signal.features["promotion_eligible"] is True for signal in signals)


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
    assert home_spread.features["promotion_eligible"] is True
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


def test_live_total_and_spread_reduce_to_pregame_at_start(tmp_path):
    model = BaseballRunModel()
    prediction = model.predict(_mlb_game())
    # At 0-0 with 9 innings left, live == pre-game for totals and spreads.
    assert abs(
        model.live_total_probability(prediction, 0, 8.5, 9)
        - model.total_probability(prediction, 8.5)
    ) < 1e-9
    assert abs(
        model.live_spread_probability(prediction, True, 1.5, 0, 0, 9)
        - model.spread_probability(prediction, subject_is_home=True, margin=1.5)
    ) < 1e-9


def test_live_total_counts_runs_already_scored(tmp_path):
    model = BaseballRunModel()
    prediction = model.predict(_mlb_game())
    # 9 runs already in past an 8.5 line -> over is already decided (~certain).
    assert model.live_total_probability(prediction, 9, 8.5, 2) > 0.95
    # A quiet 1-run game late -> the 8.5 over is nearly dead.
    assert model.live_total_probability(prediction, 1, 8.5, 2) < 0.1


def test_live_signal_prices_live_total_and_spread(tmp_path):
    from autonomy.live_odds import EspnSummaryBook

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=6, away_score=3, current_period=8)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
        # Hermetic stub -- no plays -> base_out_state is None, a no-op; this
        # test only cares about the live total/spread pricing baseline, and
        # must not make a real network call.
        live_book=EspnSummaryBook(league="mlb", fetch_summary=lambda _league, _event: {}),
    )
    total = source.generate(_market(
        "KXMLBTOTAL-26JUL102005HOUTEX-9", "Total Runs?", floor_strike=8.5))
    spread = source.generate(_market(
        "KXMLBSPREAD-26JUL102005HOUTEX-TEX2", "Texas by 1.5?",
        floor_strike=1.5, strike_type="greater"))
    assert total.source == "mlb_live_total" and total.features["live"] is True
    assert total.probability_yes > 0.5      # 9 already scored, over 8.5 likely
    assert spread.source == "mlb_live_spread"
    assert spread.probability_yes > 0.5     # TEX (home) up 3, covering +1.5 likely


def test_statsapi_pa_simulator_registers_as_separately_graded_live_source(tmp_path):
    from dataclasses import replace

    from autonomy.live_odds import EspnSummaryBook
    from autonomy.sports.statsapi import (
        BatterRates, LineupSlot, MlbGameContext, PitcherRates,
    )

    lineup_home = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    lineup_away = tuple(LineupSlot(i + 1, 200 + i, bats="L") for i in range(9))
    batter_rates = {
        slot.player_id: BatterRates(
            player_id=slot.player_id, bats=slot.bats, plate_appearances=500,
            k_pct=0.20, bb_pct=0.09, obp=0.34, slg=0.45, iso=0.18,
        )
        for slot in (*lineup_home, *lineup_away)
    }
    context = MlbGameContext(
        game_pk=999, snapshot="projected", captured_at=NOW.isoformat(),
        home="TEX", away="HOU",
        home_pitcher=PitcherRates(1, throws="R", k_pct=0.24, bb_pct=0.07, hr9=1.0),
        away_pitcher=PitcherRates(2, throws="L", k_pct=0.25, bb_pct=0.08, hr9=1.1),
        home_lineup=lineup_home, away_lineup=lineup_away,
        batter_rates=batter_rates, park_run_factor=1.0, park_hr_factor=1.0,
    )

    class StubStatsApi:
        def __init__(self):
            self.context_calls = 0

        def projected_context_for_matchup(self, date_iso, **kwargs):
            self.context_calls += 1
            assert date_iso == "2026-07-10"
            assert kwargs["home"] == "TEX" and kwargs["away"] == "HOU"
            return context

        def confirm_lineups(self, ctx, *, captured_at):
            return replace(ctx, snapshot="confirmed", captured_at=captured_at)

        def hydrate_batter_rates(self, ctx):
            return ctx

        def clear_schedule_cache(self):
            pass

    simulator_calls = []

    def fake_simulator(ctx, **kwargs):
        simulator_calls.append(kwargs)
        assert ctx.snapshot == "confirmed"
        assert kwargs["divisional"] is True
        assert kwargs["rivalry"] is True
        return {
            "home_win": 0.68, "yrfi": 0.52,
            "expected_home_runs": 5.4, "expected_away_runs": 3.6,
        }

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=7)
    ]
    statsapi = StubStatsApi()
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
        live_book=EspnSummaryBook(league="mlb", fetch_summary=lambda _l, _e: {}),
        statsapi=statsapi, pa_simulator=fake_simulator, pa_sims=200,
    )
    markets = (
        _market("KXMLBGAME-26JUL102005HOUTEX-TEX", "Winner?"),
        _market("KXMLBTOTAL-26JUL102005HOUTEX-9", "Total?", floor_strike=8.5),
        _market(
            "KXMLBSPREAD-26JUL102005HOUTEX-TEX2", "Texas by 1.5?",
            floor_strike=1.5,
        ),
    )
    signals = [source.generate(market) for market in markets]
    assert [signal.source for signal in signals] == [
        "mlb_pa_live_winner", "mlb_pa_live_total", "mlb_pa_live_spread",
    ]
    assert len(simulator_calls) == 1 and statsapi.context_calls == 1
    for signal in signals:
        assert signal.features["model_version"] == "mlb_pa_sim_live_v1"
        assert signal.features["pa_simulator"]["game_pk"] == 999
        assert signal.features["pa_simulator"]["batter_rate_coverage"] == 1.0
        assert signal.features["challenger_only"] is True
        assert signal.features["promotion_eligible"] is True


def test_statsapi_pa_failure_falls_back_to_incumbent_live_source(tmp_path):
    class EmptyStatsApi:
        def projected_context_for_matchup(self, *args, **kwargs):
            return None

        def clear_schedule_cache(self):
            pass

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=7)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
        statsapi=EmptyStatsApi(), pa_simulator=lambda *_a, **_k: {},
    )
    signal = source.generate(_market(
        "KXMLBGAME-26JUL102005HOUTEX-TEX", "Winner?",
    ))
    assert signal.source == "mlb_live_winner"
    assert signal.features["pa_simulator"] is None


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


def test_injuries_widen_uncertainty_without_shifting_the_mean(tmp_path):
    from autonomy.sports.injuries import InjuryBook
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [_mlb_game()]  # home TEX, away HOU
    hurt_payload = {"injuries": [
        {"displayName": "Texas Rangers",
         "injuries": [{"status": "Out"}, {"status": "Day-To-Day"}, {"status": "Out"}]},
        {"displayName": "Houston Astros", "injuries": [{"status": "Day-To-Day"}]},
    ]}
    healthy = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "a.json",
        injuries=InjuryBook(fetch_fn=lambda: {"injuries": []}))
    hurt = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "b.json",
        injuries=InjuryBook(fetch_fn=lambda: hurt_payload))
    healthy.injuries.refresh()
    hurt.injuries.refresh()
    market = _market("KXMLBGAME-26JUL102005HOUTEX-TEX", "Winner?")
    clean = healthy.generate(market)
    banged = hurt.generate(market)
    assert banged.uncertainty > clean.uncertainty          # widened
    assert banged.features["injury_burden"] > 0
    assert clean.features["injury_burden"] == 0
    assert abs(banged.probability_yes - clean.probability_yes) < 1e-9  # mean unchanged


def test_live_game_abstains_on_yrfi(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=5, away_score=2, current_period=7)
    ]
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
    )
    # YRFI is a first-inning market; an in-progress game abstains (winner,
    # total, and spread are re-priced live, but YRFI is meaningless once underway).
    assert source.generate(_market(
        "KXMLBRFI-26JUL102005HOUTEX", "First Inning Run?")) is None


def test_park_factor_scales_total_and_yrfi_but_not_winner_margin(tmp_path):
    from autonomy.sports.baseball import poisson_win_probability

    model = BaseballRunModel()
    game = Game(
        game_id="gcol", league="mlb", home="COL", away="SD", status="pre",
        home_won=None, date="2026-07-10T20:05:00Z",
        home_pitcher_era=4.0, away_pitcher_era=4.0,
    )
    prediction = model.predict(game)
    # Winner is priced off the UNSCALED per-team means -- park factor never
    # touches expected_home_runs/expected_away_runs (winner margin unaffected).
    assert prediction.home_win_probability == poisson_win_probability(
        prediction.expected_home_runs, prediction.expected_away_runs)
    assert prediction.park_factor == 1.28
    # expected_total_runs is the ONLY thing scaled, and by exactly the factor.
    assert abs(
        prediction.expected_total_runs
        - (prediction.expected_home_runs + prediction.expected_away_runs) * 1.28
    ) < 1e-9


def test_park_factor_scales_yrfi_upward_for_a_hitters_park(tmp_path):
    # Two cold-start models differing ONLY in home team code (identical
    # priors otherwise) isolate the park-factor effect on YRFI.
    col_pred = BaseballRunModel().predict(Game(
        game_id="g1", league="mlb", home="COL", away="SD", status="pre",
        home_won=None, date="2026-07-10T20:05:00Z",
    ))
    neutral_pred = BaseballRunModel().predict(Game(
        game_id="g2", league="mlb", home="ATL", away="SD", status="pre",
        home_won=None, date="2026-07-10T20:05:00Z",
    ))
    assert col_pred.yrfi_probability > neutral_pred.yrfi_probability


def test_park_factor_absent_for_unknown_team_is_byte_identical_total(tmp_path):
    prediction = BaseballRunModel().predict(Game(
        game_id="g3", league="mlb", home="ZZZ", away="SD", status="pre",
        home_won=None, date="2026-07-10T20:05:00Z",
    ))
    assert prediction.park_factor == 1.0
    assert prediction.expected_total_runs == (
        prediction.expected_home_runs + prediction.expected_away_runs
    )


def test_re24_table_hand_checked_anchors():
    from autonomy.sports.baseball import RE24_TABLE
    # WS-11 brief anchors: bases loaded/0 outs ~2.3, empty/2 outs ~0.10.
    assert abs(RE24_TABLE[("loaded", 0)] - 2.3) < 0.05
    assert abs(RE24_TABLE[("empty", 2)] - 0.10) < 0.05
    # Monotone in the expected directions.
    assert RE24_TABLE[("empty", 0)] > RE24_TABLE[("empty", 1)] > RE24_TABLE[("empty", 2)]
    assert RE24_TABLE[("loaded", 0)] > RE24_TABLE[("2nd_3rd", 0)] > RE24_TABLE[("empty", 0)]


def test_base_state_key_maps_runner_flags():
    from autonomy.sports.baseball import base_state_key
    assert base_state_key(False, False, False) == "empty"
    assert base_state_key(True, False, False) == "1st"
    assert base_state_key(False, True, False) == "2nd"
    assert base_state_key(False, False, True) == "3rd"
    assert base_state_key(True, True, False) == "1st_2nd"
    assert base_state_key(True, False, True) == "1st_3rd"
    assert base_state_key(False, True, True) == "2nd_3rd"
    assert base_state_key(True, True, True) == "loaded"


def test_base_out_delta_fail_closed_and_directional():
    from autonomy.sports.baseball import base_out_delta
    assert base_out_delta(None, None) == 0.0
    assert base_out_delta("loaded", None) == 0.0
    assert base_out_delta("bogus", 0) == 0.0
    assert base_out_delta("empty", 3) == 0.0  # outs=3 not in the 8x3 table
    assert base_out_delta("loaded", 0) > 0.0   # raises the remaining mean
    assert base_out_delta("empty", 2) < 0.0    # lowers the remaining mean


def test_live_total_probability_no_live_state_is_byte_identical_to_old_signature(tmp_path):
    model = BaseballRunModel()
    prediction = model.predict(_mlb_game())
    old_style = model.live_total_probability(prediction, 3, 8.5, 4)
    new_style = model.live_total_probability(
        prediction, 3, 8.5, 4, base_state=None, outs=None, current_period=None)
    assert old_style == new_style


def test_live_total_probability_bases_loaded_no_outs_raises_over_probability(tmp_path):
    model = BaseballRunModel()
    prediction = model.predict(_mlb_game())
    baseline = model.live_total_probability(prediction, 4, 8.5, 3)
    loaded = model.live_total_probability(prediction, 4, 8.5, 3, base_state="loaded", outs=0)
    empty2 = model.live_total_probability(prediction, 4, 8.5, 3, base_state="empty", outs=2)
    assert loaded > baseline > empty2


def test_tto_fatigue_multiplier_windows():
    from autonomy.sports.baseball import tto_fatigue_multiplier
    assert tto_fatigue_multiplier(None) == 1.0
    assert tto_fatigue_multiplier(1) == 1.0
    assert tto_fatigue_multiplier(4) == 1.0
    assert tto_fatigue_multiplier(5) == 1.12
    assert tto_fatigue_multiplier(6) == 1.12
    assert tto_fatigue_multiplier(7) == 1.0
    assert tto_fatigue_multiplier(9) == 1.0


def test_live_total_probability_tto_window_raises_over_probability(tmp_path):
    model = BaseballRunModel()
    prediction = model.predict(_mlb_game())
    inning4 = model.live_total_probability(prediction, 4, 8.5, 5, current_period=4)
    inning5 = model.live_total_probability(prediction, 4, 8.5, 5, current_period=5)
    assert inning5 > inning4


def test_rest_travel_uncertainty_bump_pure_function():
    from autonomy.sports.baseball import rest_travel_uncertainty_bump
    # Day game (UTC 17:05 ~ ET 13:05) after a previous night game (UTC 23:35
    # prior day ~ ET 19:35) -> soft bump.
    assert rest_travel_uncertainty_bump("2026-07-11T17:05Z", "2026-07-10T23:35Z") == 0.02
    # Both day games -> no bump.
    assert rest_travel_uncertainty_bump("2026-07-11T17:05Z", "2026-07-10T17:05Z") == 0.0
    # Missing data -> no-op.
    assert rest_travel_uncertainty_bump(None, "2026-07-10T23:35Z") == 0.0
    assert rest_travel_uncertainty_bump("2026-07-11T17:05Z", None) == 0.0


def test_live_total_signal_includes_park_factor_and_base_out_features(tmp_path):
    from autonomy.live_odds import EspnSummaryBook
    from autonomy.sports.mlb_parks import PARK_FACTORS

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=6, away_score=3, current_period=6)
    ]
    live_book = EspnSummaryBook(
        league="mlb",
        fetch_summary=lambda league, eid: {"plays": [
            {"outs": 0, "onFirst": {}, "onSecond": {}, "onThird": {}},
        ]},
    )
    source = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
        live_book=live_book,
    )
    sig = source.generate(_market(
        "KXMLBTOTAL-26JUL102005HOUTEX-9", "Total Runs?", floor_strike=8.5))
    assert sig is not None
    assert sig.features["base_out_state"] == {"base_state": "loaded", "outs": 0}
    assert sig.features["park_factor"] == PARK_FACTORS[canonical_team("mlb", "TEX")]


def test_live_total_signal_base_out_absent_is_byte_identical(tmp_path):
    from autonomy.live_odds import EspnSummaryBook

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("mlb", "20260710")] = [
        _mlb_game(status="in", home_score=6, away_score=3, current_period=8)
    ]
    empty_book = EspnSummaryBook(league="mlb", fetch_summary=lambda _league, _event: {})

    def boom(_l, _e):
        raise RuntimeError("espn down")

    dead_book = EspnSummaryBook(league="mlb", fetch_summary=boom)
    market = _market("KXMLBTOTAL-26JUL102005HOUTEX-9", "Total Runs?", floor_strike=8.5)
    sig_empty = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "a.json",
        live_book=empty_book,
    ).generate(market)
    sig_dead = BaseballIntelligenceSignal(
        espn=client, model=BaseballRunModel(), model_path=tmp_path / "b.json",
        live_book=dead_book,
    ).generate(market)
    assert sig_empty.probability_yes == sig_dead.probability_yes
    assert sig_empty.features["base_out_state"] is None
    assert sig_dead.features["base_out_state"] is None


def test_rest_travel_widens_uncertainty_when_previous_game_was_a_night_game(tmp_path):
    from dataclasses import replace

    from autonomy.signals.sports_intelligence import _date_range

    day_game = replace(_mlb_game(), date="2026-07-10T17:05Z")  # TEX home, day start
    previous_night_game = Game(
        game_id="prev1", league="mlb", home="TEX", away="LAA", status="post",
        home_won=True, date="2026-07-09T23:35Z",
        home_score=5, away_score=2, home_first_inning_runs=1, away_first_inning_runs=0,
    )
    tired_client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    tired_client._cache[("mlb", "20260710")] = [day_game]
    tired_client._cache[("mlb", _date_range())] = [day_game, previous_night_game]
    tired = BaseballIntelligenceSignal(
        espn=tired_client, model=BaseballRunModel(), model_path=tmp_path / "tired.json",
    )

    rested_client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    rested_client._cache[("mlb", "20260710")] = [day_game]
    rested_client._cache[("mlb", _date_range())] = [day_game]  # no previous game found
    rested = BaseballIntelligenceSignal(
        espn=rested_client, model=BaseballRunModel(), model_path=tmp_path / "rested.json",
    )

    market = _market("KXMLBGAME-26JUL102005HOUTEX-TEX", "Winner?")
    tired_sig = tired.generate(market)
    rested_sig = rested.generate(market)
    assert tired_sig.uncertainty > rested_sig.uncertainty
    # Soft signal: direction is narrative, so the MEAN never moves.
    assert abs(tired_sig.probability_yes - rested_sig.probability_yes) < 1e-9


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
    # WS-10: TEX/OU are both in football_weather.COLLEGE_STADIUMS, so a real
    # (unmocked) TeamSportsIntelligenceSignal would otherwise attempt a live
    # Open-Meteo fetch for this total market -- keep this pre-existing test
    # hermetic with a stub that fails closed instantly (0.0 adjustment).
    source = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path,
        fetch_football_weather=lambda *_a, **_k: {},
    )
    signal = source.generate(total_market)
    assert signal is not None and signal.source == "ncaaf_game_total"


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


# ---------------------------------------------------------------------------
# WS-A2: PowerRatingsSignal -- scope/gating smoke tests (full emission math
# is covered in tests/test_autonomy_power_ratings_emit.py).
# ---------------------------------------------------------------------------


def test_power_ratings_signal_applicable_only_for_supported_leagues_and_market_types():
    signal = PowerRatingsSignal()
    # MLB has no power-ratings coverage (not in POWER_RATINGS_SUPPORTED_LEAGUES).
    assert signal.applicable(_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?",
        yes_sub_title="Houston")) is False
    # NFL totals are out of scope for this challenger (winner/spread only).
    assert signal.applicable(_market(
        "KXNFLTOTAL-26SEP132025KCBUF-45", "Kansas City Chiefs vs Buffalo Bills Total Points?",
        floor_strike=44.5)) is False
    assert signal.applicable(_market(
        "KXNFLGAME-26SEP132025KCBUF-KC", "Kansas City Chiefs vs Buffalo Bills Winner?")) is True


def test_power_ratings_challenger_signal_cannot_enter_execution_forecast():
    # The real emitted Signal (not a hand-built stand-in) must still be
    # excluded from fusion -- ties this challenger to the same global
    # challenger-only/promotion-eligible gate as every other signal here.
    class Ledger:
        def get_weight(self, _source, default=1.0):
            return default

    def _fixed_consensus(home, away, league, sources):
        from autonomy.sports.power_ratings import ConsensusMargin
        return ConsensusMargin(ensemble_margin=6.0, dispersion=1.0, n_sources=2,
                                per_source={"a": 6.0, "b": 6.0})

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    game = Game("g1", "nfl", "KC", "BUF", "pre", None, "2026-09-13T20:25Z",
                home_name="KC", away_name="BUF")
    client._cache[("nfl", "20260913")] = [game]
    models = {"nfl": TeamScoreModel("nfl"), "ncaaf": TeamScoreModel("ncaaf"),
              "nba": TeamScoreModel("nba"), "ncaamb": TeamScoreModel("ncaamb")}
    signal = PowerRatingsSignal(
        espn=client, model_dir=None, elo_dir=None,
        consensus_fn=_fixed_consensus, models=models, elo_models={},
    )
    market = _market("KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?")
    emitted = signal.generate(market)
    assert emitted is not None
    assert emitted.features["challenger_only"] is True
    assert emitted.features["promotion_eligible"] is True
    assert EnsembleForecaster(Ledger()).fuse(market, [emitted]) is None


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
