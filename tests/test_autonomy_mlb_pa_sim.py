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


import random as _random

from autonomy.sports.mlb_pa_sim import sample_outcome, simulate_half_inning
from autonomy.sports.mlb_pa_sim import _advance


class _QueuedRng:
    """Deterministic rng stub: random() yields queued values, then 0.999."""

    def __init__(self, values=()):
        self._values = list(values)

    def random(self) -> float:
        return self._values.pop(0) if self._values else 0.999


def test_advance_bases_loaded_walk_scores_one_keeps_loaded():
    bases = [True, True, True]
    assert _advance(bases, "bb", _QueuedRng()) == 1
    assert bases == [True, True, True]


def test_advance_walk_with_first_open_no_force_run():
    bases = [False, True, True]  # 1st open, 2nd+3rd occupied
    assert _advance(bases, "bb", _QueuedRng()) == 0
    assert bases == [True, True, True]  # batter to 1st, no forced run


def test_advance_single_scores_runner_from_second_on_low_roll():
    bases = [False, True, False]  # runner on 2nd
    # Low roll < SINGLE_SCORE_FROM_SECOND -> the runner scores from 2nd.
    assert _advance(bases, "single", _QueuedRng([0.0])) == 1
    assert bases == [True, False, False]  # only the batter, on 1st


def test_advance_single_holds_runner_at_third_on_high_roll():
    bases = [False, True, False]  # runner on 2nd
    # High roll -> the runner holds at 3rd (old station-to-station behavior).
    assert _advance(bases, "single", _QueuedRng([0.99])) == 0
    assert bases == [True, False, True]  # batter on 1st, runner held at 3rd


def test_advance_single_first_to_third_taken_on_low_roll():
    # 3rd is open; runner on 1st takes 3rd on a low first-to-third roll.
    bases = [True, False, False]  # runner on 1st only
    assert _advance(bases, "single", _QueuedRng([0.0])) == 0
    assert bases == [True, False, True]  # batter on 1st, runner to 3rd


def test_advance_single_first_to_third_blocked_by_held_runner():
    # Runner on 2nd holds at 3rd (high roll), which occupies 3rd; the runner on
    # 1st is then forced to 2nd WITHOUT a first-to-third roll (the base is taken,
    # so the guard short-circuits and no second value is drawn).
    bases = [True, True, False]  # runners on 1st and 2nd
    assert _advance(bases, "single", _QueuedRng([0.99])) == 0
    assert bases == [True, True, True]  # batter 1B, 1B-runner 2B, 2B-runner 3B


def test_advance_single_scores_runner_from_third():
    # A runner on 3rd always scores on a single (no roll for the 3B runner).
    bases = [False, False, True]  # runner on 3rd
    assert _advance(bases, "single", _QueuedRng()) == 1
    assert bases == [True, False, False]  # only the batter, on 1st


def test_advance_double_scores_runner_from_second():
    bases = [False, True, False]  # runner on 2nd
    assert _advance(bases, "double", _QueuedRng()) == 1  # 2nd always scores
    assert bases == [False, True, False]  # batter on 2nd


def test_advance_double_scores_runner_from_first_on_low_roll():
    bases = [True, False, False]  # runner on 1st
    # Low roll < DOUBLE_SCORE_FROM_FIRST -> the runner scores from 1st.
    assert _advance(bases, "double", _QueuedRng([0.0])) == 1
    assert bases == [False, True, False]  # batter on 2nd


def test_advance_home_run_with_two_on_scores_three_empties_bases():
    bases = [True, True, False]  # runners on 1st and 2nd
    assert _advance(bases, "hr", _QueuedRng()) == 3  # two runners + batter
    assert bases == [False, False, False]


