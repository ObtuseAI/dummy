"""Phase 1 adapter: sportsdataverse open schedule CSVs -> lake, every league.

The sportsdataverse data repos publish per-season schedule CSVs (open, no key,
ESPN schema: game id + team abbreviations + scores + completed flag) for every
league Dummy trades that isn't already deep. Same parser across all of them, so
one adapter deepens NBA / NCAAMB / NHL / WNBA history from ~2 ESPN seasons to
~20. ESPN game ids + abbreviations mean the rows DEDUP with the ESPN-sourced
games and match the live signals. Pure-stdlib CSV; polite fetch.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.sports.history_store import SportsHistoryStore

# league -> (repo, path prefix, file prefix)
SDV_SOURCES: dict[str, tuple[str, str, str]] = {
    "wnba": ("wehoop-data", "wnba", "wnba"),
    "nba": ("hoopR-data", "nba", "nba"),
    "ncaamb": ("hoopR-data", "mbb", "mbb"),
    "nhl": ("fastRhockey-data", "nhl", "nhl"),
}
_URL = ("https://raw.githubusercontent.com/sportsdataverse/{repo}/main/"
        "{path}/schedules/csv/{prefix}_schedule_{season}.csv")


def _int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() in ("", "NA"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_sdv_schedule(text: str, league: str, season: int, *, url: str = "") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        gid = (row.get("id") or "").strip()
        home, away = row.get("home_abbreviation"), row.get("away_abbreviation")
        date = (row.get("date") or row.get("start_date") or "").strip()
        if not gid or not home or not away or not date:
            continue
        hs, as_ = _int(row.get("home_score")), _int(row.get("away_score"))
        completed = str(row.get("status_type_completed")).strip().lower() in ("true", "1")
        status = "final" if completed and hs is not None and as_ is not None else "scheduled"
        out.append({
            "game_id": gid, "league": league, "season": season, "start_time": date,
            "status": status, "home": home, "away": away, "home_score": hs, "away_score": as_,
            "source": "sportsdataverse", "provenance_url": url,
        })
    return out


def ingest_sdv_schedule(
    store: SportsHistoryStore, fetcher: PoliteFetcher, league: str, seasons: Iterable[int],
) -> dict[str, Any]:
    if league not in SDV_SOURCES:
        return {"rows": 0, "ok": False, "reason": f"no sdv source for {league}"}
    repo, path, prefix = SDV_SOURCES[league]
    seasons = list(seasons)
    total = ok = 0
    for season in seasons:
        url = _URL.format(repo=repo, path=path, prefix=prefix, season=int(season))
        resp = fetcher.get(url)
        if not resp.ok:
            continue
        total += store.upsert_games(parse_sdv_schedule(resp.text, league, int(season), url=url))
        ok += 1
    store.record_ingest("sportsdataverse", league,
                        f"{min(seasons)}-{max(seasons)}" if seasons else "all",
                        status="ok", rows=total, http={"seasons": ok})
    return {"rows": total, "seasons": ok, "ok": True}
