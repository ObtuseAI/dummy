"""NHL bivariate-Poisson + OT/SO engine (WS-3): unit math + signal integration.

Zero network: all boxscore/scoreboard fixtures used here are either hand-built
in-memory (mirroring tests/test_autonomy_nba_model.py's pattern) or the small
trimmed real-payload fixtures committed under tests/fixtures/ from the
build-time probes (see autonomy/sports/nhl_model.py's module docstring for
the exact event ids/dates and observed keys).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
from autonomy.sports.boxscores import BoxscoreStore, TeamBoxscore
from autonomy.sports.espn import Game
from autonomy.sports.nhl_model import (
    GOAL_MATRIX_TRUNCATION,
    GOALIE_DELTA_MAX,
    GOALIE_UNKNOWN_UNCERTAINTY_BUMP,
    MIN_GAMES_FOR_ENGINE,
    MODEL_VERSION,
    OT_GOAL_PRE_SHOOTOUT,
    OT_STRENGTH_TILT,
    PULLED_GOALIE_FINAL_MINUTES,
    PULLED_GOALIE_LEADING_MULT,
    PULLED_GOALIE_MAX_DEFICIT,
    PULLED_GOALIE_TRAILING_MULT,
    ROOKIE_GOALIE_START_THRESHOLD,
    GoalieBoxscore,
    NhlGoalieState,
    NhlModel,
    NhlTeamState,
    away_cover_probability,
    final_total_pmf,
    goal_split,
    goalie_delta,
    home_cover_probability,
    home_win_probability,
    is_rookie_goalie,
    is_warm,
    minutes_remaining_in_game,
    ot_win_probability,
    parse_goalie_boxscores,
    parse_probable_goalies,
    poisson_pmf,
    pulled_goalie_lambdas,
    total_over_probability,
    win_prob_reg_normalized,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _box(team: str, opponent: str, is_home: bool, ppg: float, ppo: float,
         shots: float = 30.0, game_id: str = "g1") -> TeamBoxscore:
    return TeamBoxscore(
        game_id=game_id, league="nhl", team=team, opponent=opponent, is_home=is_home,
        stats={"powerPlayGoals": ppg, "powerPlayOpportunities": ppo, "shotsTotal": shots},
    )


# ============================================================ poisson math


def test_poisson_pmf_matches_hand_computed_value():
    # Pois(2.0)(3) = e^-2 * 2^3 / 3!
    expected = math.exp(-2.0) * (2.0 ** 3) / 6.0
    assert poisson_pmf(3, 2.0) == pytest.approx(expected, abs=1e-12)


def test_goal_matrix_cell_is_independent_poisson_product_hand_computed():
    # A single (home=4, away=2) cell against a matrix built from independent
    # Poissons must equal the hand-multiplied closed-form value -- no
    # correlation term (documented as deferred in the module docstring).
    lambda_home, lambda_away = 3.2, 2.7
    hand = (
        (math.exp(-lambda_home) * lambda_home ** 4 / math.factorial(4))
        * (math.exp(-lambda_away) * lambda_away ** 2 / math.factorial(2))
    )
    assert poisson_pmf(4, lambda_home) * poisson_pmf(2, lambda_away) == pytest.approx(hand, abs=1e-12)


def test_goal_split_regulation_tie_matches_hand_summed_diagonal():
    split = goal_split(0, 1.0, 1.0)
    expected_tie = sum(poisson_pmf(k, 1.0) ** 2 for k in range(GOAL_MATRIX_TRUNCATION + 1))
    assert split.reg_tie == pytest.approx(expected_tie, abs=1e-9)


def test_goal_split_probabilities_sum_to_one():
    split = goal_split(0, 3.05, 2.9)
    # GOAL_MATRIX_TRUNCATION=12 is the brief's exact, deliberate truncation --
    # at typical NHL lambdas (~3.0) that loses ~3e-5 of joint tail mass, so
    # the tolerance here is set to comfortably clear that documented noise
    # floor while still catching a genuine formula bug (which would be off
    # by orders of magnitude more).
    assert split.reg_win + split.reg_tie + split.reg_loss == pytest.approx(1.0, abs=1e-4)


# ================================================================== OT / SO


def test_win_prob_reg_normalized_excludes_tie_mass():
    # 0.6 win, 0.1 tie, 0.3 loss -> normalized win share over win+loss only.
    assert win_prob_reg_normalized(0.6, 0.3) == pytest.approx(0.6 / 0.9, abs=1e-12)


def test_ot_win_probability_is_coin_flip_when_regulation_is_symmetric():
    assert ot_win_probability(0.4, 0.4) == pytest.approx(0.5, abs=1e-12)


def test_ot_win_probability_tilts_toward_the_stronger_regulation_side():
    # reg_win > reg_loss -> p_ot should lean above 0.5, bounded by the tilt.
    p_ot = ot_win_probability(0.55, 0.35)
    assert 0.5 < p_ot < 0.5 + 0.5 * OT_STRENGTH_TILT


def test_home_win_probability_is_exactly_half_when_lambdas_are_equal():
    split = goal_split(0, 3.0, 3.0)
    # "Exactly" 0.5 as a mathematical/structural fact (symmetric lambdas ->
    # symmetric reg_win/reg_loss -> p_ot=0.5 -> home_win=0.5*(total mass));
    # GOAL_MATRIX_TRUNCATION=12's documented ~1.6e-5 per-side tail loss at
    # lambda=3.0 sets the noise floor -- see test_goal_split_probabilities_sum_to_one.
    assert home_win_probability(split) == pytest.approx(0.5, abs=1e-4)


def test_home_win_probability_favors_higher_lambda_side():
    split = goal_split(0, 3.4, 2.6)
    assert home_win_probability(split) > 0.5


# ============================================================== puck line


@pytest.mark.parametrize("lambda_home,lambda_away", [
    (3.05, 2.90), (2.5, 3.5), (4.0, 4.0), (1.8, 3.2), (3.05, 3.05),
])
def test_puck_line_cover_probability_is_always_below_win_probability(lambda_home, lambda_away):
    split = goal_split(0, lambda_home, lambda_away)
    win = home_win_probability(split)
    cover = home_cover_probability(split, 1.5)
    assert cover < win


def test_puck_line_home_and_away_cover_are_not_simply_complementary():
    # Both sides can fail to cover in a 1-goal (OT/SO) decision -- so
    # home_cover(1.5) + away_cover(1.5) < 1, unlike the winner cell (which
    # IS a true complementary pair: home_win + away_win == 1 exactly).
    split = goal_split(0, 3.05, 2.90)
    home_cover = home_cover_probability(split, 1.5)
    away_cover = away_cover_probability(split, 1.5)
    away_win = 1.0 - home_win_probability(split)
    assert home_cover + away_cover < 1.0
    assert away_cover < away_win  # the OT/SO-decided away wins never "cover"


# ==================================================================== totals


def test_totals_ot_bump_increases_mass_just_above_a_tie_boundary():
    split = goal_split(0, 3.0, 3.0)
    # Every tie total is even; pick threshold = tie_total + 0.5 so ONLY the
    # OT/SO +1 bump can push mass across it (see module docstring's totals
    # derivation) -- 3-3 (total 6) is the modal tie at lambda=3.0.
    threshold = 6.5
    bumped_pmf = final_total_pmf(split)
    raw_pmf = split.total_pmf  # the zero-bump ("stays at reg total") baseline
    bumped = total_over_probability(bumped_pmf, threshold)
    raw = total_over_probability(raw_pmf, threshold)
    assert bumped > raw


def test_totals_pmf_sums_to_one_after_the_ot_bump():
    split = goal_split(0, 3.05, 2.9)
    pmf = final_total_pmf(split)
    # Same GOAL_MATRIX_TRUNCATION=12 noise floor as the other sum-to-one
    # check above; the OT bump only reallocates mass, it never creates or
    # destroys any, so this should track the pre-bump total exactly.
    assert sum(pmf) == pytest.approx(1.0, abs=1e-4)


def test_ot_goal_pre_shootout_constant_is_the_documented_value():
    assert OT_GOAL_PRE_SHOOTOUT == 0.70


# ================================================================== goalie


def test_goalie_delta_is_bounded_to_the_documented_max():
    assert goalie_delta(0.999) == pytest.approx(GOALIE_DELTA_MAX, abs=1e-12)
    assert goalie_delta(0.001) == pytest.approx(-GOALIE_DELTA_MAX, abs=1e-12)


def test_goalie_delta_is_zero_at_the_league_prior():
    from autonomy.sports.nhl_model import GOALIE_PRIOR_SAVE_PCT
    assert goalie_delta(GOALIE_PRIOR_SAVE_PCT) == pytest.approx(0.0, abs=1e-12)


def test_known_elite_goalie_shifts_the_mean_not_just_uncertainty():
    model = NhlModel()
    model.goalies["BUF|Elite Wall"] = NhlGoalieState(starts=40, save_pct_ewma=0.950)
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="pre",
                home_won=None, date="2026-01-12T00:00Z")
    known = model.predict(game, home_goalie_name=None, away_goalie_name="Elite Wall")
    unknown = model.predict(game, home_goalie_name=None, away_goalie_name=None)
    # A known elite AWAY goalie suppresses the HOME team's expected goals
    # (home shoots on the away goalie) -- a mean shift, not just uncertainty.
    assert known.expected_home_goals < unknown.expected_home_goals
    assert known.goalie_known_away is True
    assert unknown.goalie_known_away is False


def test_goalie_unknown_widens_uncertainty_never_shifts_the_mean():
    model = NhlModel()
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="pre",
                home_won=None, date="2026-01-12T00:00Z")
    known_absent_but_flagged = model.predict(game, home_goalie_name=None, away_goalie_name=None)
    # No goalie history at all -> even "known" (a name given) with zero
    # starts regresses to the same prior-blended mean as unknown, but the
    # uncertainty bump only fires when the probable itself is absent.
    named_cold = model.predict(game, home_goalie_name=None, away_goalie_name="Rookie Nobody")
    assert named_cold.expected_home_goals == pytest.approx(known_absent_but_flagged.expected_home_goals, abs=1e-9)
    assert named_cold.winner_uncertainty < known_absent_but_flagged.winner_uncertainty


def test_goalie_unknown_uncertainty_bump_matches_documented_constant():
    model = NhlModel()
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="pre",
                home_won=None, date="2026-01-12T00:00Z")
    both_known = model.predict(game, home_goalie_name="Someone", away_goalie_name="Someone Else")
    one_unknown = model.predict(game, home_goalie_name="Someone", away_goalie_name=None)
    assert one_unknown.winner_uncertainty == pytest.approx(
        min(0.45, both_known.winner_uncertainty + GOALIE_UNKNOWN_UNCERTAINTY_BUMP), abs=1e-9)


def test_rookie_goalie_flag_uses_own_store_start_count_proxy():
    veteran = NhlGoalieState(starts=15, save_pct_ewma=0.905)
    rookie = NhlGoalieState(starts=3, save_pct_ewma=0.905)
    cold = None
    assert is_rookie_goalie(veteran) is False
    assert is_rookie_goalie(rookie) is True
    assert is_rookie_goalie(cold) is True
    assert ROOKIE_GOALIE_START_THRESHOLD == 10


def test_parse_goalie_boxscores_reads_the_probed_fixture_shape():
    summary = _load_fixture("boxscore_nhl_401803067_players.json")
    rows = parse_goalie_boxscores(summary)
    by_team = {row.team: row for row in rows}
    assert by_team["FLA"].name == "Sergei Bobrovsky"
    assert by_team["FLA"].saves == pytest.approx(20.0)
    assert by_team["FLA"].shots_against == pytest.approx(23.0)
    assert by_team["BUF"].name == "Colten Ellis"
    assert by_team["BUF"].saves == pytest.approx(28.0)
    assert by_team["BUF"].shots_against == pytest.approx(31.0)
    assert by_team["BUF"].game_id == "401803067"


def test_parse_probable_goalies_reads_the_probed_scoreboard_fixture():
    payload = _load_fixture("scoreboard_nhl_20260112_401803067.json")
    parsed = parse_probable_goalies(payload)
    home_goalie, away_goalie = parsed["401803067"]
    assert home_goalie == "Colten Ellis"
    assert away_goalie == "Sergei Bobrovsky"


def test_parse_probable_goalies_missing_probables_is_none_not_fabricated():
    payload = {"events": [{"id": "1", "competitions": [{"competitors": [
        {"homeAway": "home", "team": {"abbreviation": "BOS"}},
        {"homeAway": "away", "team": {"abbreviation": "BUF"}},
    ]}]}]}
    parsed = parse_probable_goalies(payload)
    assert parsed["1"] == (None, None)


# ============================================================ special teams


def test_special_teams_mismatch_shift_is_bounded():
    from autonomy.sports.nhl_model import SPECIAL_TEAMS_MAX_SHIFT, special_teams_shift
    # mismatch = pp_subject - (1 - pk_opponent) - league_mean (brief's exact
    # formula); pp_subject=0.99 and pk_opponent=0.99 both push the mismatch
    # strongly positive (subject's own PP% far exceeds the tiny (1-pk_opponent)
    # baseline), clipped at the documented +/-0.15 bound.
    assert special_teams_shift(0.99, 0.99) == pytest.approx(SPECIAL_TEAMS_MAX_SHIFT, abs=1e-9)
    assert special_teams_shift(0.01, 0.01) == pytest.approx(-SPECIAL_TEAMS_MAX_SHIFT, abs=1e-9)


def test_special_teams_mismatch_is_zero_at_league_priors():
    from autonomy.sports.nhl_model import PRIOR_PK_PCT, PRIOR_PP_PCT, special_teams_shift
    assert special_teams_shift(PRIOR_PP_PCT, PRIOR_PK_PCT) == pytest.approx(0.0, abs=1e-9)


# ================================================================ live math


def test_minutes_remaining_at_start_of_first_period():
    assert minutes_remaining_in_game(1, "20:00") == pytest.approx(60.0, abs=1e-9)


def test_minutes_remaining_mid_third_period():
    assert minutes_remaining_in_game(3, "5:00") == pytest.approx(5.0, abs=1e-9)


def test_minutes_remaining_overtime_uses_only_its_own_clock():
    assert minutes_remaining_in_game(4, "3:00") == pytest.approx(3.0, abs=1e-9)


def test_minutes_remaining_unparseable_clock_is_none():
    assert minutes_remaining_in_game(2, "0.0") is None
    assert minutes_remaining_in_game(None, "5:00") is None


def test_pulled_goalie_noop_outside_final_three_minutes():
    home, away = pulled_goalie_lambdas(1.0, 1.0, home_score=2, away_score=3, minutes_remaining=5.0)
    assert (home, away) == (1.0, 1.0)


def test_pulled_goalie_noop_when_deficit_exceeds_bound():
    home, away = pulled_goalie_lambdas(1.0, 1.0, home_score=1, away_score=4, minutes_remaining=2.0)
    assert (home, away) == (1.0, 1.0)
    assert PULLED_GOALIE_MAX_DEFICIT == 2


def test_pulled_goalie_noop_when_tied():
    home, away = pulled_goalie_lambdas(1.0, 1.0, home_score=2, away_score=2, minutes_remaining=1.0)
    assert (home, away) == (1.0, 1.0)


def test_pulled_goalie_inflates_trailing_and_leading_correctly_inside_window():
    assert PULLED_GOALIE_FINAL_MINUTES == 3.0
    # Home trails by 1 with 2 minutes left: home (trailing, extra attacker)
    # gets the smaller bump; away (leading, empty net) gets the larger one.
    home, away = pulled_goalie_lambdas(1.0, 1.0, home_score=2, away_score=3, minutes_remaining=2.0)
    assert home == pytest.approx(PULLED_GOALIE_TRAILING_MULT, abs=1e-9)
    assert away == pytest.approx(PULLED_GOALIE_LEADING_MULT, abs=1e-9)


def test_pulled_goalie_only_applies_in_live_final_three_minutes_boundary():
    just_outside = pulled_goalie_lambdas(1.0, 1.0, home_score=1, away_score=2, minutes_remaining=3.01)
    just_inside = pulled_goalie_lambdas(1.0, 1.0, home_score=1, away_score=2, minutes_remaining=3.0)
    assert just_outside == (1.0, 1.0)
    assert just_inside != (1.0, 1.0)


# ============================================= model: settlement invariant


def test_update_refuses_a_non_post_game():
    model = NhlModel()
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="in",
                home_won=None, date="2026-01-12T00:00Z", home_score=2, away_score=1)
    home_box = _box("BOS", "BUF", True, ppg=1.0, ppo=3.0)
    away_box = _box("BUF", "BOS", False, ppg=0.0, ppo=2.0)
    assert model.update(game, home_box, away_box) is False
    assert model.games_seen == 0


def test_update_learns_only_from_a_completed_final_and_is_idempotent():
    model = NhlModel()
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="post",
                home_won=True, date="2026-01-12T00:00Z", home_score=4, away_score=2)
    home_box = _box("BOS", "BUF", True, ppg=1.0, ppo=3.0, game_id="g1")
    away_box = _box("BUF", "BOS", False, ppg=0.0, ppo=2.0, game_id="g1")
    assert model.update(game, home_box, away_box) is True
    assert model.games_seen == 1
    # Idempotent by game_id.
    assert model.update(game, home_box, away_box) is False
    assert model.games_seen == 1


def test_update_missing_boxscore_is_a_noop():
    model = NhlModel()
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="post",
                home_won=True, date="2026-01-12T00:00Z", home_score=4, away_score=2)
    assert model.update(game, None, None) is False


def test_update_ingests_goalie_boxscores_and_builds_the_store():
    model = NhlModel()
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="post",
                home_won=True, date="2026-01-12T00:00Z", home_score=4, away_score=2)
    home_box = _box("BOS", "BUF", True, ppg=1.0, ppo=3.0, game_id="g1")
    away_box = _box("BUF", "BOS", False, ppg=0.0, ppo=2.0, game_id="g1")
    home_goalies = [GoalieBoxscore(game_id="g1", team="BOS", name="Home Netminder",
                                    saves=30.0, shots_against=32.0, time_on_ice_minutes=60.0)]
    away_goalies = [GoalieBoxscore(game_id="g1", team="BUF", name="Away Netminder",
                                    saves=26.0, shots_against=30.0, time_on_ice_minutes=60.0)]
    model.update(game, home_box, away_box, home_goalies, away_goalies)
    state = model.goalies["BOS|Home Netminder"]
    assert state.starts == 1
    assert state.save_pct_ewma != pytest.approx(0.905, abs=1e-6)  # moved off the prior


# ============================================================== persistence


def test_save_and_load_round_trips_team_and_goalie_state(tmp_path):
    model = NhlModel()
    game = Game(game_id="g1", league="nhl", home="BOS", away="BUF", status="post",
                home_won=True, date="2026-01-12T00:00Z", home_score=4, away_score=2)
    home_box = _box("BOS", "BUF", True, ppg=1.0, ppo=3.0, game_id="g1")
    away_box = _box("BUF", "BOS", False, ppg=0.0, ppo=2.0, game_id="g1")
    home_goalies = [GoalieBoxscore(game_id="g1", team="BOS", name="Home Netminder",
                                    saves=30.0, shots_against=32.0, time_on_ice_minutes=60.0)]
    model.update(game, home_box, away_box, home_goalies, [])

    path = tmp_path / "nhl_bipoisson_model.json"
    model.save(path)
    reloaded = NhlModel.load(path)
    assert reloaded.teams["BOS"].games == 1
    assert reloaded.teams["BOS"].gf_ewma == pytest.approx(model.teams["BOS"].gf_ewma, abs=1e-12)
    assert reloaded.goalies["BOS|Home Netminder"].starts == 1
    assert reloaded.goalies["BOS|Home Netminder"].save_pct_ewma == pytest.approx(
        model.goalies["BOS|Home Netminder"].save_pct_ewma, abs=1e-12)
    assert reloaded.games_seen == 1
    assert "g1" in reloaded.processed_game_ids


def test_load_missing_file_returns_fresh_model(tmp_path):
    model = NhlModel.load(tmp_path / "does_not_exist.json")
    assert model.games_seen == 0
    assert model.teams == {}
    assert model.goalies == {}


# =================================================================== warm gate


def test_is_warm_requires_both_teams_to_meet_the_floor(tmp_path):
    store = BoxscoreStore("nhl", path=tmp_path / "boxscores_nhl.json")
    assert is_warm(store, "BOS", "BUF") is False
    boxes = [_box("BOS", "BUF", True, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    store.ingest(boxes)
    assert is_warm(store, "BOS", "BUF") is False  # BUF still cold


# ============================================================ signal hook


NOW = datetime(2026, 1, 12, 16, 0, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _mk_signal(tmp_path, game: Game, nhl_model=None):
    from autonomy.sports.espn import EspnClient

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("nhl", "20260112")] = [game]
    signal = TeamSportsIntelligenceSignal(
        espn=client, model_dir=tmp_path,
        nhl_model=nhl_model, nhl_boxscores=BoxscoreStore("nhl", path=tmp_path / "boxscores_nhl.json"),
        fetch_nhl_scoreboard=lambda league, dates: {"events": []},
    )
    return signal


def test_nhl_hook_falls_back_to_generic_model_when_cold(tmp_path):
    game = Game("g1", "nhl", "BOS", "BUF", "pre", None, "2026-01-12T20:00Z")
    signal = _mk_signal(tmp_path, game)
    result = signal.generate(_market("KXNHLGAME-26JAN12BOSBUF-BOS", "Bruins vs Sabres Winner?"))
    assert result is not None
    assert result.features["nhl_model_fallback"] is True
    assert result.features["model_version"] == "team-score-ewma-v1"
    assert "margin_model_version" not in result.features


def test_nhl_hook_uses_bipoisson_engine_once_warm(tmp_path):
    model = NhlModel()
    game = Game("g1", "nhl", "BOS", "BUF", "pre", None, "2026-01-12T20:00Z")
    signal = _mk_signal(tmp_path, game, nhl_model=model)
    boxes = [_box("BOS", "BUF", True, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    boxes += [_box("BUF", "BOS", False, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    signal.nhl_boxscores.ingest(boxes)

    result = signal.generate(_market("KXNHLGAME-26JAN12BOSBUF-BOS", "Bruins vs Sabres Winner?"))
    assert result is not None
    assert result.features["nhl_model_fallback"] is False
    assert result.features["margin_model_version"] == MODEL_VERSION
    assert result.features["goalie_known_home"] is False
    assert result.features["goalie_known_away"] is False


def test_nhl_hook_prices_total_and_spread_once_warm(tmp_path):
    model = NhlModel()
    game = Game("g1", "nhl", "BOS", "BUF", "pre", None, "2026-01-12T20:00Z")
    signal = _mk_signal(tmp_path, game, nhl_model=model)
    boxes = [_box("BOS", "BUF", True, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    boxes += [_box("BUF", "BOS", False, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    signal.nhl_boxscores.ingest(boxes)

    total = signal.generate(_market(
        "KXNHLTOTAL-26JAN12BOSBUF-6", "BOS vs BUF Total", floor_strike=5.5))
    assert total is not None
    assert total.source == "nhl_game_total"

    spread = signal.generate(_market(
        "KXNHLSPREAD-26JAN12BOSBUF-BOS1", "BOS vs BUF Spread", floor_strike=1.5))
    assert spread is not None
    assert spread.source == "nhl_spread"
    assert 0.0 <= spread.probability_yes <= 1.0 and 0.0 <= total.probability_yes <= 1.0


def test_nhl_hook_live_winner_reprices_an_in_progress_game(tmp_path):
    model = NhlModel()
    game = Game("g1", "nhl", "BOS", "BUF", "in", None, "2026-01-12T20:00Z",
                home_score=2, away_score=1, current_period=3, current_clock="5:00")
    signal = _mk_signal(tmp_path, game, nhl_model=model)
    boxes = [_box("BOS", "BUF", True, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    boxes += [_box("BUF", "BOS", False, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    signal.nhl_boxscores.ingest(boxes)

    result = signal.generate(_market("KXNHLGAME-26JAN12BOSBUF-BOS", "Bruins vs Sabres Winner?"))
    assert result is not None
    assert result.source == "nhl_live_winner"
    assert result.features["live"] is True


def test_nhl_hook_live_abstains_when_cold(tmp_path):
    game = Game("g1", "nhl", "BOS", "BUF", "in", None, "2026-01-12T20:00Z",
                home_score=2, away_score=1, current_period=3, current_clock="5:00")
    signal = _mk_signal(tmp_path, game)
    result = signal.generate(_market("KXNHLGAME-26JAN12BOSBUF-BOS", "Bruins vs Sabres Winner?"))
    assert result is None


def _probables_payload(game_id: str, home_name: str, away_name: str) -> dict:
    return {"events": [{"id": game_id, "competitions": [{"competitors": [
        {"homeAway": "home", "probables": [{"athlete": {"displayName": home_name}}]},
        {"homeAway": "away", "probables": [{"athlete": {"displayName": away_name}}]},
    ]}]}]}


def test_nhl_hook_emitted_signal_widens_uncertainty_when_goalie_unknown(tmp_path):
    # WS-3 review regression: the pre-game winner path must widen the
    # emitted Signal.uncertainty by GOALIE_UNKNOWN_UNCERTAINTY_BUMP when the
    # starting goalie is unconfirmed, sourced from the NHL model's own
    # nhl_prediction.winner_uncertainty -- not the generic TeamScoreModel's
    # prediction.winner_uncertainty, which never carries the bump.
    game = Game("g1", "nhl", "BOS", "BUF", "pre", None, "2026-01-12T20:00Z")
    boxes = [_box("BOS", "BUF", True, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]
    boxes += [_box("BUF", "BOS", False, 1.0, 3.0, game_id=f"g{i}") for i in range(MIN_GAMES_FOR_ENGINE)]

    unknown_dir = tmp_path / "unknown"
    unknown_dir.mkdir()
    unknown_signal = _mk_signal(unknown_dir, game, nhl_model=NhlModel())
    unknown_signal.nhl_boxscores.ingest(boxes)
    unknown_result = unknown_signal.generate(
        _market("KXNHLGAME-26JAN12BOSBUF-BOS", "Bruins vs Sabres Winner?"))
    assert unknown_result is not None
    assert unknown_result.features["goalie_known_home"] is False
    assert unknown_result.features["goalie_known_away"] is False

    known_dir = tmp_path / "known"
    known_dir.mkdir()
    known_signal = _mk_signal(known_dir, game, nhl_model=NhlModel())
    known_signal._fetch_nhl_scoreboard = (
        lambda league, dates: _probables_payload("g1", "Known Home Goalie", "Known Away Goalie"))
    known_signal.nhl_boxscores.ingest(boxes)
    known_result = known_signal.generate(
        _market("KXNHLGAME-26JAN12BOSBUF-BOS", "Bruins vs Sabres Winner?"))
    assert known_result is not None
    assert known_result.features["goalie_known_home"] is True
    assert known_result.features["goalie_known_away"] is True

    # The widening must actually reach the emitted Signal, not just the
    # NhlModel prediction object -- this is the exact defect under review.
    # Both goalies are unconfirmed in the "unknown" case, so the bump is
    # applied twice (once per side) inside NhlModel.predict -- compute the
    # expected values independently from the model itself rather than
    # re-deriving the arithmetic, so this test doesn't silently drift if the
    # bump formula changes.
    reference_model = NhlModel()
    expected_unknown = reference_model.predict(game, None, None).winner_uncertainty
    expected_known = reference_model.predict(
        game, "Known Home Goalie", "Known Away Goalie").winner_uncertainty
    assert expected_unknown > expected_known  # sanity: the bump is real
    assert unknown_result.uncertainty == pytest.approx(expected_unknown, abs=1e-9)
    assert known_result.uncertainty == pytest.approx(expected_known, abs=1e-9)
    assert unknown_result.uncertainty > known_result.uncertainty
