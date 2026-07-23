"""Derived source-reported availability for retro flat-file backfills.

The point-in-time gate quarantines rows whose result availability is
unknown. Published season CSVs (sportsdataverse / wehoop / cfbfastR /
nflverse) carry no per-game publication timestamp, but they do carry the
game's own start time — and a final score for a game that started at T was
public knowledge well before T + 12h. Stamping that *bound* as
``source_reported`` availability is a claim about the source's own data
(game date + final flag), never about our observation, so:

- ``observed_at_receipt`` rows always outrank these (enforced in
  ``SportsHistoryStore.upsert_games``);
- every stamped row discloses ``availability_basis`` in ``extra``;
- rows without a parseable timezone-aware start time stay ``unknown`` and
  quarantined, exactly as before.

This unlocks multi-season walk-forward/tuning/holdout evaluation that the
2026-07-22 elite audit lists as readiness blocker #1, without fabricating
observation timestamps.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

RESULT_AVAILABILITY_BOUND_HOURS = 12.0
AVAILABILITY_BASIS = "derived_game_start_plus_12h_v1"


def parse_aware(value: Any) -> datetime | None:
    """Public alias: parse an ISO timestamp, requiring timezone awareness."""
    return _parse_aware(value)


def _parse_aware(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def stamp_retro_source_reported(
    rows: Iterable[dict[str, Any]], *, now: datetime | None = None,
) -> int:
    """Stamp completed retro rows with derived source-reported availability.

    Mutates rows in place; returns how many were stamped. Rows that are not
    final, lack scores, already carry availability, or have no parseable
    timezone-aware start time are left untouched (and stay quarantined).
    """
    now_dt = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamped = 0
    for row in rows:
        if row.get("status") != "final":
            continue
        if row.get("home_score") is None or row.get("away_score") is None:
            continue
        if row.get("result_available_at") or row.get("received_at"):
            continue
        start = _parse_aware(row.get("start_time"))
        if start is None:
            continue
        available = start + timedelta(hours=RESULT_AVAILABILITY_BOUND_HOURS)
        if available > now_dt:
            # Too recent for the bound to be conservative; leave unknown.
            continue
        extra = row.get("extra")
        extra = dict(extra) if isinstance(extra, dict) else {}
        extra["availability_basis"] = AVAILABILITY_BASIS
        row["result_available_at"] = available.isoformat()
        row["received_at"] = now_dt.isoformat()
        row["provenance_quality"] = "source_reported"
        row["extra"] = extra
        stamped += 1
    return stamped
