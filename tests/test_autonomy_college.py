"""WS-4: NCAAF college kernel + NCAAMB pace-model reparameterization.

Zero network: fixtures are hand-built in-memory, mirroring
tests/test_autonomy_nba_model.py / test_autonomy_nfl_margin.py's pattern.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
from autonomy.sports.boxscores import BoxscoreStore, TeamBoxscore
from autonomy.sports.college import (
    BASE_ABS_MARGIN_PMF_COLLEGE,
    NCAAF_MODEL_VERSION,
    NCAAMB_MODEL_VERSION,
    NCAAMB_PARAMS,
    NcaafCollegeModel,
    TALENT_GAP_FULL_GAMES,
    ncaaf_college,
    ncaaf_talent_gap_margin,
    parse_neutral_site,
    talent_gap_margin,
)
from autonomy.sports.elo import EloModel
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.live_team_models import (
    NCAAF_LIVE_MODEL_VERSION,
    NCAAMB_LIVE_MODEL_VERSION,
)
from autonomy.sports.nba_model import MIN_GAMES_FOR_ENGINE, NbaModel, NbaTeamState
from autonomy.sports.nfl_margin import BASE_ABS_MARGIN_PMF, margin_distribution
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel, TeamScorePrediction

NOW = datetime(2026, 1, 12, 16, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------- college PMF


def test_college_pmf_normalizes_to_one():
    dist = margin_distribution(0.0, base_pmf=BASE_ABS_MARGIN_PMF_COLLEGE)
    assert sum(dist.values()) == pytest.approx(1.0, abs=1e-9)


def test_college_pmf_key_number_spikes_are_shallower_than_nfl():
    ratio_3 = BASE_ABS_MARGIN_PMF_COLLEGE[3] / BASE_ABS_MARGIN_PMF[3]
    ratio_7 = BASE_ABS_MARGIN_PMF_COLLEGE[7] / BASE_ABS_MARGIN_PMF[7]
    assert ratio_3 < 1.0
    assert ratio_7 < 1.0
    assert ratio_3 == pytest.approx(0.6, abs=0.1)
    assert ratio_7 == pytest.approx(0.6, abs=0.1)


def test_college_pmf_mass_extends_further_than_nfl():
    assert max(BASE_ABS_MARGIN_PMF_COLLEGE) == 60
    assert max(BASE_ABS_MARGIN_PMF) == 45


# ------------------------------------------------------- talent-gap blend


def test_talent_gap_blend_at_zero_games_is_pure_elo():
    margin, weight = talent_gap_margin(ewma_margin=10.0, elo_diff=50.0, games=0)
    assert weight == 0.0
    assert margin == pytest.approx(50.0 / 25.0, abs=1e-12)


def test_talent_gap_blend_at_full_games_is_pure_ewma():
    margin, weight = talent_gap_margin(ewma_margin=10.0, elo_diff=50.0, games=int(TALENT_GAP_FULL_GAMES))
    assert weight == 1.0
    assert margin == pytest.approx(10.0, abs=1e-12)


def test_talent_gap_blend_clamps_weight_beyond_full_games():
    margin_6, weight_6 = talent_gap_margin(10.0, 50.0, 6)
    margin_20, weight_20 = talent_gap_margin(10.0, 50.0, 20)
    assert weight_6 == weight_20 == 1.0
    assert margin_6 == pytest.approx(margin_20, abs=1e-12)


def test_talent_gap_blend_is_monotone_between_zero_and_full_games():
    values = [talent_gap_margin(10.0, 2.0, games)[0] for games in range(0, 7)]
    # ewma_margin (10.0) > elo_margin_pts (2.0/25=0.08) here, so blended
    # margin should be non-decreasing as w grows toward the ewma term.
    assert values == sorted(values)
    weights = [talent_gap_margin(10.0, 2.0, games)[1] for games in range(0, 7)]
    assert weights == sorted(weights)
    assert weights[0] == 0.0
    assert weights[-1] == 1.0


# -------------------------------------------------------------- NCAAF kernel


def _ncaaf_prediction(expected_home: float, expected_away: float, sample_games: int = 10) -> TeamScorePrediction:
    config = LEAGUE_SCORE_CONFIGS["ncaaf"]
    return TeamScorePrediction(
        home_win_probability=0.5,  # unused by ncaaf_college -- it recomputes from the kernel
        expected_home_score=expected_home,
        expected_away_score=expected_away,
        expected_total=expected_home + expected_away,
        total_sigma=config.total_sigma,
        winner_uncertainty=0.15,
        total_uncertainty=0.18,
        sample_games=sample_games,
        league="ncaaf",
    )


def test_ncaaf_neutral_site_zeroes_the_home_edge():
    # expected_home/away already carry the generic model's +/-home_edge/2
    # split (mirrors what TeamScoreModel.predict actually produces).
    home_edge = LEAGUE_SCORE_CONFIGS["ncaaf"].home_edge_points
    prediction = _ncaaf_prediction(expected_home=30.0 + home_edge / 2.0, expected_away=27.0 - home_edge / 2.0)
    margin_neutral, _ = ncaaf_talent_gap_margin(prediction, home_elo=1500.0, away_elo=1500.0,
                                                 games=10, neutral_site=True)
    margin_non_neutral, _ = ncaaf_talent_gap_margin(prediction, home_elo=1500.0, away_elo=1500.0,
                                                      games=10, neutral_site=False)
    assert margin_non_neutral - margin_neutral == pytest.approx(home_edge, abs=1e-9)


def test_ncaaf_college_kernel_uses_the_college_base_pmf():
    prediction = _ncaaf_prediction(expected_home=24.0, expected_away=21.0)
    kernel, out = ncaaf_college(prediction, home_elo=1500.0, away_elo=1500.0, games=10, neutral_site=False)
    assert isinstance(kernel, NcaafCollegeModel)
    assert kernel.distribution == margin_distribution(out.expected_margin, base_pmf=BASE_ABS_MARGIN_PMF_COLLEGE)
    assert out.model_version == NCAAF_MODEL_VERSION
    assert 0.0 < out.home_win_probability < 1.0


def test_ncaaf_college_widens_uncertainty_when_leaning_on_elo():
    prediction = _ncaaf_prediction(expected_home=24.0, expected_away=21.0)
    _, cold = ncaaf_college(prediction, home_elo=1600.0, away_elo=1400.0, games=0, neutral_site=False)
    _, warm = ncaaf_college(prediction, home_elo=1600.0, away_elo=1400.0, games=10, neutral_site=False)
    assert cold.talent_gap_weight == 0.0
    assert warm.talent_gap_weight == 1.0
    # Soft state (leaning on the Elo prior) -> uncertainty widens, never
    # shrinks, and the mean (expected_margin) is untouched by this widen.
    assert cold.winner_uncertainty >= warm.winner_uncertainty
    assert cold.total_uncertainty >= warm.total_uncertainty


# ------------------------------------------------------------- NCAAMB engine


def test_ncaamb_cold_prior_total_is_sane():
    model = NbaModel(params=NCAAMB_PARAMS)
    game = Game("g1", "ncaamb", "DUKE", "UNC", "pre", None, "2026-01-12T20:00Z")
    prediction = model.predict(game)
    # 2 * prior_pace * prior_rating / 100 = 2*68*105/100 = 142.8
    assert prediction.expected_total == pytest.approx(142.8, abs=1e-9)
    assert 120.0 < prediction.expected_total < 165.0  # sane band vs total_sigma_base=17.0
    assert prediction.model_version == NCAAMB_MODEL_VERSION


def test_ncaamb_cold_start_uses_college_priors_not_nba_priors():
    model = NbaModel(params=NCAAMB_PARAMS)
    state = model._team("DUKE")
    assert state.pace_ewma == pytest.approx(68.0)
    assert state.ortg_ewma == pytest.approx(105.0)
    assert state.drtg_ewma == pytest.approx(105.0)


def test_ncaamb_neutral_site_zeroes_the_home_edge():
    model = NbaModel(params=NCAAMB_PARAMS)
    model.teams["DUKE"] = NbaTeamState(games=10, pace_ewma=70.0, ortg_ewma=112.0, drtg_ewma=100.0)
    model.teams["UNC"] = NbaTeamState(games=10, pace_ewma=69.0, ortg_ewma=108.0, drtg_ewma=103.0)
    game = Game("g1", "ncaamb", "DUKE", "UNC", "pre", None, "2026-01-12T20:00Z")
    non_neutral = model.predict(game, neutral=False)
    neutral = model.predict(game, neutral=True)
    assert non_neutral.expected_margin - neutral.expected_margin == pytest.approx(
        NCAAMB_PARAMS.home_edge_points, abs=1e-9)


def test_ncaamb_params_differ_from_nba_params():
    from autonomy.sports.nba_model import NBA_PARAMS

    assert NCAAMB_PARAMS != NBA_PARAMS
    assert NCAAMB_PARAMS.prior_pace == 68.0
    assert NCAAMB_PARAMS.prior_rating == 105.0
    assert NCAAMB_PARAMS.home_edge_points == 3.5
    assert NCAAMB_PARAMS.total_sigma_base == 17.0
    assert NCAAMB_PARAMS.margin_sigma_base == 10.5


# ----------------------------------------------------------- neutral-site probe parsing


def test_parse_neutral_site_reads_the_espn_flag():
    payload = {
        "events": [
            {"id": "401752923", "competitions": [{"neutralSite": True}]},
            {"id": "401752921", "competitions": [{"neutralSite": False}]},
            {"id": "no_competitions", "competitions": []},
        ],
    }
    parsed = parse_neutral_site(payload)
    assert parsed["401752923"] is True
    assert parsed["401752921"] is False
    assert "no_competitions" not in parsed


def test_parse_neutral_site_fails_closed_on_missing_payload():
    assert parse_neutral_site(None) == {}
    assert parse_neutral_site({}) == {}


# ----------------------------------------------------- NBA byte-identical guard


def test_nba_params_unaffected_by_college_reparameterization():
    from autonomy.sports.nba_model import HOME_EDGE_POINTS, MODEL_VERSION, NBA_PARAMS, PRIOR_PACE, PRIOR_RATING

    assert NBA_PARAMS.prior_pace == PRIOR_PACE == 99.5
    assert NBA_PARAMS.prior_rating == PRIOR_RATING == 114.0
    assert NBA_PARAMS.home_edge_points == HOME_EDGE_POINTS == 3.0
    assert NBA_PARAMS.version == MODEL_VERSION == "nba_pace_efficiency_v1"


# =================================================================== hub


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


def _box(team: str, opponent: str, is_home: bool, fga: float, orb: float,
         to: float, fta: float, game_id: str, league: str = "ncaamb") -> TeamBoxscore:
    return TeamBoxscore(
        game_id=game_id, league=league, team=team, opponent=opponent, is_home=is_home,
        stats={
            "fieldGoalsAttempted": fga, "offensiveRebounds": orb,
            "turnovers": to, "freeThrowsAttempted": fta,
        },
    )


def test_ncaaf_signal_is_challenger_only_and_fail_closed_with_no_matchup(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("ncaaf", "20260112")] = []  # no matchup found -> fail-closed
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
    )
    result = signal.generate(_market("KXNCAAFGAME-26JAN12KCBUF-KC", "Chiefs vs Bills Winner?"))
    assert result is None


def test_ncaaf_signal_prices_winner_spread_total_with_challenger_only(tmp_path):
    game = Game("g1", "ncaaf", "KC", "BUF", "pre", None, "2026-01-12T20:25Z",
                home_name="Kansas City Chiefs", away_name="Buffalo Bills")
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("ncaaf", "20260112")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    models["ncaaf"].teams["KC"] = models["ncaaf"]._team("KC")
    models["ncaaf"].teams["KC"].games = 10
    models["ncaaf"].teams["KC"].score_for_ewma = 34.0
    models["ncaaf"].teams["KC"].score_against_ewma = 20.0
    models["ncaaf"].teams["BUF"] = models["ncaaf"]._team("BUF")
    models["ncaaf"].teams["BUF"].games = 10
    models["ncaaf"].teams["BUF"].score_for_ewma = 28.0
    models["ncaaf"].teams["BUF"].score_against_ewma = 24.0
    elo = EloModel(league="ncaaf", ratings={"KC": 1650.0, "BUF": 1500.0})
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
        ncaaf_elo=elo,
    )

    winner = signal.generate(_market("KXNCAAFGAME-26JAN12KCBUF-KC", "Chiefs vs Bills Winner?"))
    assert winner is not None
    assert winner.features["challenger_only"] is True
    assert winner.features["margin_model_version"] == NCAAF_MODEL_VERSION
    assert 0.0 < winner.probability_yes < 1.0

    spread = signal.generate(_market(
        "KXNCAAFSPREAD-26JAN12KCBUF-KC3", "Kansas City Chiefs vs Buffalo Bills Spread",
        floor_strike=2.5))
    assert spread is not None
    assert spread.features["challenger_only"] is True
    assert spread.features["margin_model_version"] == NCAAF_MODEL_VERSION

    total = signal.generate(_market(
        "KXNCAAFTOTAL-26JAN12KCBUF", "Kansas City Chiefs vs Buffalo Bills Total Points",
        floor_strike=55.5))
    assert total is not None
    assert total.features["challenger_only"] is True
    assert total.features["margin_model_version"] == NCAAF_MODEL_VERSION
    # Winner cell and spread ladder share one distribution -- coherent.
    assert winner.probability_yes >= spread.probability_yes


def test_ncaaf_live_signal_uses_score_clock_and_discrete_scoring_model(tmp_path):
    game = Game(
        "g1", "ncaaf", "KC", "BUF", "in", None, "2026-01-12T20:25Z",
        home_name="Kansas City Chiefs", away_name="Buffalo Bills",
        home_score=28, away_score=24, current_period=4, current_clock="3:30",
    )
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("ncaaf", "20260112")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
        ncaaf_elo=EloModel(league="ncaaf", ratings={"KC": 1600.0, "BUF": 1500.0}),
    )

    winner = signal.generate(_market(
        "KXNCAAFGAME-26JAN12KCBUF-KC", "Chiefs vs Bills Winner?"))
    spread = signal.generate(_market(
        "KXNCAAFSPREAD-26JAN12KCBUF-KC1", "Chiefs vs Bills Spread",
        floor_strike=0.5))
    total = signal.generate(_market(
        "KXNCAAFTOTAL-26JAN12KCBUF", "Chiefs vs Bills Total Points",
        floor_strike=55.5))

    assert winner is not None and spread is not None and total is not None
    assert (winner.source, spread.source, total.source) == (
        "ncaaf_live_winner", "ncaaf_live_spread", "ncaaf_live_total")
    for result in (winner, spread, total):
        assert result.features["live_model_version"] == NCAAF_LIVE_MODEL_VERSION
        assert result.features["minutes_remaining"] == pytest.approx(3.5)
        assert result.features["expected_home_score"] >= 28
        assert result.features["expected_away_score"] >= 24
    assert winner.probability_yes >= spread.probability_yes


def test_ncaamb_signal_falls_back_wholesale_when_cold(tmp_path):
    game = Game("g1", "ncaamb", "DUKE", "UNC", "pre", None, "2026-01-12T20:25Z",
                home_name="Duke Blue Devils", away_name="North Carolina Tar Heels")
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("ncaamb", "20260112")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
    )
    winner = signal.generate(_market("KXNCAAMBGAME-26JAN12DUKEUNC-DUKE", "Duke vs UNC Winner?"))
    assert winner is not None
    assert winner.features["challenger_only"] is True
    assert winner.features["ncaamb_model_fallback"] is True
    assert "margin_model_version" not in winner.features


def test_ncaamb_signal_prices_from_the_pace_engine_when_warm(tmp_path):
    game = Game("g1", "ncaamb", "DUKE", "UNC", "pre", None, "2026-01-12T20:25Z",
                home_name="Duke Blue Devils", away_name="North Carolina Tar Heels")
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("ncaamb", "20260112")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    store = BoxscoreStore("ncaamb", path=tmp_path / "boxscores_ncaamb.json")
    store.ingest([
        _box("DUKE", "UNC", True, fga=62.0, orb=11.0, to=12.0, fta=18.0, game_id=f"gh{i}")
        for i in range(MIN_GAMES_FOR_ENGINE)
    ])
    store.ingest([
        _box("UNC", "DUKE", False, fga=60.0, orb=10.0, to=13.0, fta=16.0, game_id=f"ga{i}")
        for i in range(MIN_GAMES_FOR_ENGINE)
    ])
    ncaamb_model = NbaModel(params=NCAAMB_PARAMS)
    ncaamb_model.teams["DUKE"] = NbaTeamState(games=10, pace_ewma=71.0, ortg_ewma=112.0, drtg_ewma=100.0)
    ncaamb_model.teams["UNC"] = NbaTeamState(games=10, pace_ewma=69.0, ortg_ewma=108.0, drtg_ewma=103.0)
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
        ncaamb_boxscores=store, ncaamb_model=ncaamb_model,
    )
    reference = ncaamb_model.predict(game)

    winner = signal.generate(_market("KXNCAAMBGAME-26JAN12DUKEUNC-DUKE", "Duke vs UNC Winner?"))
    assert winner is not None
    assert winner.features["challenger_only"] is True
    assert winner.features["margin_model_version"] == NCAAMB_MODEL_VERSION
    assert winner.features["ncaamb_model_fallback"] is False
    assert winner.probability_yes == pytest.approx(reference.home_win_probability, abs=1e-9)


def test_ncaamb_live_signal_uses_40_minute_state_model(tmp_path):
    game = Game(
        "g1", "ncaamb", "DUKE", "UNC", "in", None, "2026-01-12T20:25Z",
        home_name="Duke Blue Devils", away_name="North Carolina Tar Heels",
        home_score=38, away_score=35, current_period=2, current_clock="12:00",
    )
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("ncaamb", "20260112")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    store = BoxscoreStore("ncaamb", path=tmp_path / "boxscores_ncaamb.json")
    store.ingest([
        _box("DUKE", "UNC", True, 62.0, 11.0, 12.0, 18.0, f"gh{i}")
        for i in range(MIN_GAMES_FOR_ENGINE)
    ])
    store.ingest([
        _box("UNC", "DUKE", False, 60.0, 10.0, 13.0, 16.0, f"ga{i}")
        for i in range(MIN_GAMES_FOR_ENGINE)
    ])
    ncaamb_model = NbaModel(params=NCAAMB_PARAMS)
    ncaamb_model.teams["DUKE"] = NbaTeamState(
        games=10, pace_ewma=71.0, ortg_ewma=112.0, drtg_ewma=100.0)
    ncaamb_model.teams["UNC"] = NbaTeamState(
        games=10, pace_ewma=69.0, ortg_ewma=108.0, drtg_ewma=103.0)
    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
        ncaamb_boxscores=store, ncaamb_model=ncaamb_model,
    )

    winner = signal.generate(_market(
        "KXNCAAMBGAME-26JAN12DUKEUNC-DUKE", "Duke vs UNC Winner?"))
    spread = signal.generate(_market(
        "KXNCAAMBSPREAD-26JAN12DUKEUNC-DUKE3",
        "Duke Blue Devils vs North Carolina Tar Heels Spread",
        floor_strike=2.5))
    total = signal.generate(_market(
        "KXNCAAMBTOTAL-26JAN12DUKEUNC",
        "Duke Blue Devils vs North Carolina Tar Heels Total Points",
        floor_strike=145.5))

    assert winner is not None and spread is not None and total is not None
    assert (winner.source, spread.source, total.source) == (
        "ncaamb_live_winner", "ncaamb_live_spread", "ncaamb_live_total")
    for result in (winner, spread, total):
        assert result.features["live_model_version"] == NCAAMB_LIVE_MODEL_VERSION
        assert result.features["minutes_remaining"] == pytest.approx(12.0)
        assert result.features["expected_scores_post_shift"] is True
    assert winner.probability_yes >= spread.probability_yes
