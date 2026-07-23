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
    scoring = tune_scoring_sigmas(store, league)
    out.update(scoring)
    # Rest mean-shift coefficient (challenger): 0.0 is always a candidate, so a
    # league where rest does not predict the winner keeps the σ-only fallback.
    from autonomy.sports.walk_forward import walk_forward_rest

    rest_best = tune_param(
        store, league, walk_forward_rest, "coefficient",
        [0.0, 0.03, 0.06, 0.09, 0.12, 0.16],
    )
    if rest_best is not None:
        out["rest_shift"] = rest_best
    if league == "nfl":
        # EPA covers NFL only today; the walk-forward returns n=0 elsewhere
        # so other leagues would just be wasted grid passes.
        from autonomy.sports.walk_forward import walk_forward_epa

        for name, pname, grid in (
            ("epa_home_edge", "home_edge_epa", [0.0, 0.03, 0.06, 0.09, 0.12]),
            ("epa_scale", "scale", [4.0, 6.0, 8.0, 10.0, 12.0]),
        ):
            best = tune_param(store, league, walk_forward_epa, pname, grid)
            if best is not None:
                out[name] = best
    return out


# Sigma grid multipliers around each league's reviewable prior. Winner hit
# rate cannot select sigma (monotone transform), so the objective is the
# out-of-sample mean normal log-likelihood of realized margins/totals.
_SIGMA_MULTIPLIERS = (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.35)
_SIGMA_MIN_GAMES = 40


def tune_scoring_sigmas(
    store: SportsHistoryStore, league: str,
) -> dict[str, Any]:
    from autonomy.sports.scoring_model import _LEAGUE_PARAMS
    from autonomy.sports.walk_forward import (
        collect_scoring_residuals,
        sigma_log_likelihood,
    )

    _edge, prior_margin, prior_total = _LEAGUE_PARAMS.get(league, (2.0, 12.0, 14.0))
    residuals = collect_scoring_residuals(store, league)
    if len(residuals) < _SIGMA_MIN_GAMES:
        return {}
    margins = [m for m, _t in residuals]
    totals = [t for _m, t in residuals]
    out: dict[str, Any] = {}
    for key, param, prior, values in (
        ("scoring_sigma_margin", "sigma_margin", prior_margin, margins),
        ("scoring_sigma_total", "sigma_total", prior_total, totals),
    ):
        best_value: float | None = None
        best_ll: float | None = None
        for multiplier in _SIGMA_MULTIPLIERS:
            sigma = round(prior * multiplier, 3)
            ll = sigma_log_likelihood(values, sigma)
            if ll is None:
                continue
            if best_ll is None or ll > best_ll:
                best_ll, best_value = ll, sigma
        if best_value is not None:
            entry: dict[str, Any] = {
                "param": param, "value": best_value,
                "edge": round(best_ll, 5), "objective": "mean_normal_loglik",
                "n": len(values), "prior": prior,
            }
            pbp = _pbp_sigma_disclosure(league, param)
            if pbp is not None:
                entry["pbp_empirical_sigma"] = pbp
            out[key] = entry
    return out


def _pbp_sigma_disclosure(league: str, param: str) -> float | None:
    """Empirical PBP-lake sigma for cross-checking, never for selection."""
    try:
        from autonomy.sports.pbp_params import load_pbp_params

        block = load_pbp_params(league)
        if block is None:
            return None
        metric = block.get("margin" if param == "sigma_margin" else "total")
        sigma = (metric or {}).get("sigma")
        return float(sigma) if isinstance(sigma, (int, float)) else None
    except Exception:  # noqa: BLE001
        return None


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
