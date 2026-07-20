"""Phase 4: self-tuning — walk-forward each analytic across its key parameter.

The analytics ship reviewable priors (home-field edge, logistic scale). This
closes the recursive loop: for each league, replay the lake across a grid of a
parameter value, keep the one that MAXIMIZES the point-in-time edge over a coin
flip, and persist it. The live signals then load the tuned value (falling back
to the prior). Because the walk-forward is strictly point-in-time, tuning on the
lake never peeks at a game's own result -- it optimizes the method, not the
answer.

Pure/offline; reads the lake, writes a small JSON the signals consume.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from autonomy.sports.history_store import SportsHistoryStore

TUNED_PATH = Path("runtime/autonomy/sports_tuned_params.json")


def tune_param(
    store: SportsHistoryStore, league: str, wf_fn: Callable[..., dict[str, Any]],
    param_name: str, grid: list[float], *, min_n: int = 40,
) -> dict[str, Any] | None:
    """Grid-search one analytic's parameter; return the edge-maximizing value."""
    best: dict[str, Any] | None = None
    for value in grid:
        report = wf_fn(store, league=league, **{param_name: value})
        if not report.get("n") or report["n"] < min_n:
            continue
        edge = report.get("edge_vs_baseline")
        if edge is None:
            continue
        if best is None or edge > best["edge"]:
            best = {"param": param_name, "value": value, "edge": round(edge, 5),
                    "hit_rate": report.get("hit_rate"), "n": report["n"]}
    return best


def tune_league(store: SportsHistoryStore, league: str) -> dict[str, Any]:
    """Tune every analytic that has a tunable parameter for one league."""
    from autonomy.sports.walk_forward import (
        walk_forward_four_factors, walk_forward_glicko, walk_forward_mov_elo,
        walk_forward_pythagorean,
    )

    ha = [20.0, 30.0, 40.0, 50.0, 60.0]
    hap = [0.0, 0.02, 0.04, 0.06, 0.08]
    out: dict[str, Any] = {}
    for name, fn, pname, grid in (
        ("glicko", walk_forward_glicko, "home_advantage", ha),
        ("mov_elo", walk_forward_mov_elo, "home_advantage", ha),
        ("pythagenpat", walk_forward_pythagorean, "home_advantage_prob", hap),
        ("four_factors", walk_forward_four_factors, "home_advantage_prob", hap),
    ):
        best = tune_param(store, league, fn, pname, grid)
        if best is not None:
            out[name] = best
    return out


def tune_all(store: SportsHistoryStore, leagues: list[str], *, path: Path | None = None) -> dict[str, Any]:
    tuned = {lg: tune_league(store, lg) for lg in leagues}
    tuned = {lg: v for lg, v in tuned.items() if v}
    target = path or TUNED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    from datetime import datetime, timezone

    tmp.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                               "leagues": tuned}), encoding="utf-8")
    tmp.replace(target)
    return tuned


def load_tuned(league: str, analytic: str, param: str, default: float,
               path: Path | None = None) -> float:
    """The tuned value for (league, analytic, param), or ``default``. Used by the
    live signals so a tuning run auto-improves them with no code change."""
    try:
        blob = json.loads((path or TUNED_PATH).read_text(encoding="utf-8"))
        entry = ((blob.get("leagues") or {}).get(league) or {}).get(analytic)
        if entry and entry.get("param") == param and entry.get("value") is not None:
            return float(entry["value"])
    except Exception:  # noqa: BLE001
        pass
    return default
