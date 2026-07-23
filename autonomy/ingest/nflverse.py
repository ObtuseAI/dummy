"""Phase 1 adapter: nflverse game results into the history lake.

nflverse (https://github.com/nflverse) publishes NFL data under an open licence
as flat CSV — no key, no scraping, no ToS grey area. ``games.csv`` is the
multi-decade schedule+results table; we parse it with the stdlib and upsert one
row per game into :class:`SportsHistoryStore`. Point-in-time is preserved: a
game with no final score lands as ``scheduled`` and is invisible to
``games_before`` until it actually finishes.

Fail-soft: a down feed or malformed row records an ingest-log failure and
returns a zero-row result rather than raising — the backfill is resumable.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.ingest.provenance import stamp_retro_source_reported
from autonomy.sports.history_store import SportsHistoryStore

# The canonical open games table (schedule + results, 1999-present).
NFLVERSE_GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"


def _int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_nflverse_games(
    text: str, *, url: str = NFLVERSE_GAMES_URL, seasons: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Parse a nflverse games.csv into history-store game rows."""
    out: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        season = _int(row.get("season"))
        if season is None or (seasons and season not in seasons):
            continue
        gameday = (row.get("gameday") or "").strip()
        if not gameday:
            continue
        gametime = (row.get("gametime") or "00:00").strip() or "00:00"
        home_score, away_score = _int(row.get("home_score")), _int(row.get("away_score"))
        status = "final" if home_score is not None and away_score is not None else "scheduled"
        home, away = row.get("home_team"), row.get("away_team")
        gid = (row.get("game_id") or f"nfl-{season}-{row.get('week')}-{away}-{home}").strip()
        out.append({
            "game_id": gid, "league": "nfl", "season": season,
            "start_time": f"{gameday}T{gametime}:00Z", "status": status,
            "home": home, "away": away, "home_score": home_score, "away_score": away_score,
            "source": "nflverse", "provenance_url": url,
            "extra": {"week": row.get("week"), "game_type": row.get("game_type")},
        })
    return out


def ingest_nflverse_games(
    store: SportsHistoryStore, fetcher: PoliteFetcher, *,
    url: str = NFLVERSE_GAMES_URL, seasons: Iterable[int] | None = None,
) -> dict[str, Any]:
    """Fetch + parse + upsert nflverse games. Idempotent (cache-backed)."""
    season_set = set(int(s) for s in seasons) if seasons is not None else None
    resp = fetcher.get(url)
    if not resp.ok:
        store.record_ingest("nflverse", "nfl", None, status=f"http_{resp.status}",
                            rows=0, http=dict(fetcher.stats))
        return {"rows": 0, "ok": False, "status": resp.status}
    games = parse_nflverse_games(resp.text, url=url, seasons=season_set)
    stamp_retro_source_reported(games)
    store.upsert_games(games)
    date_range = (
        f"{min(season_set)}-{max(season_set)}" if season_set else "all"
    )
    store.record_ingest("nflverse", "nfl", date_range, status="ok",
                        rows=len(games), http=dict(fetcher.stats))
    return {"rows": len(games), "ok": True, "from_cache": resp.from_cache}
