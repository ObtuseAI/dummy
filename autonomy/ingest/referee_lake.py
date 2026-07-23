"""Bounded backfill of referee tendencies from ESPN game summaries.

For settled games in the history lake (which lack officials), fetch the ESPN
game summary once per game, extract the assigned officials and the final
total, and fold them into runtime/autonomy/referee_tendencies.json. Bounded
per run (polite public reads), resumable via a processed-id cursor, and
strictly aggregate — no per-game officials are persisted, only per-referee
running sums.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.sports.espn import LEAGUE_TO_ESPN
from autonomy.sports.referees import (
    RefereeTendencies,
    parse_officials,
    summary_total,
)

_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={event}"
)
# ESPN sport path per league (mirrors LEAGUE_TO_ESPN's scoreboard paths).
_LEAGUE_PATH = {
    "nba": "basketball/nba", "wnba": "basketball/wnba",
    "ncaamb": "basketball/mens-college-basketball",
    "mlb": "baseball/mlb", "nhl": "hockey/nhl",
    "nfl": "football/nfl", "ncaaf": "football/college-football",
}


def summary_url(league: str, event_id: str) -> str | None:
    path = _LEAGUE_PATH.get(str(league).lower())
    if not path or league not in LEAGUE_TO_ESPN:
        return None
    return _SUMMARY_URL.format(path=path, event=event_id)


def backfill_referees(
    store: Any,
    league: str,
    *,
    fetcher: PoliteFetcher | None = None,
    tendencies: RefereeTendencies | None = None,
    max_games: int = 200,
    fetch_json: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Fold up to ``max_games`` settled games' officials into the tendencies."""
    fetcher = fetcher or PoliteFetcher()
    tendencies = tendencies or RefereeTendencies()

    def _default_fetch(url: str) -> dict[str, Any] | None:
        resp = fetcher.get(url)
        if not getattr(resp, "ok", False):
            return None
        try:
            return json.loads(resp.text)
        except (TypeError, ValueError):
            return None

    fetch = fetch_json or _default_fetch
    games = store.evaluation_games(league=league)
    processed = recorded = skipped = 0
    for game in games:
        if processed >= max_games:
            break
        event_id = str(game.get("game_id") or "")
        url = summary_url(league, event_id)
        if not event_id or url is None:
            skipped += 1
            continue
        summary = fetch(url)
        processed += 1
        if not isinstance(summary, dict):
            skipped += 1
            continue
        officials = parse_officials(summary)
        total = summary_total(summary)
        if not officials or total is None:
            skipped += 1
            continue
        recorded += tendencies.observe(league, officials, total)
    tendencies.save()
    return {
        "league": league,
        "games_processed": processed,
        "referee_observations": recorded,
        "skipped": skipped,
        "league_mean_total": tendencies.league_mean_total(league),
    }