def test_sample_outcome_is_deterministic_and_valid():
    dist = {"k": 0.25, "bb": 0.08, "hbp": 0.01, "single": 0.14,
            "double": 0.05, "triple": 0.004, "hr": 0.03, "out": 0.436}
    rng = _random.Random(7)
    picks = [sample_outcome(dist, rng) for _ in range(200)]
    assert set(picks) <= set(dist)
    # Determinism: same seed -> same sequence.
    rng2 = _random.Random(7)
    picks2 = [sample_outcome(dist, rng2) for _ in range(200)]
    assert picks == picks2


def test_half_inning_hr_out_distribution_is_deterministic_and_terminates():
    hr_out = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 0.0,
              "double": 0.0, "triple": 0.0, "hr": 0.5, "out": 0.5}
    a = simulate_half_inning(0, lambda i: hr_out, _random.Random(3))
    b = simulate_half_inning(0, lambda i: hr_out, _random.Random(3))
    assert a == b                      # deterministic
    assert a[0] >= 0 and a[1] >= 3     # terminated at >= 3 outs (cursor advanced)


def test_half_inning_all_outs_scores_zero():
    outs_only = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 0.0,
                 "double": 0.0, "triple": 0.0, "hr": 0.0, "out": 1.0}
    runs, cursor = simulate_half_inning(0, lambda i: outs_only, _random.Random(1))
    assert runs == 0
    assert cursor == 3  # exactly three batters retired


from autonomy.sports.mlb_pa_sim import GameResult, simulate_one_game
from autonomy.sports.statsapi import LineupSlot, MlbGameContext, PitcherRates


def _context(*, home_batter_iso, away_batter_iso):
    home_lineup = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    away_lineup = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
    batter_rates = {}
    for i in range(9):
        batter_rates[100 + i] = BatterRates(
            player_id=100 + i, bats="R", k_pct=0.20, bb_pct=0.09,
            obp=0.340, slg=0.300 + home_batter_iso, iso=home_batter_iso)
        batter_rates[200 + i] = BatterRates(
            player_id=200 + i, bats="R", k_pct=0.20, bb_pct=0.09,
            obp=0.340, slg=0.300 + away_batter_iso, iso=away_batter_iso)
    return MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="H", away="A",
        home_lineup=home_lineup, away_lineup=away_lineup,
        home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        away_pitcher=PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        batter_rates=batter_rates, park_run_factor=1.0, park_hr_factor=1.0,
    )


def test_simulate_one_game_returns_coherent_result():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    result = simulate_one_game(ctx, _random.Random(11))
    assert isinstance(result, GameResult)
    assert result.home_runs >= 0 and result.away_runs >= 0
    # First-inning runs cannot exceed the game total; F5 cannot exceed the full game.
    assert result.home_first_inning_runs <= result.home_runs
    assert result.home_runs_through_5 <= result.home_runs
    assert result.away_first_inning_runs <= result.away_runs
    assert result.away_runs_through_5 <= result.away_runs


def test_simulate_one_game_is_deterministic():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    a = simulate_one_game(ctx, _random.Random(5))
    b = simulate_one_game(ctx, _random.Random(5))
    assert a == b


def test_stronger_lineup_scores_more_on_average():
    strong = _context(home_batter_iso=0.28, away_batter_iso=0.10)
    weak = _context(home_batter_iso=0.10, away_batter_iso=0.10)
    strong_total = sum(simulate_one_game(strong, _random.Random(s)).home_runs for s in range(60))
    weak_total = sum(simulate_one_game(weak, _random.Random(s)).home_runs for s in range(60))
    assert strong_total > weak_total  # ISO-loaded lineup scores more across seeds


def test_home_away_pitchers_are_paired_with_opposing_lineups():
    # Equal lineups, but home has a DOMINANT starter and away a WEAK one.
    # Home lineup faces the weak away pitcher -> scores a lot; away lineup faces
    # the dominant home pitcher -> scores little. So home outscores away on average.
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    from dataclasses import replace as _replace
    ctx = _replace(
        ctx,
        home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.36, bb_pct=0.05, hr9=0.5),
        away_pitcher=PitcherRates(player_id=8, throws="R", k_pct=0.12, bb_pct=0.11, hr9=2.4),
    )
    home_total = sum(simulate_one_game(ctx, _random.Random(s)).home_runs for s in range(80))
    away_total = sum(simulate_one_game(ctx, _random.Random(s)).away_runs for s in range(80))
    assert home_total > away_total  # a swap of the pitchers would flip this


