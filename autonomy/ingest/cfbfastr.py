"""Phase 1 adapter: cfbfastR college-football game results -> history lake.

NCAAF play-by-play (with EPA) is only published as parquet (needs pyarrow, which
this codebase forbids) or behind the key-gated CollegeFootballData API -- so EPA
is out of bounds. But cfbfastR-data's games INDEX is an open, stdlib-parseable
CSV of multi-season college-football results, which is exactly what the rating
analytics (Glicko-2 / MOV-Elo / Pythagenpat) need. This adapter ingests it so
NCAAF gets real lake analytics in-bounds -- winner ratings, just not EPA.

Pure-stdlib CSV parse; fetch via the polite framework (cached, rate-limited).
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.ingest.provenance import stamp_retro_source_reported
from autonomy.sports.history_store import SportsHistoryStore

CFBD_GAMES_URL = (
    "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/"
    "pbp/cfb_games_in_data_repo.csv"
)


def _int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() in ("", "NA"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_cfbd_games(
    text: str, *, url: str = CFBD_GAMES_URL, seasons: set[int] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        season = _int(row.get("season"))
        if season is None or (seasons and season not in seasons):
            continue
        start = (row.get("start_date") or "").strip()
        gid = (row.get("game_id") or "").strip()
        home, away = row.get("home_team"), row.get("away_team")
        if not start or not gid or not home or not away:
            continue
        hp, ap = _int(row.get("home_points")), _int(row.get("away_points"))
        status = "final" if hp is not None and ap is not None else "scheduled"
        out.append({
            "game_id": f"cfb-{gid}", "league": "ncaaf", "season": season,
            "start_time": start, "status": status, "home": home, "away": away,
            "home_score": hp, "away_score": ap, "source": "cfbfastr",
            "provenance_url": url,
            "extra": {"home_conference": row.get("home_conference"),
                      "away_conference": row.get("away_conference"), "week": row.get("week")},
        })
    return out


def ingest_cfbd_games(
    store: SportsHistoryStore, fetcher: PoliteFetcher, *,
    url: str = CFBD_GAMES_URL, seasons: Iterable[int] | None = None,
) -> dict[str, Any]:
    season_set = {int(s) for s in seasons} if seasons is not None else None
    resp = fetcher.get(url)
    if not resp.ok:
        store.record_ingest("cfbfastr", "ncaaf", None, status=f"http_{resp.status}", rows=0, http={})
        return {"rows": 0, "ok": False, "status": resp.status}
    games = parse_cfbd_games(resp.text, url=url, seasons=season_set)
    stamp_retro_source_reported(games)
    store.upsert_games(games)
    date_range = f"{min(season_set)}-{max(season_set)}" if season_set else "all"
    store.record_ingest("cfbfastr", "ncaaf", date_range, status="ok",
                        rows=len(games), http=dict(fetcher.stats))
    return {"rows": len(games), "ok": True, "from_cache": resp.from_cache}
