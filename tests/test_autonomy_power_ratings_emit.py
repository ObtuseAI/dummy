"""Tests for PowerRatingsSignal (Phenon Harness WS-A2): standalone
challenger winner+spread ladder + opportunistic divergence flag.

Zero network: `consensus_fn` is injected with a fixed `ConsensusMargin` so
every test is pure math against `margin_distribution` (football) /
`win_probability_from_margin` (basketball) -- no ESPN FPI/BPI fetch, no Elo
model, ever touched here.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import (
    DISPERSION_CEILING,
    DISPERSION_UNCERTAINTY_CAP,
    DISPERSION_UNCERTAINTY_SCALE,
    DIVERGENCE_THRESHOLD,
    POWER_RATINGS_BASE_UNCERTAINTY,
    POWER_RATINGS_DEGRADED_STREAK_ENV,
    POWER_RATINGS_MODEL_VERSION,
    POWER_RATINGS_WARM_STATE_FILENAME,
    PowerRatingsSignal,
    _massey_colley_date_ranges,
)
from autonomy.sports.college import (
    margin_cover_probability as college_margin_cover_probability,
    margin_win_probability as college_margin_win_probability,
    ncaaf_margin_distribution,
)
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.nfl_margin import margin_distribution, spread_cover_probability, win_probability
from autonomy.sports.power_ratings import ConsensusMargin
from autonomy.sports.team_scores import TeamScoreModel
from autonomy.taxonomy import specialist_for

NOW = datetime(2026, 9, 13, 16, 0, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _fixed_consensus(ensemble_margin: float, dispersion: float, n_sources: int = 3):
    per_source = {f"src{i}": ensemble_margin for i in range(n_sources)}

    def _fn(home, away, league, sources):
        return ConsensusMargin(
            ensemble_margin=ensemble_margin, dispersion=dispersion,
            n_sources=n_sources, per_source=per_source,
        )
    return _fn


def _signal(league: str, home: str, away: str, consensus_fn, tmp_path,
            status: str = "pre", home_name: str | None = None,
            away_name: str | None = None) -> PowerRatingsSignal:
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    game = Game("g1", league, home, away, status, None, "2026-09-13T20:25Z",
                home_name=home_name or home, away_name=away_name or away)
    client._cache[(league, "20260913")] = [game]
    models = {"nfl": TeamScoreModel("nfl"), "ncaaf": TeamScoreModel("ncaaf"),
              "nba": TeamScoreModel("nba"), "ncaamb": TeamScoreModel("ncaamb")}
    return PowerRatingsSignal(
        espn=client, model_dir=tmp_path, elo_dir=tmp_path,
        consensus_fn=consensus_fn, models=models, elo_models={},
    )


# ---------------------------------------------------------------------------
# Emission 1: standalone challenger -- winner + spread ladder, hand-computed
# ---------------------------------------------------------------------------


def test_challenger_winner_and_spread_hand_computed_via_margin_distribution(tmp_path):
    signal = _signal(
        "nfl", "KC", "BUF", _fixed_consensus(ensemble_margin=6.0, dispersion=1.0), tmp_path,
        home_name="Kansas City Chiefs", away_name="Buffalo Bills")

    winner = signal.generate(_market("KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?"))
    assert winner is not None
    assert winner.source == "power_ratings_nfl"
    assert winner.features["challenger_only"] is True
    assert winner.features["promotion_eligible"] is True
    assert winner.features["margin_model_version"] == POWER_RATINGS_MODEL_VERSION
    assert winner.features["ensemble_margin"] == 6.0
    assert winner.features["n_sources"] == 3

    dist = margin_distribution(6.0)
    expected_winner_prob = min(0.995, max(0.005, win_probability(dist)))
    assert winner.probability_yes == pytest.approx(expected_winner_prob, abs=1e-9)

    spread = signal.generate(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-KC3",
        "Kansas City Chiefs vs Buffalo Bills Spread", floor_strike=2.5))
    assert spread is not None
    expected_cover_prob = min(0.995, max(0.005, spread_cover_probability(dist, 2.5)))
    assert spread.probability_yes == pytest.approx(expected_cover_prob, abs=1e-9)

    # Away-subject side prices the mirrored (flipped-sign) distribution.
    away_spread = signal.generate(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-BUF3",
        "Kansas City Chiefs vs Buffalo Bills Spread", floor_strike=2.5))
    assert away_spread is not None
    flipped = {-m: p for m, p in dist.items()}
    expected_away_cover = min(0.995, max(0.005, spread_cover_probability(flipped, 2.5)))
    assert away_spread.probability_yes == pytest.approx(expected_away_cover, abs=1e-9)

    # Lattice coherence: home favored -> home spread cover < home winner prob.
    assert spread.probability_yes < winner.probability_yes


def test_ncaaf_uses_college_scoring_event_kernel_not_nfl(tmp_path):
    """NCAAF power ratings route through the distinct college kernel."""
    signal = _signal(
        "ncaaf", "TEX", "OU", _fixed_consensus(ensemble_margin=6.0, dispersion=1.0), tmp_path,
        home_name="Texas Longhorns", away_name="Oklahoma Sooners")

    winner = signal.generate(_market("KXNCAAFGAME-26SEP132025TEXOU-TEX", "Texas vs Oklahoma Winner?"))
    assert winner is not None
    assert winner.source == "power_ratings_ncaaf"

    college_dist = ncaaf_margin_distribution(6.0)
    expected_winner_prob = college_margin_win_probability(college_dist)
    assert winner.probability_yes == pytest.approx(expected_winner_prob, abs=1e-9)

    # Proof the college table is actually in effect: the NFL-table ladder
    # for the identical ensemble margin gives a DIFFERENT probability.
    nfl_dist = margin_distribution(6.0)
    nfl_winner_prob = min(0.995, max(0.005, win_probability(nfl_dist)))
    assert winner.probability_yes != pytest.approx(nfl_winner_prob, abs=1e-9)

    spread = signal.generate(_market(
        "KXNCAAFSPREAD-26SEP132025TEXOU-TEX3",
        "Texas Longhorns vs Oklahoma Sooners Spread", floor_strike=2.5))
    assert spread is not None
    expected_cover_prob = college_margin_cover_probability(college_dist, 2.5)
    assert spread.probability_yes == pytest.approx(expected_cover_prob, abs=1e-9)


def test_nfl_unaffected_stays_on_default_nfl_table(tmp_path):
    """NFL keeps the module default (base_pmf=None -> BASE_ABS_MARGIN_PMF);
    only NCAAF is redirected to the college table."""
    signal = _signal(
        "nfl", "KC", "BUF", _fixed_consensus(ensemble_margin=6.0, dispersion=1.0), tmp_path,
        home_name="Kansas City Chiefs", away_name="Buffalo Bills")
    winner = signal.generate(_market("KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?"))
    assert winner is not None
    nfl_dist = margin_distribution(6.0)
    expected = min(0.995, max(0.005, win_probability(nfl_dist)))
    assert winner.probability_yes == pytest.approx(expected, abs=1e-9)


def test_challenger_basketball_uses_normal_margin_helper(tmp_path):
    from autonomy.sports.nba_model import spread_cover_probability as nba_cover, win_probability_from_margin

    signal = _signal(
        "nba", "LAL", "BOS", _fixed_consensus(ensemble_margin=5.0, dispersion=0.5), tmp_path,
        home_name="Lakers", away_name="Celtics")

    winner = signal.generate(_market("KXNBAGAME-26SEP13LALBOS-LAL", "Lakers vs Celtics Winner?"))
    assert winner is not None
    assert winner.source == "power_ratings_nba"
    from autonomy.signals.sports_intelligence import POWER_RATINGS_BASKETBALL_SIGMA
    expected = min(0.995, max(0.005, win_probability_from_margin(5.0, POWER_RATINGS_BASKETBALL_SIGMA)))
    assert winner.probability_yes == pytest.approx(expected, abs=1e-9)

    spread = signal.generate(_market(
        "KXNBASPREAD-26SEP13LALBOS-LAL2", "Lakers vs Celtics Spread", floor_strike=1.5))
    assert spread is not None
    expected_cover = min(0.995, max(
        0.005, nba_cover(5.0, POWER_RATINGS_BASKETBALL_SIGMA, 1.5)))
    assert spread.probability_yes == pytest.approx(expected_cover, abs=1e-9)


# ---------------------------------------------------------------------------
# Emission 1: dispersion widens uncertainty only, mean byte-identical
# ---------------------------------------------------------------------------


def test_dispersion_widens_uncertainty_not_mean(tmp_path):
    low = _signal(
        "nfl", "KC", "BUF", _fixed_consensus(ensemble_margin=6.0, dispersion=0.0), tmp_path)
    high = _signal(
        "nfl", "KC", "BUF", _fixed_consensus(ensemble_margin=6.0, dispersion=9.0), tmp_path)
    # 9.0 dispersion is below the point where DISPERSION_UNCERTAINTY_SCALE *
    # dispersion would clear DISPERSION_UNCERTAINTY_CAP -- picked so this
    # case exercises the un-capped branch of the widen formula.
    assert DISPERSION_UNCERTAINTY_SCALE * 9.0 < DISPERSION_UNCERTAINTY_CAP

    market = _market("KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?")
    low_signal = low.generate(market)
    high_signal = high.generate(market)
    assert low_signal is not None and high_signal is not None

    # Mean (probability_yes) is byte-identical regardless of dispersion.
    assert low_signal.probability_yes == high_signal.probability_yes

    # Uncertainty widens, bounded/capped.
    assert high_signal.uncertainty > low_signal.uncertainty
    assert low_signal.uncertainty == pytest.approx(POWER_RATINGS_BASE_UNCERTAINTY, abs=1e-9)
    assert high_signal.uncertainty == pytest.approx(
        POWER_RATINGS_BASE_UNCERTAINTY + DISPERSION_UNCERTAINTY_SCALE * 9.0, abs=1e-9)

    # A dispersion far beyond the cap widens no further than the cap.
    huge = _signal(
        "nfl", "KC", "BUF", _fixed_consensus(ensemble_margin=6.0, dispersion=999.0), tmp_path)
    huge_signal = huge.generate(market)
    assert huge_signal is not None
    assert huge_signal.uncertainty == pytest.approx(
        POWER_RATINGS_BASE_UNCERTAINTY + DISPERSION_UNCERTAINTY_CAP, abs=1e-9)
    assert huge_signal.uncertainty > high_signal.uncertainty


# ---------------------------------------------------------------------------
# Emission 2: opportunistic divergence flag gating
# ---------------------------------------------------------------------------


def _our_engine_margin_nfl() -> float:
    # Cold TeamScoreModel("nfl") margin == home_edge_points == 2.0 exactly
    # (both teams sit at the identical prior, so the only asymmetry is the
    # home-edge split -- see team_scores.py::TeamScoreModel.predict).
    return 2.0


def test_divergence_flag_fires_only_on_large_gap_and_low_dispersion(tmp_path):
    market = _market("KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?")
    our_margin = _our_engine_margin_nfl()
    threshold = DIVERGENCE_THRESHOLD["nfl"]
    ceiling = DISPERSION_CEILING["nfl"]

    # Large gap, low dispersion -> fires.
    fires = _signal(
        "nfl", "KC", "BUF",
        _fixed_consensus(ensemble_margin=our_margin + threshold + 4.0, dispersion=ceiling - 1.0),
        tmp_path,
    )
    fired_signal = fires.generate(market)
    assert fired_signal is not None
    divergence = fired_signal.features["power_divergence"]
    assert divergence is not None
    assert divergence["gap"] == pytest.approx(threshold + 4.0, abs=1e-6)
    assert divergence["ensemble_margin"] == pytest.approx(our_margin + threshold + 4.0)
    assert divergence["our_engine_margin"] == pytest.approx(our_margin)
    assert divergence["kalshi_mid"] == pytest.approx(0.45)  # (44+46)/2/100

    # Large gap, HIGH dispersion -> suppressed even though the gap is identical.
    suppressed = _signal(
        "nfl", "KC", "BUF",
        _fixed_consensus(ensemble_margin=our_margin + threshold + 4.0, dispersion=ceiling + 5.0),
        tmp_path,
    )
    suppressed_signal = suppressed.generate(market)
    assert suppressed_signal is not None
    assert suppressed_signal.features["power_divergence"] is None

    # Small gap, low dispersion -> no flag (gap doesn't clear the bar).
    small_gap = _signal(
        "nfl", "KC", "BUF",
        _fixed_consensus(ensemble_margin=our_margin + threshold - 1.0, dispersion=0.0),
        tmp_path,
    )
    small_gap_signal = small_gap.generate(market)
    assert small_gap_signal is not None
    assert small_gap_signal.features["power_divergence"] is None


# ---------------------------------------------------------------------------
# Fail-closed: consensus_margin None -> no signal at all
# ---------------------------------------------------------------------------


def test_consensus_none_emits_no_signal_byte_identical_to_disabled(tmp_path):
    def _none_consensus(home, away, league, sources):
        return None

    signal = _signal("nfl", "KC", "BUF", _none_consensus, tmp_path)
    winner = signal.generate(_market("KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?"))
    assert winner is None

    spread = signal.generate(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-KC3", "Chiefs vs Bills Spread", floor_strike=2.5))
    assert spread is None


def test_live_game_never_emits_pre_game_only_gate(tmp_path):
    # Pre-game-only first pass (see class docstring / WS-A2 brief): a live
    # game must never emit, regardless of consensus.
    signal = _signal(
        "nfl", "KC", "BUF", _fixed_consensus(ensemble_margin=6.0, dispersion=1.0), tmp_path,
        status="in",
    )
    winner = signal.generate(_market("KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?"))
    assert winner is None


# ---------------------------------------------------------------------------
# Taxonomy routing: real specialist_for path, not hand-built
# ---------------------------------------------------------------------------


def test_specialist_for_routes_power_ratings_sources_per_league():
    assert specialist_for("power_ratings_nfl") == "nfl"
    assert specialist_for("power_ratings_ncaaf") == "ncaaf"
    assert specialist_for("power_ratings_nba") == "nba"
    assert specialist_for("power_ratings_ncaamb") == "ncaamb"


def test_challenger_signal_source_routes_through_real_taxonomy(tmp_path):
    # End-to-end: the ACTUAL emitted Signal.source resolves via the real
    # taxonomy path, not a hand-built string.
    signal = _signal(
        "ncaamb", "DUKE", "UNC", _fixed_consensus(ensemble_margin=4.0, dispersion=1.0), tmp_path)
    winner = signal.generate(_market("KXNCAAMBGAME-26SEP132025DUKEUNC-DUKE", "Duke vs UNC Winner?"))
    assert winner is not None
    assert specialist_for(winner.source) == "ncaamb"


# ---------------------------------------------------------------------------
# CF2: Massey/Colley re-warm on cadence (throttled) in on_cycle_start
# ---------------------------------------------------------------------------


def _owned_signal(tmp_path) -> PowerRatingsSignal:
    """A signal that CONSTRUCTED its own (empty, no-network) Massey/Colley."""
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    models = {lg: TeamScoreModel(lg) for lg in ("nfl", "ncaaf", "nba", "ncaamb")}
    return PowerRatingsSignal(
        espn=client, model_dir=tmp_path, elo_dir=tmp_path,
        consensus_fn=_fixed_consensus(ensemble_margin=3.0, dispersion=1.0),
        models=models, elo_models={},
    )


def test_owned_massey_colley_rewarm_after_ttl(tmp_path):
    signal = _owned_signal(tmp_path)
    assert signal._owns_massey and signal._owns_colley
    # Warmed once at construction; the timestamp is set.
    assert signal._last_massey_colley_warm is not None

    calls = {"n": 0}
    signal._warm_massey_colley = lambda **kw: calls.__setitem__("n", calls["n"] + 1)  # type: ignore[method-assign]

    # Last warm is stale (> TTL ago) -> on_cycle_start re-warms and advances ts.
    stale = datetime.now(timezone.utc) - timedelta(hours=13)
    signal._last_massey_colley_warm = stale
    signal.on_cycle_start()
    assert calls["n"] == 1
    assert signal._last_massey_colley_warm > stale


def test_owned_massey_colley_not_rewarmed_within_ttl(tmp_path):
    signal = _owned_signal(tmp_path)
    calls = {"n": 0}
    signal._warm_massey_colley = lambda **kw: calls.__setitem__("n", calls["n"] + 1)  # type: ignore[method-assign]

    fresh = datetime.now(timezone.utc) - timedelta(hours=1)
    signal._last_massey_colley_warm = fresh
    signal.on_cycle_start()
    assert calls["n"] == 0            # inside TTL -> no re-solve
    assert signal._last_massey_colley_warm == fresh


def test_injected_massey_colley_never_rewarmed(tmp_path):
    # Injected sources are trusted as already-warm and never touched.
    class _Spy:
        def __init__(self) -> None:
            self.warmups = 0

        def warmup(self, league, date_ranges):
            self.warmups += 1

        def rating(self, league, team):
            return None

        def points_per_unit(self, league):
            return None

    massey, colley = _Spy(), _Spy()
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    models = {lg: TeamScoreModel(lg) for lg in ("nfl", "ncaaf", "nba", "ncaamb")}
    signal = PowerRatingsSignal(
        espn=client, model_dir=tmp_path, elo_dir=tmp_path,
        consensus_fn=_fixed_consensus(ensemble_margin=3.0, dispersion=1.0),
        models=models, elo_models={}, massey_source=massey, colley_source=colley,
    )
    assert not signal._owns_massey and not signal._owns_colley
    assert signal._last_massey_colley_warm is None
    signal._last_massey_colley_warm = None  # even with no recorded warm...
    signal.on_cycle_start()               # ...injected sources are left alone
    assert massey.warmups == 0
    assert colley.warmups == 0


# ---------------------------------------------------------------------------
# Warm outcome triage + degraded-streak telemetry. Root cause of the ~800/day
# "warmup produced no ratings" WARNING spam (2026-07): a preseason-woken
# league (season gate wakes on SCHEDULED games up to 21 days ahead; NFL woke
# 2026-07-20) has ZERO settled games inside the trailing 120-day
# Massey/Colley window, and production constructs a fresh PowerRatingsSignal
# every ~5-min cycle (build_brain in run_one_cycle), re-running the
# construction-time warm each time. The empty-window drop is the correct
# fail-closed outcome and now logs at DEBUG; a persisted per-league streak
# counter emits one loud POWER_RATINGS_DEGRADED_STREAK line every N degraded
# warms instead.
# ---------------------------------------------------------------------------


class _OneActiveSeason:
    """Season-gate stub: exactly one league active, no network, no state IO."""

    def __init__(self, league: str) -> None:
        self.league = league

    def active(self, league: str) -> bool:
        return league == self.league


def _settled_nfl(game_id: str, home: str, away: str, home_score: int, away_score: int) -> Game:
    return Game(
        game_id, "nfl", home, away, "post", home_score > away_score,
        "2026-07-01T20:00Z", home_score=home_score, away_score=away_score,
    )


def _settled_round_robin() -> list[Game]:
    """4 real NFL teams, full round-robin: every team has 3 settled games
    (>= ratings_solvers.MIN_GAMES_PER_TEAM, so .rating() must return values)."""
    return [
        _settled_nfl("g1", "KC", "BUF", 27, 20),
        _settled_nfl("g2", "KC", "DAL", 31, 17),
        _settled_nfl("g3", "PHI", "KC", 24, 21),
        _settled_nfl("g4", "BUF", "DAL", 28, 14),
        _settled_nfl("g5", "BUF", "PHI", 23, 22),
        _settled_nfl("g6", "DAL", "PHI", 13, 30),
    ]


def _warm_signal(tmp_path, games: list[Game] | None = None) -> PowerRatingsSignal:
    """Owned-source signal warming through a hermetic ESPN client: the first
    warm-window chunk serves ``games``, every other fetch parses to []."""
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    if games:
        first_range = _massey_colley_date_ranges()[0]
        client._cache[("nfl", first_range)] = list(games)
    models = {lg: TeamScoreModel(lg) for lg in ("nfl", "ncaaf", "nba", "ncaamb")}
    return PowerRatingsSignal(
        espn=client, model_dir=tmp_path, elo_dir=tmp_path,
        consensus_fn=_fixed_consensus(ensemble_margin=3.0, dispersion=1.0),
        models=models, elo_models={}, seasons=_OneActiveSeason("nfl"),
    )


@pytest.fixture
def quiet_log_sink():
    """Detach the real jsonl sink (logs/dummy.jsonl) for log-assertion tests;
    caplog still captures via propagation to the root logger."""
    from core.logger import logger as dummy_logger

    saved = dummy_logger.handlers[:]
    dummy_logger.handlers = []
    yield
    dummy_logger.handlers = saved


def _warm_state(tmp_path) -> dict:
    path = tmp_path / POWER_RATINGS_WARM_STATE_FILENAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("degraded_streaks", {})


def test_warm_with_settled_games_produces_ratings_quietly(tmp_path, caplog, quiet_log_sink):
    caplog.set_level(logging.DEBUG, logger="dummy")
    signal = _warm_signal(tmp_path, games=_settled_round_robin())

    assert signal.massey_source._ratings["nfl"]
    assert signal.colley_source._ratings["nfl"]
    assert signal.massey_source.rating("nfl", "KC") is not None
    assert signal.colley_source.rating("nfl", "KC") is not None
    # No drop, no streak: nothing above DEBUG, and no degraded state on disk.
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert "dropped from ensemble" not in caplog.text
    assert _warm_state(tmp_path) == {}


def test_warm_empty_window_skips_quietly_without_warning(tmp_path, caplog, quiet_log_sink):
    """The preseason-wake state (gate active, zero settled games in window)
    must be a clean DEBUG skip, not the old per-cycle WARNING."""
    caplog.set_level(logging.DEBUG, logger="dummy")
    signal = _warm_signal(tmp_path, games=None)

    assert signal.massey_source._ratings["nfl"] == {}
    assert signal.colley_source._ratings["nfl"] == {}
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert "produced no ratings" not in caplog.text  # the old noisy line is gone
    debug_lines = [
        r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
    ]
    assert any(
        "no settled games" in line and "nfl" in line for line in debug_lines
    )
    # The degraded streak advanced (one warm = one degraded cycle).
    assert _warm_state(tmp_path) == {"nfl": 1}


def test_degraded_streak_emits_loud_line_every_n(tmp_path, caplog, quiet_log_sink, monkeypatch):
    monkeypatch.setenv(POWER_RATINGS_DEGRADED_STREAK_ENV, "3")
    caplog.set_level(logging.DEBUG, logger="dummy")
    signal = _warm_signal(tmp_path, games=None)  # streak 1 (construction warm)
    signal._warm_massey_colley()                 # streak 2
    assert "POWER_RATINGS_DEGRADED_STREAK" not in caplog.text
    signal._warm_massey_colley()                 # streak 3 -> emit
    warnings = [
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ]
    assert warnings.count("POWER_RATINGS_DEGRADED_STREAK league=nfl n=3") == 1
    assert _warm_state(tmp_path) == {"nfl": 3}

    for _ in range(3):                           # streaks 4, 5, 6 -> emit at 6
        signal._warm_massey_colley()
    warnings = [
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ]
    assert warnings.count("POWER_RATINGS_DEGRADED_STREAK league=nfl n=6") == 1
    assert _warm_state(tmp_path) == {"nfl": 6}


def test_degraded_streak_resets_on_healthy_warm(tmp_path, caplog, quiet_log_sink):
    (tmp_path / POWER_RATINGS_WARM_STATE_FILENAME).write_text(
        json.dumps({"degraded_streaks": {"nfl": 7, "nba": 2}}), encoding="utf-8")
    caplog.set_level(logging.DEBUG, logger="dummy")
    _warm_signal(tmp_path, games=_settled_round_robin())
    # nfl warmed healthy -> reset (dropped from the file); nba was skipped by
    # the season gate -> its streak is frozen, neither grown nor reset.
    assert _warm_state(tmp_path) == {"nba": 2}
    assert "POWER_RATINGS_DEGRADED_STREAK" not in caplog.text


def test_warmup_exception_is_logged_with_class_and_message(tmp_path, caplog, quiet_log_sink):
    """A raising warmup is no longer silently swallowed: the exception class
    and message reach the log (and the league still counts as degraded)."""
    caplog.set_level(logging.DEBUG, logger="dummy")
    signal = _warm_signal(tmp_path, games=_settled_round_robin())
    assert _warm_state(tmp_path) == {}

    def _boom(league, date_ranges):
        raise ValueError("scoreboard exploded")

    signal.massey_source.warmup = _boom  # type: ignore[method-assign]
    signal._warm_massey_colley(warm_massey=True, warm_colley=False)

    warnings = [
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ]
    assert any(
        "massey warmup failed for nfl" in line
        and "ValueError" in line
        and "scoreboard exploded" in line
        for line in warnings
    )
    assert _warm_state(tmp_path) == {"nfl": 1}


def test_solver_failure_with_settled_games_stays_loud(tmp_path, caplog, quiet_log_sink, monkeypatch):
    """Settled games present but the solve yields nothing (non-convergence):
    abnormal -> still a WARNING, distinct from the quiet empty-window skip."""
    import autonomy.sports.ratings_solvers as ratings_solvers

    monkeypatch.setattr(ratings_solvers, "solve_spd", lambda *a, **k: None)
    caplog.set_level(logging.DEBUG, logger="dummy")
    _warm_signal(tmp_path, games=_settled_round_robin())

    warnings = [
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ]
    assert any(
        "massey warmup solved no ratings for nfl despite settled games" in line
        for line in warnings
    )
    assert any(
        "colley warmup solved no ratings for nfl despite settled games" in line
        for line in warnings
    )
    assert _warm_state(tmp_path) == {"nfl": 1}