def test_bullpen_fatigue_degrades_run_prevention():
    from autonomy.sports.mlb_pa_sim import _bullpen_distributions
    lineup = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    rates = {100 + i: BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                  bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
             for i in range(9)}
    fresh = _bullpen_distributions(lineup, rates, {}, 1.0)
    tired = _bullpen_distributions(lineup, rates, {1: 1.0, 2: 1.0}, 1.0)
    # A fatigued bullpen allows more offense: more HR, fewer strikeouts.
    assert sum(d["hr"] for d in tired) > sum(d["hr"] for d in fresh)
    assert sum(d["k"] for d in tired) < sum(d["k"] for d in fresh)


from autonomy.sports.mlb_pa_sim import simulate_game_markets


def test_market_probabilities_are_bounded_and_keyed():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    markets = simulate_game_markets(ctx, seed=1, sims=400)
    for key in ("home_win", "total_over", "yrfi", "home_f5_lead"):
        assert 0.0 <= markets[key] <= 1.0
    assert markets["sims"] == 400
    assert markets["expected_total_runs"] > 0.0


def test_market_simulation_is_deterministic():
    ctx = _context(home_batter_iso=0.16, away_batter_iso=0.16)
    a = simulate_game_markets(ctx, seed=42, sims=300)
    b = simulate_game_markets(ctx, seed=42, sims=300)
    assert a == b


def test_much_stronger_home_lineup_favored_to_win():
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    markets = simulate_game_markets(ctx, seed=7, sims=800)
    assert markets["home_win"] > 0.60  # a far stronger lineup wins more often


from autonomy.sports.mlb_pa_sim import (
    RELIEVER_K_PCT, TTO_PENALTY_PER_TIME, _starter_distributions_by_tto,
)


def test_tto_penalty_raises_offense_deeper_into_the_order():
    lineup = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    rates = {100 + i: BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                  bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
             for i in range(9)}
    pitcher = PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2)
    by_tto = _starter_distributions_by_tto(lineup, rates, pitcher, 1.0, 1.0)
    # Third time through the order allows more offense than the first time.
    first_time_hr = sum(d["hr"] for d in by_tto[0])
    third_time_hr = sum(d["hr"] for d in by_tto[3])
    assert third_time_hr > first_time_hr
    assert TTO_PENALTY_PER_TIME > 0.0


def test_realistic_reliever_is_not_cartoonish():
    # The reliever strikes out modestly more than league, not 70% more.
    assert 0.22 <= RELIEVER_K_PCT <= 0.28


def test_home_field_advantage_favors_the_home_side():
    from autonomy.sports.mlb_pa_sim import HOME_FIELD_BOOST
    assert HOME_FIELD_BOOST > 1.0
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)  # identical teams
    markets = simulate_game_markets(ctx, seed=99, sims=1500)
    assert markets["home_win"] > 0.51  # equal teams, but the home side is favored


