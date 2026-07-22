"""Phase 1 adapter: ESPN scoreboard games -> history lake, for every league.

Reuses the existing keyless :class:`autonomy.sports.espn.EspnClient` (public
scoreboard JSON) so the lake gets game history across ALL traded leagues
(MLB/WNBA/NBA/NFL/NHL/NCAAF/NCAAMB), not just the open flat-file feeds. A
``post`` game lands final (visible to point-in-time queries); ``pre``/``in``
land scheduled/in-progress and stay invisible until they finish.

Client is injected, so the adapter is tested against real ``Game`` records with
no network. Fail-soft: a bad game is skipped, a down feed records a failed
ingest checkpoint rather than raising.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from autonomy.ingest.provenance import (
    AVAILABILITY_BASIS,
    RESULT_AVAILABILITY_BOUND_HOURS,
    parse_aware,
)
from autonomy.sports.history_store import SportsHistoryStore

_STATUS_MAP = {"post": "post", "in": "in", "pre": "scheduled"}

# A final observed within this window of its start time is a genuine live
# observation ("we watched it become final"). A final observed long after
# its start is a retro backfill: claiming today's receipt as availability
# would poison season ordering, so those rows get the derived
# source_reported bound (game start + league-safe duration) instead.
RETRO_OBSERVATION_GRACE_HOURS = 48.0


def _final_provenance(
    start_time: Any, received_at: str,
) -> tuple[str | None, str, str | None]:
    """(result_available_at, provenance_quality, availability_basis)."""
    start = parse_aware(start_time)
    received = parse_aware(received_at)
    if start is None or received is None:
        return None, "unknown", None
    if received - start <= timedelta(hours=RETRO_OBSERVATION_GRACE_HOURS):
        return received_at, "observed_at_receipt", None
    bound = start + timedelta(hours=RESULT_AVAILABILITY_BOUND_HOURS)
    if bound > received:
        return None, "unknown", None
    return bound.isoformat(), "source_reported", AVAILABILITY_BASIS


def _season_of(date: str) -> int | None:
    try:
        return int(date[:4])
    except (TypeError, ValueError):
        return None


def espn_games_to_rows(
    games: Iterable[Any], *, source: str = "espn", received_at: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in games:
        if not getattr(g, "game_id", None) or not getattr(g, "date", None):
            continue
        status = _STATUS_MAP.get(getattr(g, "status", ""), "scheduled")
        # ESPN's scoreboard does not report an authoritative finalization
        # timestamp. A final observed near game time is knowable no earlier
        # than this receipt; a final observed long after game time is a retro
        # backfill and gets the derived source_reported bound instead of
        # falsely claiming today's receipt as first availability.
        availability: str | None = None
        quality = "observed_at_receipt" if received_at else "unknown"
        basis: str | None = None
        if status == "post" and received_at:
            availability, quality, basis = _final_provenance(g.date, received_at)
        extra: dict[str, Any] = {
            "home_ml": getattr(g, "home_ml", None), "away_ml": getattr(g, "away_ml", None),
            "home_ml_open": getattr(g, "home_ml_open", None),
            "away_ml_open": getattr(g, "away_ml_open", None),
            "odds_provider": getattr(g, "odds_provider", None),
        }
        if basis:
            extra["availability_basis"] = basis
        rows.append({
            "game_id": g.game_id, "league": getattr(g, "league", None),
            "season": _season_of(g.date), "start_time": g.date, "status": status,
            "home": getattr(g, "home", None), "away": getattr(g, "away", None),
            "home_score": getattr(g, "home_score", None),
            "away_score": getattr(g, "away_score", None),
            "source": source,
            "provenance_url": f"espn:{getattr(g, 'league', '')}:{g.game_id}",
            "result_available_at": availability,
            "received_at": received_at,
            "provenance_quality": quality,
            "extra": extra,
        })
    return rows


def espn_games_to_lines(games: Iterable[Any]) -> list[dict[str, Any]]:
    """Moneyline open+close snapshots from the scoreboard's odds block -> lines
    rows (closing-line history that grounds CLV / market-pressure)."""
    lines: list[dict[str, Any]] = []
    for g in games:
        gid, ts = getattr(g, "game_id", None), getattr(g, "date", None)
        if not gid or not ts:
            continue
        book = getattr(g, "odds_provider", None) or "espn"
        for side in ("home", "away"):
            for phase, attr in (("close", f"{side}_ml"), ("open", f"{side}_ml_open")):
                price = getattr(g, attr, None)
                if price is None:
                    continue
                lines.append({
                    "ticker": f"espnml:{gid}:{side}:{phase}", "book": book, "ts": ts,
                    "market_type": "moneyline", "price": float(price),
                    "is_close": phase == "close", "game_id": gid, "source": "espn",
                })
    return lines


def ingest_espn_league(
    store: SportsHistoryStore, client: Any, league: str, *, dates: str | None = None,
    received_at: str | None = None,
) -> dict[str, Any]:
    """Fetch one league's scoreboard and upsert its games + odds lines."""
    try:
        games = list(client.games(league, dates))
    except Exception as exc:  # noqa: BLE001 -- a down feed must not raise
        store.record_ingest("espn", league, dates or "recent",
                            status=f"error:{type(exc).__name__}", rows=0, http={})
        return {"rows": 0, "ok": False, "error": str(exc)[:120]}
    observed_at = received_at or datetime.now(timezone.utc).isoformat()
    rows = espn_games_to_rows(games, received_at=observed_at)
    store.upsert_games(rows)
    lines = espn_games_to_lines(games)
    store.record_lines(lines)
    finals = sum(1 for r in rows if r["status"] == "post")
    store.record_ingest("espn", league, dates or "recent", status="ok",
                        rows=len(rows), http={"finals": finals, "lines": len(lines)})
    return {
        "rows": len(rows), "finals": finals, "lines": len(lines), "ok": True,
        "received_at": observed_at,
    }
