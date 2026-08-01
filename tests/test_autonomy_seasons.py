"""Season auto-gating: detection, TTL, stickiness, merge-save, warmup skip."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.specialists.seasons import SeasonMonitor
from autonomy.specialists.team_leagues import TeamLeagueSpecialist
from autonomy.sports.espn import EspnClient, Game

NOW = datetime(2026, 7, 12, 17, 0, tzinfo=timezone.utc)


class _FakeEspn:
    """Scriptable per-league game presence with a call log.

    Mirrors the REAL client contract: ``games_or_raise`` raises on feed
    failure while ``games`` swallows to [] -- the distinction the gate's
    sticky/fail-open behavior depends on.
    """

    def __init__(self, active_leagues: set[str], fail_leagues: set[str] = frozenset()):
        self.active_leagues = set(active_leagues)
        self.fail_leagues = set(fail_leagues)
        self.calls: list[tuple[str, str]] = []

    def games_or_raise(self, league: str, dates: str | None = None):
        self.calls.append((league, dates or ""))
        if league in self.fail_leagues:
            raise ValueError("espn down")
        if league in self.active_leagues:
            return [Game("g1", league, "AAA", "BBB", "pre", None, "2026-07-20T00:00Z")]
        return []

    def games(self, league: str, dates: str | None = None):
        try:
            return self.games_or_raise(league, dates)
        except Exception:
            return []

    def clear_cache(self) -> None:
        return None


def _monitor(espn, tmp_path: Path, now: datetime = NOW, **kw) -> SeasonMonitor:
    return SeasonMonitor(
        espn=espn, state_path=tmp_path / "season_state.json",
        now_fn=lambda: now, **kw,
    )


def test_real_client_games_or_raise_raises_while_games_swallows():
    def _dead_fetch(_league, _dates):
        raise ValueError("network down")

    client = EspnClient(fetch_scoreboard=_dead_fetch)
    assert client.games("mlb", "20260705-20260802") == []
    client.clear_cache()
    try:
        client.games_or_raise("mlb", "20260705-20260802")
    except ValueError:
        raised = True
    else:
        raised = False
    assert raised, "games_or_raise must propagate feed failures"


def test_a_failed_games_call_does_not_poison_games_or_raise():
    """A swallowed failure must not silence a later raising call.

    ``games`` cached its empty result on failure, so the very next
    ``games_or_raise`` for the same (league, dates) key returned that []
    without raising -- re-hiding the outage the raising variant exists to
    expose. The lake ingest now depends on that variant, and forecasting
    signals call ``games`` on overlapping keys, so the caveat is
    load-bearing rather than theoretical.
    """
    calls = {"n": 0}

    def _dead_fetch(_league, _dates):
        calls["n"] += 1
        raise ValueError("network down")

    client = EspnClient(fetch_scoreboard=_dead_fetch)
    assert client.games("mlb", None) == []

    raised = False
    try:
        client.games_or_raise("mlb", None)
    except ValueError:
        raised = True
    assert raised, "a failed fetch must not be cached as an empty slate"
    assert calls["n"] == 2, "the failure must be re-attempted, not served from cache"


def test_active_reflects_scoreboard_window_and_persists(tmp_path):
    espn = _FakeEspn({"mlb"})
    monitor = _monitor(espn, tmp_path)
    assert monitor.active("mlb") is True
    assert monitor.active("nfl") is False
    league, window = espn.calls[0]
    assert window == "20260705-20260802"  # -7/+21 days around now
    # A fresh monitor on the same state file remembers without refetching
    # inside the TTL.
    espn2 = _FakeEspn(set())
    monitor2 = _monitor(espn2, tmp_path)
    assert monitor2.active("mlb") is True
    assert espn2.calls == []


def test_ttl_expiry_rechecks_and_records_wake_timestamp(tmp_path):
    espn = _FakeEspn(set())
    monitor = _monitor(espn, tmp_path)
    assert monitor.active("nfl") is False
    later = NOW + timedelta(hours=7)  # past the 6h TTL
    espn.active_leagues.add("nfl")
    woke_monitor = SeasonMonitor(
        espn=espn, state_path=tmp_path / "season_state.json",
        now_fn=lambda: later,
    )
    assert woke_monitor.active("nfl") is True
    assert woke_monitor.snapshot()["nfl"]["woke_at"] == later.isoformat()


def test_feed_error_is_sticky_and_unknown_fails_open(tmp_path):
    espn = _FakeEspn({"nba"})
    monitor = _monitor(espn, tmp_path)
    assert monitor.active("nba") is True
    # Feed dies; past-TTL recheck keeps the last known verdict (sticky).
    espn.fail_leagues.add("nba")
    later = NOW + timedelta(hours=7)
    sticky = SeasonMonitor(
        espn=espn, state_path=tmp_path / "season_state.json", now_fn=lambda: later)
    assert sticky.active("nba") is True
    assert sticky.snapshot()["nba"]["last_check_error"] is True
    # Never-checked league + feed error -> fail OPEN (active).
    espn.fail_leagues.add("nhl")
    assert sticky.active("nhl") is True
    # An empty scoreboard WITHOUT an error is a genuine offseason verdict.
    espn.fail_leagues.clear()
    espn.active_leagues.clear()
    much_later = NOW + timedelta(hours=14)
    offseason = SeasonMonitor(
        espn=espn, state_path=tmp_path / "season_state.json",
        now_fn=lambda: much_later)
    assert offseason.active("nba") is False
    assert offseason.snapshot()["nba"]["last_check_error"] is False


def test_save_merges_instead_of_clobbering_other_monitors_leagues(tmp_path):
    state_path = tmp_path / "season_state.json"
    elo_monitor = SeasonMonitor(
        espn=_FakeEspn({"wnba"}), state_path=state_path, now_fn=lambda: NOW)
    assert elo_monitor.active("wnba") is True
    # A second monitor instance (different signal) checks a different league;
    # its save must not erase the first monitor's verdict.
    team_monitor = SeasonMonitor(
        espn=_FakeEspn(set()), state_path=state_path, now_fn=lambda: NOW)
    assert team_monitor.active("nfl") is False
    on_disk = json.loads(state_path.read_text(encoding="utf-8"))
    assert on_disk["wnba"]["active"] is True
    assert on_disk["nfl"]["active"] is False


def test_team_signal_skips_dormant_league_warmup(tmp_path):
    from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
    from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

    espn = _FakeEspn({"nba"})  # only the NBA shows games
    monitor = _monitor(espn, tmp_path)
    signal = TeamSportsIntelligenceSignal(
        espn=espn,
        models={league: TeamScoreModel(league) for league in LEAGUE_SCORE_CONFIGS},
        model_dir=tmp_path,
        seasons=monitor,
    )
    espn.calls.clear()
    signal.on_cycle_start()
    per_league: dict[str, int] = {}
    for league, _window in espn.calls:
        per_league[league] = per_league.get(league, 0) + 1
    assert per_league["nba"] >= 2  # season check + warmup fetch
    for dormant in ("nfl", "ncaaf", "nhl", "ncaamb"):
        assert per_league.get(dormant, 0) == 1  # season check only
    # Steady state: cached verdicts, only the active league fetches again.
    espn.calls.clear()
    signal.on_cycle_start()
    assert all(league == "nba" for league, _w in espn.calls)


def test_mlb_signal_skips_everything_when_dormant(tmp_path):
    from autonomy.signals.sports_intelligence import BaseballIntelligenceSignal
    from autonomy.sports.baseball import BaseballRunModel

    class _SpyInjuries:
        def __init__(self):
            self.refreshes = 0

        def refresh(self):
            self.refreshes += 1

        def burden_for(self, _team):
            return 0.0

        def questionable_for(self, _team):
            return 0

    espn = _FakeEspn(set())  # offseason
    injuries = _SpyInjuries()
    signal = BaseballIntelligenceSignal(
        espn=espn, model=BaseballRunModel(), model_path=tmp_path / "mlb.json",
        injuries=injuries, seasons=_monitor(espn, tmp_path),
    )
    signal.on_cycle_start()
    assert injuries.refreshes == 0  # dormant: no warmup, no injuries fetch
    # In-season: warmup + injuries refresh run.
    espn.active_leagues.add("mlb")
    later = NOW + timedelta(hours=7)
    in_season = BaseballIntelligenceSignal(
        espn=espn, model=BaseballRunModel(), model_path=tmp_path / "mlb2.json",
        injuries=injuries,
        seasons=SeasonMonitor(
            espn=espn, state_path=tmp_path / "season_state.json",
            now_fn=lambda: later),
    )
    in_season.on_cycle_start()
    assert injuries.refreshes == 1


def test_specialist_health_reports_dormant(tmp_path):
    espn = _FakeEspn(set())
    monitor = _monitor(espn, tmp_path)
    specialist = TeamLeagueSpecialist(
        league="nfl", intelligence=None, sportsbook=None, seasons=monitor)
    health = specialist.health()
    assert health.status == "dormant"
    assert health.details["in_season"] is False
    active = TeamLeagueSpecialist(
        league="nfl", intelligence=object(), sportsbook=None,
        seasons=_monitor(_FakeEspn({"nfl"}), tmp_path / "b"))
    assert active.health().status == "ok"
    assert active.health().details["in_season"] is True