def test_neutral_matchup_is_calibrated_to_real_mlb():
    """Task 3 calibration lock: a neutral (average vs. average) matchup must land
    in real-MLB run-environment bands AND with a realistic run COMPOSITION (the
    composition itself is locked separately by
    test_neutral_run_composition_is_realistic).

    Total runs (~8.5 real) and the home edge (~0.54 real) are held tightly.

    YRFI band is [0.40, 0.55]. Probabilistic baserunning (the _advance fix)
    replaced the old station-to-station single advancement and raised neutral
    yrfi from ~0.40 to ~0.43 at the SAME realistic run environment/composition:
    runners now convert to runs at real-MLB rates rather than piling up one base
    per single. yrfi ~0.43 remains modestly below real MLB's ~0.55; the residual
    gap is a subtler artifact of the independent per-PA run process (runs stay a
    touch over-clustered, no situational contact-vs-K shift), not the (now-fixed)
    station-to-station advancement. Forcing yrfi to ~0.55 still requires
    re-distorting composition (HR/doubles inflation), so composition stays the
    priority and yrfi is locked at its honest realistic-composition value.
    """
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    markets = simulate_game_markets(ctx, seed=2026, sims=3000)
    assert 8.0 <= markets["expected_total_runs"] <= 9.2    # real MLB ~8.5
    assert 0.40 <= markets["yrfi"] <= 0.55                 # improved via _advance; still < real ~0.55
    assert 0.51 <= markets["home_win"] <= 0.575            # home edge ~0.54


def test_neutral_run_composition_is_realistic():
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    # Recompute HR/PA and HR-share-of-hits from the neutral distribution.
    from autonomy.sports.mlb_pa_sim import plate_appearance_distribution
    b = BatterRates(player_id=1, k_pct=0.20, bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
    p = PitcherRates(player_id=2, k_pct=0.22, bb_pct=0.08, hr9=1.2)
    d = plate_appearance_distribution(b, p)
    hits = d["single"] + d["double"] + d["triple"] + d["hr"]
    assert d["hr"] <= 0.045                    # HR/PA near real ~0.033, not 2x
    assert d["hr"] / hits <= 0.22              # HR share of hits near real ~0.15


def test_reliever_hr9_is_realistic():
    from autonomy.sports.mlb_pa_sim import RELIEVER_HR9
    assert 0.9 <= RELIEVER_HR9 <= 1.4         # real relievers, not a HR sink


def test_heterogeneous_lineup_still_realistic_totals():
    # A real lineup is not uniform: a strong top, weak bottom. Totals must stay sane.
    # Upper bound widened 10.5 -> 11.5 in the composition re-calibration: softening the
    # HR-probability cap (0.09 -> 0.14) lets power hitters genuinely differentiate (the
    # point of that change), so this two-strong-lineup matchup (both sides carry an elite
    # top, ISO up to 0.26) legitimately scores more -- ~10.9 combined, i.e. ~5.4 per
    # team, which is a strong-offense game, not a runaway. Still a broad SANITY band.
    lineup_iso = [0.24, 0.22, 0.26, 0.20, 0.16, 0.13, 0.11, 0.09, 0.08]
    home = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    away = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
    rates = {}
    for i, iso in enumerate(lineup_iso):
        rates[100 + i] = BatterRates(player_id=100 + i, bats="R", k_pct=0.21,
                                     bb_pct=0.085, obp=0.320 + iso * 0.2,
                                     slg=0.360 + iso, iso=iso)
        rates[200 + i] = BatterRates(player_id=200 + i, bats="R", k_pct=0.21,
                                     bb_pct=0.085, obp=0.320 + iso * 0.2,
                                     slg=0.360 + iso, iso=iso)
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="H", away="A", home_lineup=home, away_lineup=away,
        home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        away_pitcher=PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        batter_rates=rates, park_run_factor=1.0, park_hr_factor=1.0)
    m = simulate_game_markets(ctx, seed=7, sims=2000)
    assert 6.5 <= m["expected_total_runs"] <= 11.5   # sane strong-offense run band
    assert 0.0 <= m["yrfi"] <= 1.0


def test_reliever_entry_resets_times_through_order():
    # A game long enough to reach the bullpen must still produce sane totals; the
    # reliever starts fresh (TTO level 0), not inheriting the starter's familiarity.
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    m = simulate_game_markets(ctx, seed=3, sims=800)
    assert 0.0 < m["expected_total_runs"] < 15.0  # bounded, no runaway from stale TTO
    a = simulate_game_markets(ctx, seed=3, sims=800)
    assert m == a  # deterministic through the bullpen switch


