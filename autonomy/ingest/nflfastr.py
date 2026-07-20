"""Phase 1 adapter: nflfastR play-by-play EPA -> lake (for the EPA analytic).

nflfastR (nflverse) publishes NFL play-by-play with **EPA already computed** as
open data -- so we ingest the gold-standard efficiency metric directly rather
than reconstruct it. We don't store 50k plays/season; we aggregate each play's
EPA to per-(game, team) offense (posteam) and defense-allowed (defteam) sums and
persist those as boxscore-style rows. The nflfastR ``game_id`` matches the
nflverse ``games.csv`` ids already in the lake, so the EPA rows join to games
for free. Point-in-time falls out of the games' start_time.

Pure-stdlib parse; fetch is injectable (deterministic under test, no network).
"""
from __future__ import annotations

import csv
import gzip
import io
from typing import Any, Callable, Iterable

NFLFASTR_PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/pbp/"
    "play_by_play_{season}.csv.gz"
)


def aggregate_epa(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-(game, team) EPA: a team's offensive EPA (as posteam) and the EPA it
    allowed (as defteam), with play counts. -> boxscore rows for the lake."""
    acc: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        try:
            epa = float(row.get("epa"))
        except (TypeError, ValueError):
            continue
        gid, off, deff = row.get("game_id"), row.get("posteam"), row.get("defteam")
        if not gid or not off or not deff or off == "NA" or deff == "NA":
            continue
        a = acc.setdefault((gid, off), {"off_epa": 0.0, "off_plays": 0.0, "def_epa": 0.0, "def_plays": 0.0})
        a["off_epa"] += epa
        a["off_plays"] += 1.0
        d = acc.setdefault((gid, deff), {"off_epa": 0.0, "off_plays": 0.0, "def_epa": 0.0, "def_plays": 0.0})
        d["def_epa"] += epa
        d["def_plays"] += 1.0
    return [{"game_id": gid, "team": team, "stats": stats} for (gid, team), stats in acc.items()]


def parse_pbp_csv(text: str) -> list[dict[str, Any]]:
    return list(csv.DictReader(io.StringIO(text)))


def _default_fetch(season: int) -> str:
    import httpx

    resp = httpx.get(NFLFASTR_PBP_URL.format(season=season), timeout=180, follow_redirects=True)
    resp.raise_for_status()
    return gzip.decompress(resp.content).decode("utf-8", "ignore")


def ingest_nflfastr_epa(
    store: Any, seasons: Iterable[int], *,
    fetch: Callable[[int], str] | None = None,
) -> dict[str, Any]:
    fetch = fetch or _default_fetch
    total = 0
    team_games = 0
    for season in seasons:
        try:
            text = fetch(int(season))
        except Exception:  # noqa: BLE001 -- a down/missing season is skipped
            store.record_ingest("nflfastr", "nfl", str(season), status="error", rows=0, http={})
            continue
        agg = aggregate_epa(parse_pbp_csv(text))
        total += store.record_team_boxscores(agg)
        team_games += len(agg)
        store.record_ingest("nflfastr", "nfl", str(season), status="ok",
                            rows=len(agg), http={"team_games": len(agg)})
    return {"rows": total, "team_games": team_games}
