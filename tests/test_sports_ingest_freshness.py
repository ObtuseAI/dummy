"""The guard the 2026-07-24 -> 2026-08-01 sports outage needed.

For eight days the lake took zero rows while every layer reported success:
the fetch raised ModuleNotFoundError, EspnClient.games() swallowed it to [],
ingest_espn_league logged status "ok" with rows 0, and pythonw exited 0.

The watchdog could not catch it. It checks ARTIFACT AGE, and the artifacts
were fresh -- an ingest_log row was written every cycle. They just contained
nothing. Artifact freshness is not data freshness, and that distinction is
the whole point of this module.

The guard therefore reads the DATA: the newest received_at per league. It
also has to decide which leagues are supposed to be producing, and it derives
that from scheduled fixtures rather than a hard-coded calendar -- a hard-coded
one rots, and a rotted season table would re-hide exactly this failure.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.sports.ingest_freshness import (
    IngestFreshness,
    evaluate_sports_ingest_freshness,
)


NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _iso(delta_hours: float) -> str:
    return (NOW - timedelta(hours=delta_hours)).isoformat()


def test_an_in_season_league_that_stopped_ingesting_is_stale():
    """The exact outage: fixtures exist, rows stopped arriving."""
    result = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "mlb", "last_received_at": _iso(192), "near_future_fixtures": 40, "historical_games_this_week": 500, "historical_seasons_this_week": 3},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    assert result.stale_leagues == ["mlb"]
    assert result.status == "STALE"
    detail = result.by_league["mlb"]
    assert detail["in_season"] is True
    assert detail["stale"] is True
    assert round(detail["age_hours"]) == 192


def test_an_off_season_league_with_no_fixtures_is_not_stale():
    """Silence is correct when there is nothing to ingest.

    Flagging every off-season league would train everyone to ignore the
    signal, which is how a real alert gets lost.
    """
    result = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "nfl", "last_received_at": _iso(500), "near_future_fixtures": 0, "historical_games_this_week": 0, "historical_seasons_this_week": 0},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    assert result.stale_leagues == []
    assert result.status == "OK"
    assert result.by_league["nfl"]["in_season"] is False


def test_a_fresh_in_season_league_is_ok():
    result = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "wnba", "last_received_at": _iso(2), "near_future_fixtures": 12, "historical_games_this_week": 300, "historical_seasons_this_week": 10},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    assert result.status == "OK"
    assert result.by_league["wnba"]["stale"] is False


def test_a_league_that_never_ingested_is_stale_not_skipped():
    """A missing timestamp is the most alarming case, not the least.

    Treating None as "no opinion" is how a league that never started gets
    silently excluded from the very check meant to catch it.
    """
    result = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "nhl", "last_received_at": None, "near_future_fixtures": 8, "historical_games_this_week": 200, "historical_seasons_this_week": 5},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    assert result.stale_leagues == ["nhl"]
    assert result.by_league["nhl"]["age_hours"] is None
    assert result.by_league["nhl"]["stale"] is True


def test_an_unparseable_timestamp_fails_closed():
    """Garbage in the timestamp column must alarm, not be treated as fresh."""
    result = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "mlb", "last_received_at": "not-a-timestamp", "near_future_fixtures": 5, "historical_games_this_week": 100, "historical_seasons_this_week": 4},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    assert result.stale_leagues == ["mlb"]
    assert result.by_league["mlb"]["stale"] is True


def test_a_future_timestamp_fails_closed():
    """A clock skew or a bad backfill must not read as maximally fresh."""
    result = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "mlb", "last_received_at": _iso(-6), "near_future_fixtures": 5, "historical_games_this_week": 100, "historical_seasons_this_week": 4},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    assert result.by_league["mlb"]["stale"] is True
    assert result.status == "STALE"


def test_no_leagues_at_all_is_reported_not_silently_ok():
    """An empty result set means the query found nothing, which is itself
    a failure worth surfacing -- not a clean bill of health."""
    result = evaluate_sports_ingest_freshness(rows=[], now=NOW, max_age_hours=24.0)

    assert result.status == "NO_DATA"
    assert result.stale_leagues == []


def test_mixed_fleet_reports_every_stale_league_not_just_the_first():
    result = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "mlb", "last_received_at": _iso(192), "near_future_fixtures": 40, "historical_games_this_week": 500, "historical_seasons_this_week": 3},
            {"league": "wnba", "last_received_at": _iso(1), "near_future_fixtures": 12, "historical_games_this_week": 300, "historical_seasons_this_week": 10},
            {"league": "nba", "last_received_at": _iso(400), "near_future_fixtures": 0, "historical_games_this_week": 0, "historical_seasons_this_week": 0},
            {"league": "nhl", "last_received_at": None, "near_future_fixtures": 3, "historical_games_this_week": 90, "historical_seasons_this_week": 4},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    assert result.stale_leagues == ["mlb", "nhl"]
    assert result.status == "STALE"
    assert result.by_league["nba"]["in_season"] is False


def test_the_result_is_serialisable_for_a_health_surface():
    """The watchdog publishes JSON; a dataclass that cannot round-trip is
    useless to it."""
    import json

    result = evaluate_sports_ingest_freshness(
        rows=[{"league": "mlb", "last_received_at": _iso(2), "near_future_fixtures": 5, "historical_games_this_week": 100, "historical_seasons_this_week": 4}],
        now=NOW,
        max_age_hours=24.0,
    )

    assert isinstance(result, IngestFreshness)
    payload = json.dumps(result.as_dict())
    assert json.loads(payload)["status"] == "OK"


def test_it_would_have_caught_the_real_outage():
    """The actual 2026-07-24 -> 2026-08-01 state, as measured.

    This is the only test that matters. MLB and WNBA were mid-season and had
    taken no rows for eight days while every layer reported success. The
    guard must go red on exactly that, and stay quiet about the genuinely
    dormant leagues so the alarm means something.
    """
    outage_now = datetime(2026, 8, 1, 6, 0, tzinfo=timezone.utc)
    result = evaluate_sports_ingest_freshness(
        rows=[
            # in season, dead for 8 days -- the outage
            {"league": "mlb", "last_received_at": "2026-07-23T19:08:45+00:00",
             "near_future_fixtures": 0,
             "historical_games_this_week": 559, "historical_seasons_this_week": 3},
            {"league": "wnba", "last_received_at": "2026-07-23T19:08:50+00:00",
             "near_future_fixtures": 0,
             "historical_games_this_week": 440, "historical_seasons_this_week": 15},
            # genuinely dormant -- must NOT alarm
            {"league": "nba", "last_received_at": "2026-07-22T22:46:11+00:00",
             "near_future_fixtures": 0,
             "historical_games_this_week": 53, "historical_seasons_this_week": 1},
            {"league": "ncaamb", "last_received_at": "2026-07-22T22:46:20+00:00",
             "near_future_fixtures": 0,
             "historical_games_this_week": 0, "historical_seasons_this_week": 0},
        ],
        now=outage_now,
        max_age_hours=24.0,
    )

    assert result.status == "STALE"
    assert result.stale_leagues == ["mlb", "wnba"]
    assert result.by_league["nba"]["in_season"] is False, (
        "the 2020 COVID bubble is one anomalous season, not a season pattern"
    )
    assert result.by_league["ncaamb"]["in_season"] is False


def test_a_stale_league_makes_the_watchdog_unhealthy(tmp_path):
    """Wiring proof: the guard must actually change the fleet verdict.

    A health signal computed and then ignored is the same costume as a test
    that cannot fail. This asserts the verdict flips, not merely that the
    field is published.
    """
    from autonomy.watchdog import evaluate_watchdog

    freshness = evaluate_sports_ingest_freshness(
        rows=[
            {"league": "mlb", "last_received_at": _iso(192),
             "near_future_fixtures": 0,
             "historical_games_this_week": 559, "historical_seasons_this_week": 3},
        ],
        now=NOW,
        max_age_hours=24.0,
    )

    healthy_status = evaluate_watchdog(
        runtime_dir=tmp_path, tasks=[], inventory=[]
    )
    assert healthy_status["healthy"] is True, "baseline must be healthy or this proves nothing"

    degraded = evaluate_watchdog(
        runtime_dir=tmp_path,
        tasks=[],
        inventory=[],
        sports_freshness=freshness.as_dict(),
    )
    assert degraded["healthy"] is False
    assert degraded["sports_stale_leagues"] == ["mlb"]


def test_omitting_freshness_leaves_the_verdict_untouched(tmp_path):
    """Absent input must not silently degrade health.

    The watchdog runs in contexts with no lake access; a missing signal is
    not evidence of a problem.
    """
    from autonomy.watchdog import evaluate_watchdog

    status = evaluate_watchdog(runtime_dir=tmp_path, tasks=[], inventory=[])
    assert status["healthy"] is True
    assert status["sports_stale_leagues"] == []
    assert status["sports_ingest_freshness"] is None