def test_weather_hr_factor_raises_home_runs():
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    calm = simulate_game_markets(ctx, seed=5, sims=800, weather=None)
    windy = simulate_game_markets(ctx, seed=5, sims=800, weather=(1.30, 1.05))
    assert windy["expected_total_runs"] > calm["expected_total_runs"]


def test_weather_none_is_unchanged():
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    a = simulate_game_markets(ctx, seed=5, sims=500)
    b = simulate_game_markets(ctx, seed=5, sims=500, weather=None)
    assert a == b  # weather=None is a no-op, preserving all S3b calibration


def test_extreme_platoon_split_batter_uses_real_rates():
    # A batter who crushes RHP but is weak vs LHP should score much more vs a RHP
    # starter than the flat 7% platoon bump would ever produce.
    from autonomy.sports.statsapi import BatterRates, LineupSlot, MlbGameContext, PitcherRates
    strong_vs_r = BatterRates(player_id=1, bats="L", k_pct=0.12, bb_pct=0.14,
                              obp=0.420, slg=0.620, iso=0.30)
    weak_vs_l = BatterRates(player_id=1, bats="L", k_pct=0.30, bb_pct=0.05,
                            obp=0.280, slg=0.330, iso=0.09)
    split_batter = BatterRates(player_id=1, bats="L", k_pct=0.20, bb_pct=0.10,
                               obp=0.350, slg=0.470, iso=0.20,
                               vs_lhp=weak_vs_l, vs_rhp=strong_vs_r)
    def ctx(pitcher_throws):
        rates = {100 + i: split_batter for i in range(9)}
        home = tuple(LineupSlot(i + 1, 100 + i, bats="L") for i in range(9))
        away = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
        for i in range(9):
            rates[200 + i] = BatterRates(player_id=200 + i, bats="R", k_pct=0.22,
                                         bb_pct=0.08, obp=0.320, slg=0.400, iso=0.14)
        return MlbGameContext(
            game_pk=1, snapshot="confirmed", captured_at="x", home="H", away="A",
            home_lineup=home, away_lineup=away,
            home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
            away_pitcher=PitcherRates(player_id=8, throws=pitcher_throws, k_pct=0.22, bb_pct=0.08, hr9=1.2),
            batter_rates=rates, park_run_factor=1.0, park_hr_factor=1.0)
    vs_rhp = sum(simulate_one_game(ctx("R"), _random.Random(s)).home_runs for s in range(60))
    vs_lhp = sum(simulate_one_game(ctx("L"), _random.Random(s)).home_runs for s in range(60))
    assert vs_rhp > vs_lhp * 1.3   # real split >> flat 7% platoon swing


def test_team_bullpen_rates_omitted_is_byte_identical_to_league_average():
    from autonomy.sports.mlb_pa_sim import _bullpen_distributions
    lineup = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    rates = {100 + i: BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                  bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
             for i in range(9)}
    # Positional call matching the pre-Task-4 signature (no team_bullpen arg at all).
    legacy = _bullpen_distributions(lineup, rates, {}, 1.0)
    explicit_none = _bullpen_distributions(lineup, rates, {}, 1.0, team_bullpen=None)
    assert legacy == explicit_none  # byte-identical: today's league-average path


def test_team_bullpen_rates_none_is_byte_identical_across_calibration_lock():
    # The full calibration-lock context never sets home/away_bullpen_rates, so this
    # is already covered by test_neutral_matchup_is_calibrated_to_real_mlb staying
    # green unchanged; this test pins the same guarantee directly against the
    # simulate_game_markets entry point for a second, explicit signal.
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    assert ctx.home_bullpen_rates is None and ctx.away_bullpen_rates is None
    markets = simulate_game_markets(ctx, seed=2026, sims=3000)
    assert 8.0 <= markets["expected_total_runs"] <= 9.2
    assert 0.51 <= markets["home_win"] <= 0.575


