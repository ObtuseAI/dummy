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
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from autonomy.sports.history_store import SportsHistoryStore

TUNED_PATH = Path("runtime/autonomy/sports_tuned_params.json")


def tune_param(
    store: SportsHistoryStore, league: str, wf_fn: Callable[..., dict[str, Any]],
    param_name: str, grid: list[float], *, min_n: int = 40,
) -> dict[str, Any] | None:
    """Grid-search one analytic's parameter; return the edge-maximizing value.

    Fail-closed on sign: the grid MAXIMUM can still be a refit that is
    measurably worse than the coin-flip baseline (edge <= 0), and persisting
    it would apply a proven-negative parameter live (the 2026-07-24 audit
    caught exactly that for mlb glicko/mov_elo). Such a winner is returned as
    a value-less skip record ("value": None, "skipped": "edge<=0") so the
    decision stays auditable in the artifact while ``load_tuned`` -- which
    requires a non-None "value" -- keeps serving the reviewable prior.
    """
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
    if best is not None and best["edge"] <= 0.0:
        return {"param": param_name, "value": None, "skipped": "edge<=0",
                "rejected_value": best["value"], "edge": best["edge"],
                "hit_rate": best.get("hit_rate"), "n": best["n"]}
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


def _write_tuned(
    target: Path, tuned: dict[str, Any], tuned_at: dict[str, str] | None = None,
) -> None:
    from datetime import datetime, timezone

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    # ``tuned_at`` is a SEPARATE top-level map, not a key inside each league:
    # load_tuned() indexes leagues by analytic name, so a stamp stored beside
    # the analytics would be reachable as a bogus "analytic".
    tmp.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                               "leagues": tuned,
                               "tuned_at": tuned_at or {}}), encoding="utf-8")
    tmp.replace(target)


def tune_all(
    store: SportsHistoryStore,
    leagues: list[str],
    *,
    path: Path | None = None,
    budget_s: float | None = None,
) -> dict[str, Any]:
    """Walk-forward tune each league, persisting after EVERY league.

    The full 7-league grid search can exceed the tuner task's wall-clock limit
    (which terminates it). Writing all leagues only at the end therefore lost the
    WHOLE pass to a mid-run kill -- the tuned-params file went stale for days.
    Now each finished league is persisted immediately and leagues not reached
    keep their prior tuned values, so a run that is cut short still lands the
    leagues it finished instead of losing everything.

    Wave-85 -- that fix stopped the data loss but not the STARVATION. The caller
    passed a fixed league order, and DummyTune was still being killed at PT1H
    (SCHED_S_TASK_TERMINATED), so the same first few leagues were re-tuned on
    every run and the tail was never tuned even once: the live artifact held
    nfl/wnba/mlb and nothing for nba/ncaamb/ncaaf/nhl. Least-recently-tuned now
    goes first (never-tuned leagues sort first), and an explicit budget ends the
    run cleanly instead of letting the scheduler kill it. Over successive runs
    every league gets its turn.
    """
    target = path or TUNED_PATH
    tuned: dict[str, Any] = {}
    tuned_at: dict[str, str] = {}
    try:
        blob = json.loads(target.read_text(encoding="utf-8"))
        tuned = dict(blob.get("leagues") or {})
        tuned_at = dict(blob.get("tuned_at") or {})
    except Exception:  # noqa: BLE001 -- no/bad prior file => tune everything fresh
        tuned = {}
        tuned_at = {}

    # Never-tuned leagues sort first (""), then oldest stamp first. Ties keep
    # the caller's order so the sequence stays deterministic.
    order = sorted(
        range(len(leagues)),
        key=lambda i: (tuned_at.get(leagues[i], ""), i),
    )
    deadline = (time.monotonic() + float(budget_s)) if budget_s else None
    for index in order:
        lg = leagues[index]
        if deadline is not None and time.monotonic() > deadline:
            break
        v = tune_league(store, lg)
        if v:
            tuned[lg] = v
            tuned_at[lg] = datetime.now(timezone.utc).isoformat()
            _write_tuned(target, tuned, tuned_at)  # persist after each league
    return {lg: tuned[lg] for lg in leagues if lg in tuned}


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
