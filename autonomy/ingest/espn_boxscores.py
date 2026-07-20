"""Phase 1 adapter: ESPN game boxscores -> history lake (for four factors).

One ESPN summary fetch per game (keyless), parsed to team-level boxscores via
the existing :mod:`autonomy.sports.boxscores` pipeline and upserted into the
lake. Resumable: only games missing boxscores are fetched, so a re-run costs
nothing. Fail-soft per game (a bad summary is skipped, never fatal). Polite:
a per-game sleep bounds the request rate.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from autonomy.sports.history_store import SportsHistoryStore


def ingest_boxscores(
    store: SportsHistoryStore, league: str, *,
    fetch_summary: Callable[[str, str], dict[str, Any]] | None = None,
    parse: Callable[[str, dict[str, Any] | None], list[Any]] | None = None,
    limit: int | None = None, min_interval: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    from autonomy.sports.boxscores import fetch_summary as _fetch, parse_team_boxscores as _parse

    fetch_summary = fetch_summary or _fetch
    parse = parse or _parse

    game_ids = store.game_ids_missing_boxscores(league, limit=limit)
    games_done = rows = errors = 0
    for i, gid in enumerate(game_ids):
        try:
            boxes = parse(league, fetch_summary(league, gid))
        except Exception:  # noqa: BLE001 -- a down/odd summary just gets skipped
            errors += 1
            continue
        if not boxes:
            continue
        rows += store.record_team_boxscores(
            [{"game_id": b.game_id, "team": b.team, "stats": b.stats} for b in boxes]
        )
        games_done += 1
        if min_interval and i < len(game_ids) - 1:
            sleep(min_interval)
    store.record_ingest("espn_box", league, None, status="ok", rows=rows,
                        http={"games": games_done, "errors": errors, "queued": len(game_ids)})
    return {"games": games_done, "rows": rows, "errors": errors, "queued": len(game_ids)}