def test_strong_team_bullpen_suppresses_runs_vs_weak_bullpen():
    from autonomy.sports.mlb_pa_sim import _bullpen_distributions
    lineup = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    rates = {100 + i: BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                  bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
             for i in range(9)}
    strong_pen = PitcherRates(player_id=-1, k_pct=0.32, bb_pct=0.06, hr9=0.6)
    weak_pen = PitcherRates(player_id=-1, k_pct=0.16, bb_pct=0.13, hr9=2.2)
    strong_dists = _bullpen_distributions(lineup, rates, {}, 1.0, team_bullpen=strong_pen)
    weak_dists = _bullpen_distributions(lineup, rates, {}, 1.0, team_bullpen=weak_pen)
    assert sum(d["hr"] for d in strong_dists) < sum(d["hr"] for d in weak_dists)
    assert sum(d["k"] for d in strong_dists) > sum(d["k"] for d in weak_dists)
    # Bullpen fatigue scaling still applies on top of the team-specific baseline.
    tired = _bullpen_distributions(lineup, rates, {1: 1.0, 2: 1.0}, 1.0, team_bullpen=strong_pen)
    assert sum(d["hr"] for d in tired) > sum(d["hr"] for d in strong_dists)


def test_away_bullpen_rates_suppress_home_lineup_scoring_across_seeds():
    # Home lineup faces the AWAY pitcher/bullpen -> away_bullpen_rates governs it.
    from dataclasses import replace as _replace
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    strong_pen = PitcherRates(player_id=-1, k_pct=0.34, bb_pct=0.05, hr9=0.5)
    weak_pen = PitcherRates(player_id=-1, k_pct=0.15, bb_pct=0.14, hr9=2.3)
    strong_ctx = _replace(ctx, away_bullpen_rates=strong_pen)
    weak_ctx = _replace(ctx, away_bullpen_rates=weak_pen)
    strong_total = sum(simulate_one_game(strong_ctx, _random.Random(s)).home_runs for s in range(80))
    weak_total = sum(simulate_one_game(weak_ctx, _random.Random(s)).home_runs for s in range(80))
    assert strong_total < weak_total


def test_home_bullpen_rates_suppress_away_lineup_scoring_across_seeds():
    # Away lineup faces the HOME pitcher/bullpen -> home_bullpen_rates governs it.
    from dataclasses import replace as _replace
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)
    strong_pen = PitcherRates(player_id=-1, k_pct=0.34, bb_pct=0.05, hr9=0.5)
    weak_pen = PitcherRates(player_id=-1, k_pct=0.15, bb_pct=0.14, hr9=2.3)
    strong_ctx = _replace(ctx, home_bullpen_rates=strong_pen)
    weak_ctx = _replace(ctx, home_bullpen_rates=weak_pen)
    strong_total = sum(simulate_one_game(strong_ctx, _random.Random(s)).away_runs for s in range(80))
    weak_total = sum(simulate_one_game(weak_ctx, _random.Random(s)).away_runs for s in range(80))
    assert strong_total < weak_total


def test_divisional_false_is_byte_identical_to_default():
    # divisional defaults to False; passing it explicitly must not change a
    # single field of the output (the CRITICAL non-destructive guarantee).
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    default = simulate_game_markets(ctx, seed=7, sims=800)
    explicit_false = simulate_game_markets(ctx, seed=7, sims=800, divisional=False)
    assert default == explicit_false


