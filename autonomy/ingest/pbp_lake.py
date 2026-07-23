"""Play-by-play knowledge lake: open PBP archives -> compact league priors.

Feeds Dummy an empirical understanding of the games behind the markets it
prices — how scoring actually distributes, how often leads survive, what a
line move "should" look like after a scoring run — from full play-by-play
archives (sportsdataverse hoopR / wehoop repos, ESPN schema, open CSVs, no
key). Raw PBP is streamed and folded per season; only bounded aggregates are
kept:

- empirical final margin / total distributions (spread & total calibration);
- per-period scoring profile (segment-market priors);
- comeback matrix: P(home win | home lead bucket entering period) — an
  in-game win-probability prior for live re-pricing research;
- pace/efficiency proxies (events, shooting plays, points per shot).

Everything lands in ``runtime/autonomy/sports_pbp_params.json`` as a
knowledge artifact with zero execution / promotion / fusion authority.
Models and simulators may consume it only through their own challenger
walk-forward validation.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

ARTIFACT_VERSION = "sports_pbp_params_v1"
DEFAULT_ARTIFACT_PATH = Path("runtime/autonomy/sports_pbp_params.json")
USER_AGENT = "dummy-research/1.0 (open-data ingest; contact: local)"
FETCH_TIMEOUT_SECONDS = 180.0
POLITE_SLEEP_SECONDS = 2.0

# league -> (repo, path, regulation_periods). ESPN-schema PBP repos only, so
# game ids / team ids line up with the schedule lake. NCAAMB plays halves.
PBP_SOURCES: dict[str, tuple[str, str, int]] = {
    "wnba": ("wehoop-data", "wnba", 4),
    "nba": ("hoopR-data", "nba", 4),
    "ncaamb": ("hoopR-data", "mbb", 2),
}
_URL = ("https://raw.githubusercontent.com/sportsdataverse/{repo}/main/"
        "{path}/pbp/csv/play_by_play_{season}.csv.gz")

# Home-lead buckets entering a period (upper-exclusive edges, cents-free).
LEAD_BUCKET_EDGES: tuple[int, ...] = (-15, -10, -6, -3, -1, 1, 3, 6, 10, 15)


def lead_bucket(lead: int) -> str:
    """Stable label for a home-lead bucket, e.g. ``[-3,-1)`` or ``>=15``."""
    if lead < LEAD_BUCKET_EDGES[0]:
        return f"<{LEAD_BUCKET_EDGES[0]}"
    for low, high in zip(LEAD_BUCKET_EDGES, LEAD_BUCKET_EDGES[1:]):
        if low <= lead < high:
            return f"[{low},{high})"
    return f">={LEAD_BUCKET_EDGES[-1]}"


def pbp_season_url(league: str, season: int) -> str:
    repo, path, _periods = PBP_SOURCES[league]
    return _URL.format(repo=repo, path=path, season=int(season))


def _int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() in ("", "NA"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def stream_pbp_rows(
    league: str,
    season: int,
    *,
    opener: Callable[[str], io.BufferedIOBase] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[dict[str, Any]]:
    """Stream the season's PBP rows (selected columns only) without caching.

    The gz body is spooled to a temporary file (25-70MB compressed for the
    big leagues) and deleted afterwards; rows never accumulate in memory.
    """
    url = pbp_season_url(league, season)
    if opener is None:
        def opener(target: str) -> io.BufferedIOBase:  # pragma: no cover
            request = urllib.request.Request(
                target, headers={"User-Agent": USER_AGENT},
            )
            return urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS)

    handle, spool_path = tempfile.mkstemp(suffix=".csv.gz")
    try:
        with os.fdopen(handle, "wb") as spool, opener(url) as response:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                spool.write(chunk)
        sleep(POLITE_SLEEP_SECONDS)
        with gzip.open(spool_path, "rt", encoding="utf-8", errors="replace") as text:
            for row in csv.DictReader(text):
                yield {
                    "game_id": (row.get("game_id") or "").strip(),
                    "sequence_number": _int(row.get("sequence_number")),
                    "period_number": _int(row.get("period_number") or row.get("period")),
                    "home_score": _int(row.get("home_score")),
                    "away_score": _int(row.get("away_score")),
                    "scoring_play": str(row.get("scoring_play")).strip().lower() == "true",
                    "shooting_play": str(row.get("shooting_play")).strip().lower() == "true",
                }
    finally:
        try:
            os.unlink(spool_path)
        except OSError:
            pass


class _GameFold:
    __slots__ = ("max_seq", "home", "away", "period_end", "events", "shooting")

    def __init__(self) -> None:
        self.max_seq = -1
        self.home = 0
        self.away = 0
        # period -> (max seq in period, home, away)
        self.period_end: dict[int, tuple[int, int, int]] = {}
        self.events = 0
        self.shooting = 0


def fold_pbp_rows(rows: Iterable[dict[str, Any]]) -> dict[str, _GameFold]:
    """Fold a season's rows into per-game score trajectories."""
    games: dict[str, _GameFold] = {}
    for row in rows:
        game_id = row.get("game_id") or ""
        seq = row.get("sequence_number")
        period = row.get("period_number")
        home = row.get("home_score")
        away = row.get("away_score")
        if not game_id or seq is None or period is None or home is None or away is None:
            continue
        fold = games.setdefault(game_id, _GameFold())
        fold.events += 1
        if row.get("shooting_play"):
            fold.shooting += 1
        if seq >= fold.max_seq:
            fold.max_seq = seq
            fold.home = home
            fold.away = away
        current = fold.period_end.get(period)
        if current is None or seq >= current[0]:
            fold.period_end[period] = (seq, home, away)
    return games


