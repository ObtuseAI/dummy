"""Phase 1 adapter: wehoop WNBA schedules -> lake (deep in-season history).

wehoop-data publishes per-season WNBA schedules as open CSV (back to 2002),
using ESPN's own game ids + team abbreviations -- so these rows DEDUP with the
ESPN-sourced WNBA games already in the lake (same game_id) and match the live
signal's ESPN team codes. Turns the WNBA lake from ~2 seasons into ~20, which
measurably sharpens the rating analytics. Pure-stdlib CSV; polite fetch.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.ingest.provenance import stamp_retro_source_reported
from autonomy.sports.history_store import SportsHistoryStore

WEHOOP_WNBA_URL = (
    "https://raw.githubusercontent.com/sportsdataverse/wehoop-data/main/"
    "wnba/schedules/csv/wnba_schedule_{season}.csv"
)


def _int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() in ("", "NA"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_wehoop_schedule(text: str, season: int, *, league: str = "wnba", url: str = "") -> list[dict[str, Any]]:
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
            "source": "wehoop", "provenance_url": url,
        })
    return out


def ingest_wehoop_wnba(
    store: SportsHistoryStore, fetcher: PoliteFetcher, seasons: Iterable[int], *,
    url_tmpl: str = WEHOOP_WNBA_URL,
) -> dict[str, Any]:
    total = 0
    ok_seasons = 0
    for season in seasons:
        url = url_tmpl.format(season=int(season))
        resp = fetcher.get(url)
        if not resp.ok:
            continue
        rows = parse_wehoop_schedule(resp.text, int(season), url=url)
        stamp_retro_source_reported(rows)
        total += store.upsert_games(rows)
        ok_seasons += 1
    store.record_ingest("wehoop", "wnba", f"{min(seasons)}-{max(seasons)}" if seasons else "all",
                        status="ok", rows=total, http={"seasons": ok_seasons})
    return {"rows": total, "seasons": ok_seasons}
