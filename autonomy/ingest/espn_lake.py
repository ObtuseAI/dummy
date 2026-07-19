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

from typing import Any, Iterable

from autonomy.sports.history_store import SportsHistoryStore

_STATUS_MAP = {"post": "post", "in": "in", "pre": "scheduled"}


def _season_of(date: str) -> int | None:
    try:
        return int(date[:4])
    except (TypeError, ValueError):
        return None


def espn_games_to_rows(games: Iterable[Any], *, source: str = "espn") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in games:
        if not getattr(g, "game_id", None) or not getattr(g, "date", None):
            continue
        status = _STATUS_MAP.get(getattr(g, "status", ""), "scheduled")
        rows.append({
            "game_id": g.game_id, "league": getattr(g, "league", None),
            "season": _season_of(g.date), "start_time": g.date, "status": status,
            "home": getattr(g, "home", None), "away": getattr(g, "away", None),
            "home_score": getattr(g, "home_score", None),
            "away_score": getattr(g, "away_score", None),
            "source": source,
            "provenance_url": f"espn:{getattr(g, 'league', '')}:{g.game_id}",
            "extra": {
                "home_ml": getattr(g, "home_ml", None), "away_ml": getattr(g, "away_ml", None),
                "home_ml_open": getattr(g, "home_ml_open", None),
                "away_ml_open": getattr(g, "away_ml_open", None),
                "odds_provider": getattr(g, "odds_provider", None),
            },
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
) -> dict[str, Any]:
    """Fetch one league's scoreboard and upsert its games + odds lines."""
    try:
        games = client.games(league, dates)
    except Exception as exc:  # noqa: BLE001 -- a down feed must not raise
        store.record_ingest("espn", league, dates or "recent",
                            status=f"error:{type(exc).__name__}", rows=0, http={})
        return {"rows": 0, "ok": False, "error": str(exc)[:120]}
    rows = espn_games_to_rows(games)
    store.upsert_games(rows)
    lines = espn_games_to_lines(games)
    store.record_lines(lines)
    finals = sum(1 for r in rows if r["status"] == "post")
    store.record_ingest("espn", league, dates or "recent", status="ok",
                        rows=len(rows), http={"finals": finals, "lines": len(lines)})
    return {"rows": len(rows), "finals": finals, "lines": len(lines), "ok": True}