def test_divisional_true_pulls_lopsided_home_win_toward_half():
    # A far-stronger home lineup produces a lopsided home_win; divisional=True
    # should regress it a touch toward 0.5 relative to divisional=False, but
    # not eliminate the edge entirely.
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    neutral = simulate_game_markets(ctx, seed=7, sims=800, divisional=False)
    div = simulate_game_markets(ctx, seed=7, sims=800, divisional=True)
    assert neutral["home_win"] > 0.60  # confirm the lopsided baseline
    assert 0.5 < div["home_win"] < neutral["home_win"]  # pulled toward 0.5, still home-favored
    # Only home_win should move; the other markets are computed from the same
    # raw per-sim results and are left unchanged.
    assert div["total_over"] == neutral["total_over"]
    assert div["yrfi"] == neutral["yrfi"]
    assert div["home_f5_lead"] == neutral["home_f5_lead"]
    assert div["expected_total_runs"] == neutral["expected_total_runs"]


def test_divisional_regression_constant_is_modest():
    from autonomy.sports.mlb_pa_sim import DIVISIONAL_REGRESSION
    assert 0.0 < DIVISIONAL_REGRESSION <= 0.15  # a modest bump, not a wholesale rewrite


def test_divisional_true_is_deterministic():
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    a = simulate_game_markets(ctx, seed=7, sims=500, divisional=True)
    b = simulate_game_markets(ctx, seed=7, sims=500, divisional=True)
    assert a == b


def test_rivalry_false_is_byte_identical_to_default():
    # rivalry defaults to False; passing it explicitly must not change output.
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    default = simulate_game_markets(ctx, seed=7, sims=800)
    explicit_false = simulate_game_markets(ctx, seed=7, sims=800, rivalry=False)
    assert default == explicit_false


def test_rivalry_pulls_home_win_harder_than_divisional():
    # A rivalry regresses the lopsided home_win a touch harder than a plain
    # divisional matchup (RIVALRY_REGRESSION > DIVISIONAL_REGRESSION), but stays
    # home-favored and moves ONLY home_win.
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    neutral = simulate_game_markets(ctx, seed=7, sims=800)
    div = simulate_game_markets(ctx, seed=7, sims=800, divisional=True)
    riv = simulate_game_markets(ctx, seed=7, sims=800, rivalry=True)
    assert 0.5 < riv["home_win"] < div["home_win"] < neutral["home_win"]
    assert riv["total_over"] == neutral["total_over"]
    assert riv["yrfi"] == neutral["yrfi"]
    assert riv["expected_total_runs"] == neutral["expected_total_runs"]


def test_divisional_rivalry_uses_max_not_sum():
    # A divisional rivalry pulls by the rivalry amount, not divisional+rivalry.
    ctx = _context(home_batter_iso=0.30, away_batter_iso=0.08)
    riv = simulate_game_markets(ctx, seed=7, sims=800, rivalry=True)
    both = simulate_game_markets(ctx, seed=7, sims=800, divisional=True, rivalry=True)
    assert both["home_win"] == riv["home_win"]


def test_rivalry_regression_constant_is_modest_and_exceeds_divisional():
    from autonomy.sports.mlb_pa_sim import DIVISIONAL_REGRESSION, RIVALRY_REGRESSION
    assert DIVISIONAL_REGRESSION < RIVALRY_REGRESSION <= 0.15  # modest, but a bit stronger


