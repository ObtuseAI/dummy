"""Data freshness for the sports history lake, per league.

The watchdog already checks ARTIFACT age. That was not enough: between
2026-07-24 and 2026-08-01 the lake took zero rows while an ingest_log row was
still written every cycle, so the artifact stayed fresh and contained nothing.
Every layer reported success -- the fetch raised ModuleNotFoundError, the ESPN
client swallowed it to an empty list, the ingest logged status "ok" with rows
0, and the process exited 0.

This module asks the question none of those layers could: is the DATA moving?

Two decisions carry the weight.

In-season is DERIVED, primarily from the league's HISTORICAL footprint for this
calendar week across prior seasons, and secondarily from fixtures scheduled
within the next two weeks.

The first draft used future fixtures alone and was wrong in the worst possible
way: if ingestion is broken, no fixtures get stored, the league reads as out of
season, and the guard falls silent exactly when it is needed. Measured live on
2026-08-01 -- MLB and WNBA, both mid-season, showed zero future fixtures because
the repaired ingest had so far fetched only completed games. The obvious signal
was circular. Frozen prior-season history is not; no current outage can erase it.

Two corrections came from running it against the real lake rather than
reasoning about it. The footprint is measured PER SEASON, because a raw count
conflates "plays heavily now" with "has a long history containing oddities".
And it must span more than one season, because NBA and NHL each show a single
August with games -- the 2020 COVID bubble -- which would otherwise mark both
in-season every August forever.

Everything ambiguous is STALE. A missing timestamp, an unparseable one, and a
future one all alarm. Treating any of them as "no opinion" reproduces the
original defect at a smaller scale: a league that never started ingesting is
the most alarming case, not a reason to skip the check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


#: A league with at least this many scheduled future fixtures is expected to
#: be producing rows. One is enough -- a single upcoming game means the feed
#: should be answering.
IN_SEASON_MIN_FUTURE_FIXTURES = 1

#: Games this league played on this calendar date in PRIOR seasons. This is
#: the load-bearing signal and it exists because the obvious one is circular.
#:
#: Deriving in-season from future fixtures ALONE re-creates the failure this
#: module exists to catch: if ingestion is broken, no future fixtures are
#: stored, the league reads as out of season, and the guard falls silent
#: precisely when it is needed. Verified live on 2026-08-01 -- MLB and WNBA,
#: both mid-season, reported future_fixtures=0 because the repaired ingest had
#: so far fetched only completed games.
#:
#: The historical footprint cannot rot that way. It reads frozen prior-season
#: history, which no current outage can erase.
#: Measured PER HISTORICAL SEASON, not as a raw count. A raw count conflates
#: "plays heavily in this week" with "has a long history and a few oddities in
#: it". Verified live 2026-08-01: NBA showed 53 historical games in this
#: calendar week -- about 3 per year across ~18 seasons of summer exhibitions --
#: which a raw threshold read as in-season. MLB showed 559 (~186/yr) and WNBA
#: 440 (~22/yr), which genuinely are. A false alarm on a dormant league is not
#: harmless: it is how an operator learns to ignore this signal.
IN_SEASON_MIN_GAMES_PER_SEASON = 5.0

#: ...and it must have happened in more than one season. A single anomalous
#: year is not a season pattern. Verified live 2026-08-01: NBA and NHL each
#: showed one historical season with games in this calendar week -- the 2020
#: COVID bubble, when both played through August. Without this, the bubble
#: alone would mark both as in-season every August thereafter.
IN_SEASON_MIN_HISTORICAL_SEASONS = 2

#: Only fixtures inside this horizon imply an ACTIVE season. Verified live
#: 2026-08-01: NHL had 7 scheduled fixtures, all in late September -- a game
#: seven weeks out does not mean the feed should be delivering rows today.
IN_SEASON_FIXTURE_HORIZON_DAYS = 14

#: Calendar window either side of today when matching prior seasons, absorbing
#: year-to-year schedule drift.
SEASON_FOOTPRINT_WINDOW_DAYS = 7


@dataclass(frozen=True)
class IngestFreshness:
    """Per-league verdict plus a single status for a health surface."""

    status: str
    stale_leagues: list[str]
    max_age_hours: float
    checked_at: str
    by_league: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stale_leagues": list(self.stale_leagues),
            "max_age_hours": self.max_age_hours,
            "checked_at": self.checked_at,
            "by_league": {k: dict(v) for k, v in self.by_league.items()},
        }


def _age_hours(value: Any, now: datetime) -> float | None:
    """Hours since ``value``; None when it cannot be trusted.

    None is the caller's signal to fail closed. It covers absent, malformed
    and future timestamps alike, because none of them is evidence that data
    arrived recently.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = (now - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0
    if delta < 0:
        # Clock skew or a bad backfill. Not evidence of freshness.
        return None
    return delta


def evaluate_sports_ingest_freshness(
    *,
    rows: Iterable[Mapping[str, Any]],
    now: datetime,
    max_age_hours: float,
) -> IngestFreshness:
    """Judge whether each league's ingested DATA is still moving.

    ``rows`` carries one mapping per league with ``league``,
    ``last_received_at`` and ``future_fixtures``. It is passed in rather than
    queried here so the judgement stays pure and testable, and so the caller
    owns the read-only database access.
    """
    now_utc = now.astimezone(timezone.utc)
    by_league: dict[str, dict[str, Any]] = {}
    stale: list[str] = []

    for row in rows:
        league = str(row.get("league") or "")
        if not league:
            continue
        fixtures = int(row.get("future_fixtures") or 0)
        historical = int(row.get("historical_games_this_week") or 0)
        seasons = int(row.get("historical_seasons_this_week") or 0)
        per_season = (historical / seasons) if seasons else 0.0
        near_fixtures = int(row.get("near_future_fixtures") or 0)
        # EITHER signal is enough. Future fixtures catch a league whose season
        # is starting for the first time in this history; the historical
        # footprint catches everything else and, unlike fixtures, cannot be
        # erased by the outage being detected.
        in_season = (
            near_fixtures >= IN_SEASON_MIN_FUTURE_FIXTURES
            or (
                per_season >= IN_SEASON_MIN_GAMES_PER_SEASON
                and seasons >= IN_SEASON_MIN_HISTORICAL_SEASONS
            )
        )
        age = _age_hours(row.get("last_received_at"), now_utc)

        # Out of season, silence is correct. Flagging every dormant league
        # would train an operator to ignore this signal, which is how a real
        # alert gets lost.
        is_stale = in_season and (age is None or age > max_age_hours)

        by_league[league] = {
            "league": league,
            "in_season": in_season,
            "future_fixtures": fixtures,
            "near_future_fixtures": near_fixtures,
            "historical_games_this_week": historical,
            "historical_seasons_this_week": seasons,
            "historical_games_per_season": round(per_season, 2),
            "last_received_at": row.get("last_received_at"),
            "age_hours": round(age, 2) if age is not None else None,
            "stale": is_stale,
        }
        if is_stale:
            stale.append(league)

    if not by_league:
        # An empty result set means the query found no leagues at all. That is
        # a failure of the check itself and must not read as a clean pass.
        status = "NO_DATA"
    elif stale:
        status = "STALE"
    else:
        status = "OK"

    return IngestFreshness(
        status=status,
        stale_leagues=sorted(stale),
        max_age_hours=float(max_age_hours),
        checked_at=now_utc.isoformat(),
        by_league=by_league,
    )


def read_sports_ingest_rows(db_path: str) -> list[dict[str, Any]]:
    """Read one freshness row per league, READ-ONLY.

    Opened with mode=ro so a health check can never mutate the lake, and so a
    missing database raises rather than silently creating an empty one -- an
    auto-created empty database would report NO_DATA forever and look like a
    quiet check rather than a broken one.
    """
    import sqlite3

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        return [
            {
                "league": row["league"],
                "last_received_at": row["last_received_at"],
                "future_fixtures": row["future_fixtures"],
                "near_future_fixtures": row["near_future_fixtures"],
                "historical_games_this_week": row["historical_games_this_week"],
                "historical_seasons_this_week": row["historical_seasons_this_week"],
            }
            for row in connection.execute(
                """
                SELECT league,
                       MAX(received_at) AS last_received_at,
                       SUM(
                           CASE
                               WHEN status != 'post'
                                    AND start_time > strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                               THEN 1 ELSE 0
                           END
                       ) AS future_fixtures,
                       SUM(
                           CASE
                               WHEN status != 'post'
                                    AND start_time > strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                                    AND julianday(start_time) - julianday('now')
                                        <= :fixture_horizon_days
                               THEN 1 ELSE 0
                           END
                       ) AS near_future_fixtures,
                       -- Prior-season footprint for this calendar week. Excludes
                       -- the current year so a broken ingest cannot flatter it,
                       -- and reads frozen history so no outage can erase it.
                       SUM(
                           CASE
                               WHEN strftime('%Y', start_time)
                                    < strftime('%Y', 'now')
                                AND ABS(
                                        julianday(
                                            strftime('%Y', 'now')
                                            || substr(start_time, 5, 6)
                                        )
                                        - julianday('now')
                                    ) <= :window_days
                               THEN 1 ELSE 0
                           END
                       ) AS historical_games_this_week,
                       COUNT(
                           DISTINCT CASE
                               WHEN strftime('%Y', start_time)
                                    < strftime('%Y', 'now')
                                AND ABS(
                                        julianday(
                                            strftime('%Y', 'now')
                                            || substr(start_time, 5, 6)
                                        )
                                        - julianday('now')
                                    ) <= :window_days
                               THEN strftime('%Y', start_time)
                           END
                       ) AS historical_seasons_this_week
                FROM games
                GROUP BY league
                """,
                {
                    "window_days": SEASON_FOOTPRINT_WINDOW_DAYS,
                    "fixture_horizon_days": IN_SEASON_FIXTURE_HORIZON_DAYS,
                },
            )
        ]
    finally:
        connection.close()
