"""Tests for WS-7: situational-awareness engine (rest / playoff context /
suspensions / roster-drift), across engines.

Zero network: every fixture below is hand-built in-memory, mirroring
tests/test_autonomy_players.py and tests/test_autonomy_nhl_model.py's own
conventions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
from autonomy.sports.boxscores import BoxscoreStore, TeamBoxscore
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.nhl_model import NhlModel
from autonomy.sports.players import LeagueInjuryBook, RookieBook, classify_status
from autonomy.sports.situations import (
    CLINCH_UNCERTAINTY,
    MUST_WIN_GAMES_REMAINING,
    NFL_BYE_ADJUSTMENT,
    NFL_BYE_MIN_DAYS,
    NFL_SHORT_WEEK_ADJUSTMENT,
    NHL_B2B_ADJUSTMENT,
    ROSTER_EVENT_UNCERTAINTY,
    GameDateTracker,
    PlayoffBook,
    PlayoffState,
    RosterDriftBook,
    nfl_rest_effect,
    nfl_team_rest_state,
    nhl_rest_effect,
    nhl_team_rest_state,
    parse_standings,
    playoff_soft_effect,
    rest_days_since,
    roster_athlete_ids,
    roster_drift,
    roster_hash,
    roster_soft_effect,
)

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(days=2)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56, volume=500, liquidity=1_000,
        raw=payload,
    )


# =========================================================================
# rest_days_since / GameDateTracker
# =========================================================================


def test_rest_days_since_basic_and_no_history():
    assert rest_days_since(["2026-09-06"], "2026-09-10") == 4
    assert rest_days_since([], "2026-09-10") is None
    assert rest_days_since(["not-a-date"], "2026-09-10") is None


def test_game_date_tracker_records_only_settled_games_and_is_idempotent():
    tracker = GameDateTracker(league="nfl")
    pre_game = Game("g1", "nfl", "KC", "BUF", "pre", None, "2026-09-10T20:00:00Z")
    assert tracker.update(pre_game) is False
    assert tracker.recent_dates("KC") == []

    post_game = Game("g1", "nfl", "KC", "BUF", "post", True, "2026-09-10T20:00:00Z")
    assert tracker.update(post_game) is True
    assert tracker.recent_dates("KC") == ["2026-09-10"]
    assert tracker.recent_dates("BUF") == ["2026-09-10"]
    # Idempotent by game_id: reprocessing the same settled game is a no-op.
    assert tracker.update(post_game) is False
    assert tracker.recent_dates("KC") == ["2026-09-10"]


def test_game_date_tracker_persists_round_trip(tmp_path):
    tracker = GameDateTracker(league="nhl")
    tracker.update(Game("g1", "nhl", "BOS", "TOR", "post", True, "2026-01-05T20:00:00Z"))
    path = tmp_path / "rest_nhl.json"
    tracker.save(path)
    loaded = GameDateTracker.load(path, league="nhl")
    assert loaded.recent_dates("BOS") == ["2026-01-05"]
    assert loaded.processed_game_ids == {"g1"}


def test_game_date_tracker_load_missing_file_is_empty(tmp_path):
    loaded = GameDateTracker.load(tmp_path / "does_not_exist.json", league="nfl")
    assert loaded.recent_dates("KC") == []


# =========================================================================
# NFL bye / Thursday short-week (HARD, bounded mean adjust)
# =========================================================================


def test_nfl_bye_adjustment_applies_either_side():
    # 2026-09-27 is a Sunday; last game 2026-09-13 -> 14 days, a bye.
    adjustment, features = nfl_team_rest_state(["2026-09-13"], "2026-09-27", is_home=True)
    assert adjustment == NFL_BYE_ADJUSTMENT
    assert features["bye"] is True
    assert features["thursday_short_week"] is False

    adjustment_away, features_away = nfl_team_rest_state(["2026-09-13"], "2026-09-27", is_home=False)
    assert adjustment_away == NFL_BYE_ADJUSTMENT
    assert features_away["bye"] is True


def test_nfl_bye_does_not_fire_on_a_normal_week():
    adjustment, features = nfl_team_rest_state(["2026-09-20"], "2026-09-27", is_home=True)
    assert adjustment == 0.0
    assert features["bye"] is False
    assert features["rest_days"] == 7


def test_nfl_thursday_short_week_applies_road_team_only():
    # 2026-09-10 is a Thursday; last game 2026-09-06 (Sunday) -> 4 days rest.
    away_adjustment, away_features = nfl_team_rest_state(["2026-09-06"], "2026-09-10", is_home=False)
    assert away_adjustment == NFL_SHORT_WEEK_ADJUSTMENT
    assert away_features["thursday_short_week"] is True

    # THE key rule: the HOME team on the exact same short week gets NO
    # penalty, full stop -- brief's explicit carve-out.
    home_adjustment, home_features = nfl_team_rest_state(["2026-09-06"], "2026-09-10", is_home=True)
    assert home_adjustment == 0.0
    assert home_features["thursday_short_week"] is False


def test_nfl_short_week_requires_thursday():
    # Same 4-day rest gap, but the game itself isn't on a Thursday (Sunday).
    adjustment, features = nfl_team_rest_state(["2026-09-09"], "2026-09-13", is_home=False)
    assert adjustment == 0.0
    assert features["thursday_short_week"] is False


def test_nfl_rest_effect_combines_both_sides_and_logs_features():
    effect = nfl_rest_effect(
        home_recent_dates=["2026-09-03"],   # 7 days -> normal week, no effect
        away_recent_dates=["2026-09-06"],   # 4 days -> short week (away only)
        game_date="2026-09-10",             # Thursday
    )
    # home_adj(0.0) - away_adj(-1.5) = +1.5
    assert effect.margin_delta == pytest.approx(1.5)
    assert effect.features["nfl_rest_away_thursday_short_week"] is True
    assert effect.features["nfl_rest_home_thursday_short_week"] is False
    assert effect.features["nfl_rest_margin_delta"] == pytest.approx(1.5)


def test_nfl_rest_effect_no_history_is_zero_no_op():
    effect = nfl_rest_effect([], [], "2026-09-10")
    assert effect.margin_delta == 0.0
    assert effect.features["nfl_rest_home_rest_days"] is None
    assert effect.features["nfl_rest_away_rest_days"] is None


# =========================================================================
# NHL back-to-back (HARD, bounded mean adjust)
# =========================================================================


def test_nhl_b2b_adjustment_fires_at_exactly_one_day_rest():
    adjustment, features = nhl_team_rest_state(["2026-01-04"], "2026-01-05")
    assert adjustment == NHL_B2B_ADJUSTMENT
    assert features["b2b"] is True

    adjustment_normal, features_normal = nhl_team_rest_state(["2026-01-02"], "2026-01-05")
    assert adjustment_normal == 0.0
    assert features_normal["b2b"] is False


def test_nhl_rest_effect_combines_and_no_history_is_zero():
    effect = nhl_rest_effect(["2026-01-04"], ["2026-01-01"], "2026-01-05")
    # home on b2b (-0.8), away rested (0.0) -> margin_delta = -0.8 - 0.0
    assert effect.margin_delta == pytest.approx(NHL_B2B_ADJUSTMENT)
    assert nhl_rest_effect([], [], "2026-01-05").margin_delta == 0.0


# =========================================================================
# Playoff context: parse_standings + playoff_soft_effect (SOFT, widen-only)
# =========================================================================


def _standings_payload(entries: list[tuple[str, float, float, str | None, float]]) -> dict:
    """entries: (abbr, wins, losses, clincher_description_or_None, games_behind)."""
    stats_entries = []
    for abbr, wins, losses, clincher_description, games_behind in entries:
        stats = [
            {"name": "wins", "value": wins},
            {"name": "losses", "value": losses},
            {"name": "gamesBehind", "value": games_behind},
        ]
        if clincher_description is not None:
            stats.append({"name": "clincher", "description": clincher_description, "displayValue": "x"})
        stats_entries.append({"team": {"abbreviation": abbr}, "stats": stats})
    return {"children": [{"standings": {"entries": stats_entries}}]}


def test_parse_standings_clinched_and_eliminated_late_season():
    # NFL: 17-game season: 15 games played (>= 75% of 17) is late season.
    payload = _standings_payload([
        ("KC", 14.0, 1.0, "Clinched Playoff Berth", 0.0),
        ("DEN", 3.0, 12.0, "Eliminated From Playoff", 11.0),
        ("BUF", 8.0, 7.0, None, 2.0),  # no clincher stat's description -> undecided
    ])
    parsed = parse_standings("nfl", payload)
    assert parsed["KC"].clinched is True
    assert parsed["KC"].eliminated is False
    assert parsed["DEN"].eliminated is True
    assert parsed["DEN"].clinched is False


def test_parse_standings_early_season_never_clinches_even_with_clincher_stat():
    # Only 3 games played of 17 -- nowhere near LATE_SEASON_GAMES_PLAYED_FRACTION.
    payload = _standings_payload([("KC", 3.0, 0.0, "Clinched Playoff Berth", 0.0)])
    parsed = parse_standings("nfl", payload)
    assert parsed["KC"].clinched is False
    assert parsed["KC"].eliminated is False


def test_parse_standings_must_win_flag():
    # Late season, alive, few games left, mathematically still in it. A
    # present-but-neutral clincher stat (undecided -- not yet clinched or
    # eliminated), same shape a real mid-race team would carry.
    payload = _standings_payload([("BUF", 14.0, 2.0, "", 1.0)])  # 16/17 played, 1 GB, 1 remaining
    parsed = parse_standings("nfl", payload)
    assert parsed["BUF"].games_remaining == 1
    assert parsed["BUF"].clinched is False
    assert parsed["BUF"].eliminated is False
    assert parsed["BUF"].must_win is True


def test_parse_standings_no_clincher_stat_is_all_false_ncaaf_ncaamb_shape():
    """NCAAF/NCAAMB carry real standings but no `clincher` stat at all (see
    situations.py's module docstring probe #1) -- must resolve to the exact
    same all-False shape as a dead feed, no special-casing."""
    payload = {"children": [{"standings": {"entries": [
        {"team": {"abbreviation": "OSU"}, "stats": [
            {"name": "wins", "value": 10.0}, {"name": "losses", "value": 1.0},
        ]},
    ]}}]}
    parsed = parse_standings("ncaaf", payload)
    assert parsed["OSU"] == PlayoffState(clinched=False, eliminated=False, must_win=False,
                                          games_played=None, games_remaining=None)


def test_parse_standings_malformed_payload_is_empty():
    assert parse_standings("nfl", None) == {}
    assert parse_standings("nfl", {}) == {}
    assert parse_standings("nfl", {"children": []}) == {}


def test_playoff_book_fail_closed_on_fetch_error_and_zero_until_refreshed():
    def boom():
        raise RuntimeError("espn down")

    book = PlayoffBook("nfl", fetch_fn=boom)
    assert book.for_team("KC") == PlayoffState()  # never refreshed -> default
    book.refresh()
    assert book.for_team("KC") == PlayoffState()  # refresh failed -> still empty


def test_playoff_soft_effect_widens_uncertainty_only_never_a_mean():
    baseline = playoff_soft_effect(PlayoffState(), PlayoffState())
    assert baseline.uncertainty_add == 0.0

    clinched_home = playoff_soft_effect(PlayoffState(clinched=True), PlayoffState())
    assert clinched_home.uncertainty_add == pytest.approx(CLINCH_UNCERTAINTY)

    eliminated_both = playoff_soft_effect(
        PlayoffState(eliminated=True), PlayoffState(clinched=True))
    assert eliminated_both.uncertainty_add == pytest.approx(2 * CLINCH_UNCERTAINTY)
    # SoftEffect structurally carries NO margin/mean field at all -- the
    # dataclass itself enforces "widen only" by construction.
    assert not hasattr(eliminated_both, "margin_delta")


# =========================================================================
# Roster-hash drift proxy (SOFT, widen-only)
# =========================================================================


def _roster_payload(ids: list[str]) -> dict:
    return {"athletes": [{"position": "offense", "items": [{"id": i} for i in ids]}]}


def test_roster_athlete_ids_and_hash_are_order_independent():
    ids_a = roster_athlete_ids(_roster_payload(["1", "2", "3"]))
    ids_b = roster_athlete_ids(_roster_payload(["3", "1", "2"]))
    assert ids_a == ids_b == {"1", "2", "3"}
    assert roster_hash(ids_a) == roster_hash(ids_b)


def test_roster_drift_first_cycle_is_zero_no_prior_hash():
    """Brief's exact key test: on the FIRST cycle there is no prior snapshot
    to diff against -- zero effect, fail-closed."""
    assert roster_drift(None, {"1", "2", "3"}) is False


def test_roster_drift_small_change_does_not_trigger():
    previous = {str(i) for i in range(1, 54)}  # 53-man roster
    current = set(previous)
    current.discard("1")
    current.add("999")  # one swap out of 53 -- routine churn
    assert roster_drift(previous, current) is False


def test_roster_drift_large_change_triggers():
    previous = {str(i) for i in range(1, 20)}
    current = {str(i) for i in range(10, 40)}  # >20% of the union changed
    assert roster_drift(previous, current) is True


def test_roster_drift_book_first_cycle_zero_then_detects_large_diff(tmp_path):
    fetch_teams = lambda _l: {"sports": [{"leagues": [{"teams": [
        {"team": {"abbreviation": "SF", "id": "25"}},
    ]}]}]}
    rosters = [_roster_payload([str(i) for i in range(1, 20)])]

    def fetch_roster(_league, _team_id):
        return rosters[0]

    book = RosterDriftBook("nfl", fetch_teams=fetch_teams, fetch_roster=fetch_roster)
    book.refresh(["SF"])
    first_cycle = book.event_for("SF")
    assert first_cycle["roster_event"] is False  # no prior snapshot yet

    # Second cycle: overhaul the roster (>20% turnover).
    rosters[0] = _roster_payload([str(i) for i in range(10, 40)])
    book.refresh(["SF"])
    second_cycle = book.event_for("SF")
    assert second_cycle["roster_event"] is True
    assert second_cycle["roster_diff_count"] > 0

    # Persistence round trip preserves the prior snapshot across a restart.
    path = tmp_path / "roster_nfl.json"
    book.save(path)
    reloaded = RosterDriftBook.load(path, league="nfl", fetch_teams=fetch_teams, fetch_roster=fetch_roster)
    assert reloaded.previous_ids["SF"] == sorted(str(i) for i in range(10, 40))


def test_roster_drift_book_respects_fetch_budget():
    fetch_teams = lambda _l: {"sports": [{"leagues": [{"teams": [
        {"team": {"abbreviation": t, "id": str(i)}} for i, t in enumerate(["A", "B", "C"])
    ]}]}]}
    fetched: list[str] = []

    def fetch_roster(_league, team_id):
        fetched.append(team_id)
        return _roster_payload(["1", "2"])

    book = RosterDriftBook("nfl", fetch_teams=fetch_teams, fetch_roster=fetch_roster, fetch_budget=1)
    book.refresh(["A", "B", "C"])
    assert len(fetched) == 1


def test_roster_drift_book_fail_closed_on_fetch_error():
    def boom_teams(_l):
        raise RuntimeError("down")

    book = RosterDriftBook("nfl", fetch_teams=boom_teams, fetch_roster=lambda _l, _t: {})
    book.refresh(["SF"])
    assert book.event_for("SF") == {"roster_event": False, "roster_diff_count": 0, "roster_size": None}


def test_roster_soft_effect_widens_uncertainty_only():
    baseline = roster_soft_effect({}, {})
    assert baseline.uncertainty_add == 0.0
    home_event = roster_soft_effect({"roster_event": True}, {})
    assert home_event.uncertainty_add == pytest.approx(ROSTER_EVENT_UNCERTAINTY)
    both = roster_soft_effect({"roster_event": True}, {"roster_event": True})
    assert both.uncertainty_add == pytest.approx(2 * ROSTER_EVENT_UNCERTAINTY)
    assert not hasattr(both, "margin_delta")


# =========================================================================
# Suspensions: route through WS-6's existing hard-Out path
# =========================================================================


def test_classify_status_suspension_routes_to_hard():
    assert classify_status("Suspension") == "hard"
    assert classify_status("suspension") == "hard"
    assert classify_status("Suspended") == "hard"
    # Existing WS-6 classifications must stay byte-identical.
    assert classify_status("Out") == "hard"
    assert classify_status("Questionable") == "soft"
    assert classify_status("Injured Reserve") is None
    assert classify_status("Active") is None


# =========================================================================
# Engine wiring: autonomy/signals/sports_intelligence.py
# =========================================================================

NFL_NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


def _nfl_game(game_date: str = "2026-09-10T20:00:00Z") -> Game:
    return Game(
        game_id="nfl1", league="nfl", home="KC", away="BUF", status="pre", home_won=None,
        date=game_date, home_name="Kansas City Chiefs", away_name="Buffalo Bills",
    )


def _nfl_market_fixture() -> MarketView:
    return _market("KXNFLGAME-26SEP10KCBUF-KC", "Kansas City vs Buffalo Winner?")


def _nfl_signal(
    tmp_path, nfl_rest_tracker=None, playoff_books=None, roster_drift_books=None,
) -> TeamSportsIntelligenceSignal:
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("nfl", "20260910")] = [_nfl_game()]
    injury_books = {"nfl": LeagueInjuryBook("nfl", fetch_fn=lambda: {"injuries": []})}
    injury_books["nfl"].refresh()
    return TeamSportsIntelligenceSignal(
        espn=client, model_dir=tmp_path, injury_books=injury_books,
        rookie_book=RookieBook("nfl", fetch_teams=lambda _l: {}, fetch_roster=lambda _l, _t: {}),
        nfl_rest_tracker=nfl_rest_tracker,
        playoff_books=playoff_books, roster_drift_books=roster_drift_books,
    )


def test_engine_nfl_bye_shifts_margin_and_is_road_only_penalty_free_for_home():
    """THE brief's key test: NFL bye (+1.0) and Thursday short week (-1.5,
    road only) applied on a synthetic schedule via the real engine hook,
    feature logged."""
    tmp = _make_tmp_paths()
    baseline_tracker = GameDateTracker(league="nfl")  # no history -> zero-op
    baseline = _nfl_signal(tmp[0], nfl_rest_tracker=baseline_tracker).generate(_nfl_market_fixture())

    bye_tracker = GameDateTracker(league="nfl")
    bye_tracker.teams["KC"] = ["2026-08-27"]   # 14 days before game -> KC (home) on a bye
    bye_tracker.teams["BUF"] = ["2026-09-03"]  # 7 days -> normal week
    bye_signal = _nfl_signal(tmp[1], nfl_rest_tracker=bye_tracker).generate(_nfl_market_fixture())

    assert baseline is not None and bye_signal is not None
    assert baseline.features["nfl_rest_margin_delta"] == 0.0
    assert bye_signal.features["nfl_rest_home_bye"] is True
    assert bye_signal.features["nfl_rest_margin_delta"] == pytest.approx(NFL_BYE_ADJUSTMENT)
    # KC is home and the subject -> the bye must RAISE KC's win probability.
    assert bye_signal.probability_yes > baseline.probability_yes


def test_engine_nfl_thursday_short_week_hurts_road_team_only():
    tmp = _make_tmp_paths()
    # Away (BUF) on a short week (4 days), home (KC) on a normal week.
    away_short_tracker = GameDateTracker(league="nfl")
    away_short_tracker.teams["KC"] = ["2026-09-03"]   # 7 days -- normal
    away_short_tracker.teams["BUF"] = ["2026-09-06"]  # 4 days -- short week
    away_short_signal = _nfl_signal(tmp[0], nfl_rest_tracker=away_short_tracker).generate(_nfl_market_fixture())

    # Mirror-image: home (KC) on the identical short rest instead -- must be
    # a NO-OP (brief's explicit "home team on a short week gets NO penalty").
    home_short_tracker = GameDateTracker(league="nfl")
    home_short_tracker.teams["KC"] = ["2026-09-06"]   # 4 days -- would-be short week
    home_short_tracker.teams["BUF"] = ["2026-09-03"]  # 7 days -- normal
    home_short_signal = _nfl_signal(tmp[1], nfl_rest_tracker=home_short_tracker).generate(_nfl_market_fixture())

    baseline_tracker = GameDateTracker(league="nfl")
    baseline_signal = _nfl_signal(tmp[2], nfl_rest_tracker=baseline_tracker).generate(_nfl_market_fixture())

    assert away_short_signal.features["nfl_rest_away_thursday_short_week"] is True
    # home_adj(0.0) - away_adj(NFL_SHORT_WEEK_ADJUSTMENT) = -NFL_SHORT_WEEK_ADJUSTMENT (positive).
    assert away_short_signal.features["nfl_rest_margin_delta"] == pytest.approx(-NFL_SHORT_WEEK_ADJUSTMENT)
    # KC (home, subject) benefits when BUF (away) is short-rested.
    assert away_short_signal.probability_yes > baseline_signal.probability_yes

    assert home_short_signal.features["nfl_rest_home_thursday_short_week"] is False
    assert home_short_signal.features["nfl_rest_margin_delta"] == 0.0
    # Byte-identical to the no-history baseline: the home-side short week is
    # a genuine no-op, not merely a smaller effect.
    assert home_short_signal.probability_yes == baseline_signal.probability_yes


def _make_tmp_paths():
    import tempfile
    from pathlib import Path

    base = Path(tempfile.mkdtemp())
    return [base / "a", base / "b", base / "c", base / "d"]


# -- NHL: b2b + pre-game gate ---------------------------------------------

NHL_NOW = datetime(2026, 1, 12, 16, 0, tzinfo=timezone.utc)


def _nhl_pregame_game() -> Game:
    return Game("g1", "nhl", "BOS", "TOR", "pre", None, "2026-01-12T20:00Z",
                home_name="Boston Bruins", away_name="Toronto Maple Leafs")


def _nhl_live_game() -> Game:
    return Game(
        "g1", "nhl", "BOS", "TOR", "in", None, "2026-01-12T20:00Z",
        home_name="Boston Bruins", away_name="Toronto Maple Leafs",
        home_score=2, away_score=1, current_period=1, current_clock="10:00",
    )


def _nhl_box(team: str, opponent: str, is_home: bool, game_id: str) -> TeamBoxscore:
    return TeamBoxscore(
        game_id=game_id, league="nhl", team=team, opponent=opponent, is_home=is_home,
        stats={"powerPlayGoals": 1.0, "powerPlayOpportunities": 3.0, "shotsTotal": 30.0},
    )


def _nhl_signal(tmp_path, game: Game, nhl_rest_tracker=None, warm: bool = True) -> TeamSportsIntelligenceSignal:
    from autonomy.sports.nhl_model import MIN_GAMES_FOR_ENGINE

    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("nhl", "20260112")] = [game]
    store = BoxscoreStore("nhl", path=tmp_path / "boxscores_nhl.json")
    if warm:
        store.ingest([_nhl_box("BOS", "TOR", True, f"gh{i}") for i in range(MIN_GAMES_FOR_ENGINE)])
        store.ingest([_nhl_box("TOR", "BOS", False, f"ga{i}") for i in range(MIN_GAMES_FOR_ENGINE)])
    return TeamSportsIntelligenceSignal(
        espn=client, model_dir=tmp_path, nhl_boxscores=store, nhl_model=NhlModel(),
        fetch_nhl_scoreboard=lambda league, dates: {"events": []},
        nhl_rest_tracker=nhl_rest_tracker,
    )


def test_engine_nhl_b2b_shifts_margin_pregame():
    tmp = _make_tmp_paths()
    baseline_tracker = GameDateTracker(league="nhl")
    baseline = _nhl_signal(tmp[0], _nhl_pregame_game(), nhl_rest_tracker=baseline_tracker).generate(
        _market("KXNHLGAME-26JAN12BOSTOR-BOS", "Bruins vs Maple Leafs Winner?"))

    b2b_tracker = GameDateTracker(league="nhl")
    b2b_tracker.teams["BOS"] = ["2026-01-11"]  # 1 day before -> home on a b2b
    b2b_signal = _nhl_signal(tmp[1], _nhl_pregame_game(), nhl_rest_tracker=b2b_tracker).generate(
        _market("KXNHLGAME-26JAN12BOSTOR-BOS", "Bruins vs Maple Leafs Winner?"))

    assert baseline is not None and b2b_signal is not None
    assert baseline.features["nhl_rest_margin_delta"] == 0.0
    assert b2b_signal.features["nhl_rest_home_b2b"] is True
    assert b2b_signal.features["nhl_rest_margin_delta"] == pytest.approx(NHL_B2B_ADJUSTMENT)
    # BOS is home and the subject; a b2b must LOWER its win probability.
    assert b2b_signal.probability_yes < baseline.probability_yes


def test_engine_nhl_b2b_is_gated_pregame_only_live_byte_identical():
    """KEY TEST: confirm the b2b HARD adjustment is NOT applied on the live
    branch -- a live game's scoreboard already reflects a tired backup
    goalie, so re-applying it would double-count (same discipline as WS-6's
    own nba_live/nhl_live gate)."""
    tmp = _make_tmp_paths()
    b2b_tracker_live = GameDateTracker(league="nhl")
    b2b_tracker_live.teams["BOS"] = ["2026-01-11"]
    live_hurt = _nhl_signal(tmp[0], _nhl_live_game(), nhl_rest_tracker=b2b_tracker_live).generate(
        _market("KXNHLGAME-26JAN12BOSTOR-BOS", "Bruins vs Maple Leafs Winner?"))

    live_healthy_tracker = GameDateTracker(league="nhl")
    live_healthy = _nhl_signal(tmp[1], _nhl_live_game(), nhl_rest_tracker=live_healthy_tracker).generate(
        _market("KXNHLGAME-26JAN12BOSTOR-BOS", "Bruins vs Maple Leafs Winner?"))

    assert live_hurt is not None and live_healthy is not None
    assert live_hurt.source == "nhl_live_winner"
    # The state is still computed/logged (telemetry keeps seeing it)...
    assert live_hurt.features["nhl_rest_home_b2b"] is True
    # ...but on the live branch it must be a genuine no-op: byte-identical
    # to the no-b2b live market.
    assert live_hurt.probability_yes == live_healthy.probability_yes

    # Pre-game (no live score yet) the same b2b state DOES fire (proves the
    # gate is live-only, not a blanket disable).
    b2b_tracker_pre = GameDateTracker(league="nhl")
    b2b_tracker_pre.teams["BOS"] = ["2026-01-11"]
    pregame_hurt = _nhl_signal(tmp[2], _nhl_pregame_game(), nhl_rest_tracker=b2b_tracker_pre).generate(
        _market("KXNHLGAME-26JAN12BOSTOR-BOS", "Bruins vs Maple Leafs Winner?"))
    pregame_healthy = _nhl_signal(tmp[3], _nhl_pregame_game(), nhl_rest_tracker=GameDateTracker(league="nhl")).generate(
        _market("KXNHLGAME-26JAN12BOSTOR-BOS", "Bruins vs Maple Leafs Winner?"))
    assert pregame_hurt.probability_yes < pregame_healthy.probability_yes


# -- widen-only invariants + no-feeds + feature completeness ---------------


def test_engine_playoff_and_roster_event_widen_uncertainty_only_mean_byte_identical():
    tmp = _make_tmp_paths()
    baseline = _nfl_signal(tmp[0]).generate(_nfl_market_fixture())

    clinched_books = {"nfl": PlayoffBook("nfl", fetch_fn=lambda: {})}
    clinched_books["nfl"]._teams = {"KC": PlayoffState(clinched=True)}
    clinched_signal = _nfl_signal(tmp[1], playoff_books=clinched_books).generate(_nfl_market_fixture())

    roster_books = {"nfl": RosterDriftBook("nfl")}
    roster_books["nfl"]._events = {"KC": {"roster_event": True, "roster_diff_count": 30, "roster_size": 53}}
    roster_signal = _nfl_signal(tmp[2], roster_drift_books=roster_books).generate(_nfl_market_fixture())

    assert baseline is not None and clinched_signal is not None and roster_signal is not None
    # Mean byte-identical for BOTH soft states.
    assert clinched_signal.probability_yes == baseline.probability_yes
    assert roster_signal.probability_yes == baseline.probability_yes
    # Only uncertainty rises, by exactly the documented constant each.
    assert round(clinched_signal.uncertainty - baseline.uncertainty, 4) == round(CLINCH_UNCERTAINTY, 4)
    assert round(roster_signal.uncertainty - baseline.uncertainty, 4) == round(ROSTER_EVENT_UNCERTAINTY, 4)
    assert clinched_signal.features["playoff_clinched_home"] is True
    assert roster_signal.features["roster_event_home"] is True


def test_engine_no_feeds_is_byte_identical_to_disabled():
    """Brief's own key test: no feeds (unrefreshed playoff/roster books,
    empty rest trackers) -> all-zero effects, byte-identical to disabled."""
    tmp = _make_tmp_paths()
    disabled = _nfl_signal(tmp[0]).generate(_nfl_market_fixture())

    def boom_standings():
        raise RuntimeError("espn down")

    def boom_teams(_l):
        raise RuntimeError("espn down")

    dead_playoff_books = {"nfl": PlayoffBook("nfl", fetch_fn=boom_standings)}
    dead_playoff_books["nfl"].refresh()
    dead_roster_books = {"nfl": RosterDriftBook("nfl", fetch_teams=boom_teams)}
    dead_roster_books["nfl"].refresh(["KC", "BUF"])
    absent = _nfl_signal(
        tmp[1], playoff_books=dead_playoff_books, roster_drift_books=dead_roster_books,
    ).generate(_nfl_market_fixture())

    assert disabled.probability_yes == absent.probability_yes
    assert disabled.uncertainty == absent.uncertainty
    assert absent.features["nfl_rest_margin_delta"] == 0.0
    assert absent.features["playoff_clinched_home"] is False
    assert absent.features["roster_event_home"] is False


def test_engine_feature_logging_completeness_for_active_states():
    """Every state that fired must emit its own named feature (for the
    miner)."""
    tmp = _make_tmp_paths()
    bye_tracker = GameDateTracker(league="nfl")
    bye_tracker.teams["KC"] = ["2026-08-27"]
    playoff_books = {"nfl": PlayoffBook("nfl", fetch_fn=lambda: {})}
    playoff_books["nfl"]._teams = {
        "KC": PlayoffState(clinched=True, must_win=False),
        "BUF": PlayoffState(eliminated=True),
    }
    roster_books = {"nfl": RosterDriftBook("nfl")}
    roster_books["nfl"]._events = {"BUF": {"roster_event": True, "roster_diff_count": 25, "roster_size": 53}}
    signal = _nfl_signal(
        tmp[0], nfl_rest_tracker=bye_tracker, playoff_books=playoff_books, roster_drift_books=roster_books,
    ).generate(_nfl_market_fixture())

    for key in (
        "nfl_rest_home_bye", "nfl_rest_home_rest_days", "nfl_rest_margin_delta",
        "playoff_clinched_home", "playoff_eliminated_away", "playoff_must_win_home",
        "roster_event_away", "roster_diff_count_away",
    ):
        assert key in signal.features, f"missing feature: {key}"
    assert signal.features["nfl_rest_home_bye"] is True
    assert signal.features["playoff_clinched_home"] is True
    assert signal.features["playoff_eliminated_away"] is True
    assert signal.features["roster_event_away"] is True
    assert signal.features["challenger_only"] is True