def _distribution(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mean = sum(ordered) / n
    variance = sum((v - mean) ** 2 for v in ordered) / n
    def quantile(q: float) -> float:
        index = min(n - 1, max(0, int(round(q * (n - 1)))))
        return float(ordered[index])
    return {
        "n": n,
        "mean": round(mean, 4),
        "sigma": round(math.sqrt(variance), 4),
        "p10": quantile(0.10),
        "p50": quantile(0.50),
        "p90": quantile(0.90),
    }


def aggregate_league_season(
    games: dict[str, _GameFold], *, regulation_periods: int,
) -> dict[str, Any]:
    """Bounded aggregates for one league season from folded games."""
    margins: list[float] = []
    totals: list[float] = []
    overtime = 0
    period_home: dict[int, list[int]] = {}
    period_away: dict[int, list[int]] = {}
    comeback: dict[int, dict[str, list[int]]] = {}
    events: list[int] = []
    shooting: list[int] = []
    points_per_shot: list[float] = []

    for fold in games.values():
        if fold.max_seq < 0 or (fold.home == 0 and fold.away == 0):
            continue
        margins.append(float(fold.home - fold.away))
        totals.append(float(fold.home + fold.away))
        events.append(fold.events)
        shooting.append(fold.shooting)
        if fold.shooting:
            points_per_shot.append((fold.home + fold.away) / fold.shooting)
        if any(p > regulation_periods for p in fold.period_end):
            overtime += 1
        previous = (0, 0)
        home_won = fold.home > fold.away
        for period in range(1, regulation_periods + 1):
            end = fold.period_end.get(period)
            if end is None:
                break
            _seq, home, away = end
            period_home.setdefault(period, []).append(home - previous[0])
            period_away.setdefault(period, []).append(away - previous[1])
            previous = (home, away)
            if period < regulation_periods:
                bucket = lead_bucket(home - away)
                cell = comeback.setdefault(period, {}).setdefault(bucket, [0, 0])
                cell[0] += 1
                cell[1] += 1 if home_won else 0

    return {
        "games": len(margins),
        "margin": _distribution(margins),
        "total": _distribution(totals),
        "ot_rate": round(overtime / len(margins), 4) if margins else None,
        "period_profile": {
            str(period): {
                "home_mean": round(sum(vals) / len(vals), 3),
                "away_mean": round(
                    sum(period_away[period]) / len(period_away[period]), 3,
                ),
            }
            for period, vals in sorted(period_home.items())
            if period_away.get(period)
        },
        "comeback": {
            f"after_period_{period}": {
                bucket: {
                    "n": cell[0],
                    "home_win_rate": round(cell[1] / cell[0], 4),
                }
                for bucket, cell in sorted(cells.items())
                if cell[0] >= 10  # tiny cells disclose nothing reliable
            }
            for period, cells in sorted(comeback.items())
        },
        "pace_proxy": {
            "events_per_game": round(sum(events) / len(events), 2) if events else None,
            "shooting_plays_per_game": (
                round(sum(shooting) / len(shooting), 2) if shooting else None
            ),
            "points_per_shooting_play": (
                round(sum(points_per_shot) / len(points_per_shot), 4)
                if points_per_shot else None
            ),
        },
    }


def merge_seasons(per_season: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Pooled league view: recompute pooled distributions from season blocks.

    Pooled sigma uses the law of total variance over season blocks so the
    artifact never needs raw per-game values.
    """
    blocks = [b for b in per_season.values() if b.get("games")]
    games = sum(b["games"] for b in blocks)

    def pooled(metric: str) -> dict[str, float] | None:
        rows = [
            (b["games"], b[metric]) for b in blocks
            if isinstance(b.get(metric), dict)
        ]
        if not rows or games <= 0:
            return None
        weight = sum(n for n, _d in rows)
        mean = sum(n * d["mean"] for n, d in rows) / weight
        variance = sum(
            n * (d["sigma"] ** 2 + (d["mean"] - mean) ** 2) for n, d in rows
        ) / weight
        return {
            "n": weight,
            "mean": round(mean, 4),
            "sigma": round(math.sqrt(variance), 4),
        }

    return {
        "games": games,
        "seasons": sorted(per_season),
        "margin": pooled("margin"),
        "total": pooled("total"),
        "per_season": {str(season): block for season, block in sorted(per_season.items())},
    }


def write_pbp_artifact(
    leagues: dict[str, dict[str, Any]],
    *,
    path: Path | str = DEFAULT_ARTIFACT_PATH,
    now: datetime | None = None,
) -> Path:
    """Atomically merge league blocks into the knowledge artifact."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
    merged = dict(existing.get("leagues") or {})
    merged.update(leagues)
    document = {
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "leagues": merged,
        "authority": {
            "execution": False, "promotion": False, "fusion": False,
        },
        "consumption_note": (
            "Knowledge base only. Simulators and pricing models may consume "
            "these priors solely through their own challenger walk-forward "
            "validation; nothing here changes a live weight by itself."
        ),
    }
    handle, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def ingest_pbp_seasons(
    league: str,
    seasons: Iterable[int],
    *,
    opener: Callable[[str], io.BufferedIOBase] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    artifact_path: Path | str = DEFAULT_ARTIFACT_PATH,
) -> dict[str, Any]:
    """Fetch, fold, aggregate, and persist one league's PBP seasons."""
    if league not in PBP_SOURCES:
        return {"ok": False, "reason": f"no pbp source for {league}"}
    _repo, _path, regulation = PBP_SOURCES[league]
    per_season: dict[int, dict[str, Any]] = {}
    urls: list[str] = []
    for season in seasons:
        season = int(season)
        try:
            rows = stream_pbp_rows(league, season, opener=opener, sleep=sleep)
            folded = fold_pbp_rows(rows)
        except Exception as exc:  # noqa: BLE001 - one bad season never aborts the run
            per_season[season] = {"games": 0, "error": f"{type(exc).__name__}"}
            continue
        block = aggregate_league_season(folded, regulation_periods=regulation)
        block["source_url"] = pbp_season_url(league, season)
        urls.append(block["source_url"])
        per_season[season] = block
    league_block = merge_seasons(per_season)
    league_block["regulation_periods"] = regulation
    league_block["source_urls"] = urls
    write_pbp_artifact({league: league_block}, path=artifact_path)
    return {
        "ok": True,
        "league": league,
        "games": league_block["games"],
        "seasons": league_block["seasons"],
        "artifact": str(artifact_path),
    }