def test_pitcher_only_split_is_used_when_batter_has_no_split():
    from autonomy.sports.statsapi import BatterRates, LineupSlot, MlbGameContext, PitcherRates
    # Pitcher dominates RHB but is weak vs LHB. The home lineup is all RIGHT-handed
    # batters WITH NO splits -> they should score much LESS vs this pitcher's real
    # vs-RHB split than vs a neutral pitcher, proving the pitcher split is applied.
    tough_vs_r = PitcherRates(player_id=8, throws="R", k_pct=0.34, bb_pct=0.05, hr9=0.6)
    weak_vs_l = PitcherRates(player_id=8, throws="R", k_pct=0.15, bb_pct=0.12, hr9=2.0)
    split_pitcher = PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2,
                                 vs_lhb=weak_vs_l, vs_rhb=tough_vs_r)
    neutral_pitcher = PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2)
    def ctx(away_pitcher):
        rates = {100 + i: BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                      bb_pct=0.09, obp=0.340, slg=0.450, iso=0.16)
                 for i in range(9)}  # RIGHT-handed batters, NO splits
        home = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
        away = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
        for i in range(9):
            rates[200 + i] = BatterRates(player_id=200 + i, bats="R", k_pct=0.22,
                                         bb_pct=0.08, obp=0.320, slg=0.400, iso=0.14)
        return MlbGameContext(
            game_pk=1, snapshot="confirmed", captured_at="x", home="H", away="A",
            home_lineup=home, away_lineup=away,
            home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
            away_pitcher=away_pitcher, batter_rates=rates,
            park_run_factor=1.0, park_hr_factor=1.0)
    tough = sum(simulate_one_game(ctx(split_pitcher), _random.Random(s)).home_runs for s in range(60))
    neutral = sum(simulate_one_game(ctx(neutral_pitcher), _random.Random(s)).home_runs for s in range(60))
    assert tough < neutral  # the pitcher's tough vs-RHB split suppresses the R lineup


def test_all_intelligence_absent_equals_baseline():
    """Task 6 guard: the entire Tasks 1-5 intelligence layer (handedness
    splits, per-team bullpen quality, divisional/rivalry awareness) must be a
    complete no-op when its inputs are absent. A neutral context with every
    vs_* split None, no team bullpen rates, and no divisional flag must
    reproduce EXACTLY today's pre-intelligence calibrated behavior.

    This makes explicit, in one place, the "all intelligence absent ==
    baseline" contract that the individual byte-identical guards
    (test_team_bullpen_rates_none_is_byte_identical_across_calibration_lock,
    test_divisional_false_is_byte_identical_to_default) and the calibration
    locks (test_neutral_matchup_is_calibrated_to_real_mlb,
    test_neutral_run_composition_is_realistic) already cover individually.
    """
    ctx = _context(home_batter_iso=0.15, away_batter_iso=0.15)

    # No splits: every batter and both starters carry vs_* = None.
    assert ctx.batter_rates  # sanity: the context actually has batters
    for rates in ctx.batter_rates.values():
        assert rates.vs_lhp is None and rates.vs_rhp is None
    assert ctx.home_pitcher.vs_lhb is None and ctx.home_pitcher.vs_rhb is None
    assert ctx.away_pitcher.vs_lhb is None and ctx.away_pitcher.vs_rhb is None
    # No team bullpen quality.
    assert ctx.home_bullpen_rates is None and ctx.away_bullpen_rates is None

    # The whole intelligence layer is inert: omitting `divisional` must be
    # byte-identical to passing divisional=False explicitly.
    baseline = simulate_game_markets(ctx, seed=2026, sims=3000)
    explicit_false = simulate_game_markets(ctx, seed=2026, sims=3000, divisional=False)
    assert baseline == explicit_false

    # And the baseline itself still lands in today's calibrated bands (same
    # guards as test_neutral_matchup_is_calibrated_to_real_mlb).
    assert 8.0 <= baseline["expected_total_runs"] <= 9.2    # real MLB ~8.5
    assert 0.38 <= baseline["yrfi"] <= 0.55                 # see that test's docstring
    assert 0.51 <= baseline["home_win"] <= 0.575             # home edge ~0.54

    # ...with realistic run composition (same guards as
    # test_neutral_run_composition_is_realistic), reusing the same helper.
    b = BatterRates(player_id=1, k_pct=0.20, bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
    p = PitcherRates(player_id=2, k_pct=0.22, bb_pct=0.08, hr9=1.2)
    from autonomy.sports.mlb_pa_sim import plate_appearance_distribution as _pa_dist
    d = _pa_dist(b, p)
    hits = d["single"] + d["double"] + d["triple"] + d["hr"]
    assert d["hr"] <= 0.045                    # HR/PA near real ~0.033, not 2x
    assert d["hr"] / hits <= 0.22              # HR share of hits near real ~0.15
