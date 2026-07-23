"""Fail-closed reader for the play-by-play knowledge artifact.

Consumers (scoring model validation, simulators, live re-pricing research)
call :func:`load_pbp_params` and must treat ``None`` as "no knowledge" —
the artifact grants no authority and its absence changes nothing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autonomy.ingest.pbp_lake import ARTIFACT_VERSION, DEFAULT_ARTIFACT_PATH


def load_pbp_params(
    league: str, *, path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Return the league's PBP knowledge block, or None when unavailable."""
    # Resolve the default at call time so the artifact path stays overridable
    # (tests, alternate runtimes) after import.
    target = Path(path if path is not None else DEFAULT_ARTIFACT_PATH)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get("artifact_version") != ARTIFACT_VERSION:
        return None
    leagues = document.get("leagues")
    if not isinstance(leagues, dict):
        return None
    block = leagues.get(str(league).lower())
    if not isinstance(block, dict) or not block.get("games"):
        return None
    return block


def in_game_home_win_prior(
    league: str,
    *,
    period_completed: int,
    home_lead: int,
    path: Path | str | None = None,
    min_cell_n: int = 30,
) -> dict[str, Any] | None:
    """Empirical P(home win | lead entering next period), or None.

    Research prior only: returns the matched comeback-matrix cell with its
    sample size so a consumer can weigh (or refuse) thin evidence.
    """
    from autonomy.ingest.pbp_lake import lead_bucket

    block = load_pbp_params(league, path=path)
    if block is None:
        return None
    pooled = block.get("per_season") or {}
    bucket = lead_bucket(int(home_lead))
    n_total = 0
    wins_weighted = 0.0
    for season_block in pooled.values():
        matrix = (season_block or {}).get("comeback") or {}
        cell = (matrix.get(f"after_period_{int(period_completed)}") or {}).get(bucket)
        if not isinstance(cell, dict):
            continue
        n = int(cell.get("n") or 0)
        rate = cell.get("home_win_rate")
        if n <= 0 or not isinstance(rate, (int, float)):
            continue
        n_total += n
        wins_weighted += n * float(rate)
    if n_total < min_cell_n:
        return None
    return {
        "league": str(league).lower(),
        "period_completed": int(period_completed),
        "lead_bucket": bucket,
        "n": n_total,
        "home_win_rate": round(wins_weighted / n_total, 4),
        "authority": "research_prior_only",
    }
