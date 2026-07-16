"""Phase-A execution-policy tournament (Wave-2 workstream A2/F2).

Replays the ledger's actionable decision surface under each execution cohort
(:mod:`autonomy.execution_policy`) and reports, per cohort, cluster-robust
realized/counterfactual P&L, fill-conditioned Brier edge vs market, fill rate,
and per-fill slippage -- each measured against the incumbent maker-only control
(C0). The winner is determined by evidence only: this report *ranks* cohorts, it
does NOT switch the live execution policy (see
:data:`autonomy.execution_policy.POLICY_SWITCH_AUTHORITY`).

The tournament is an evaluation layer, not a new scheduled task. It runs inside
the existing backtest pipeline (``scripts/run_dummy_backtest.py`` ->
``autonomy.backtest.run_backtest``), so per-cohort fill-conditioned evidence
accrues automatically on every backtest cycle the live machine already
schedules -- no new schtask. It reuses the same actionable-surface
reconstruction as the adverse-selection diagnostic
(:func:`autonomy.adverse_selection.load_execution_rows`) and the same cluster
bootstrap, so the two artifacts are directly comparable.

Every interval is cluster-level (per event-cluster mean, bootstrap over
clusters) -- never a per-emission CI. The success gate per the house rules is
>= 40 witnessed (or would-have-witnessed) fill event clusters per cohort; a
cohort below the floor is reported ``insufficient_clusters`` and its point
estimates are directional only.

Cohort replay semantics over the actionable surface (one row per non-abstain,
submitted, settled decision carrying a point-in-time market prior):

  * C0 maker control -- the witnessed maker fills exactly as the incumbent
    realized them (per-contract maker sim at the recorded fill price + maker
    fee). This is the ground-truth incumbent, reproduced.
  * C1 taker -- cross the market midpoint at decision time over the *whole*
    actionable surface (no maker fill selection), pay the taker fee, keep only
    rows whose chosen-side EV net of the taker fee clears ``taker_min_ev_cents``.
  * C2 taker + walk-forward threshold -- C1 plus a minimum |model - market|
    edge chosen per fold by the walk-forward selector; only the out-of-sample
    fills count as evidence, and the per-fold picks are disclosed.
  * C3 adverse-guard maker -- the witnessed maker fills censored by the
    fast-cross guard (drop fills witnessed <= ``fast_cross_guard_seconds``) and
    the divergence cap (drop fills with |model - market| > ``divergence_cap``).
    Observed-fill censoring only: it cannot add fills a changed policy would
    attract (stated caveat).
  * C4 hybrid patient-then-take -- maker fills that arrived within the rest
    window are kept as maker fills; every other actionable row is crossed as a
    taker at the rest deadline subject to the EV floor (so C4 also captures the
    winning trades the maker never fills). For fast crypto (60s TTL) C4
    collapses to C1.

Read-only and deterministic. Places no orders, moves no capital.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.adverse_selection import _cluster_ci, load_execution_rows
from autonomy.execution_policy import (
    COHORT_CONTROL,
    ExecutionPolicy,
    default_cohorts,
)
from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents

REPORT_NAME = "EXECUTION_POLICY_TOURNAMENT"
# House-rule success gate: a cohort needs at least this many witnessed (or
# would-have-witnessed) fill event clusters before its cluster-robust intervals
# are treated as gate-eligible rather than merely directional.
MIN_FILL_CLUSTERS = 40
# Walk-forward fold count for the C2 threshold selection.
WALK_FORWARD_FOLDS = 4


def _clamp_price(price: float) -> int:
    return max(1, min(99, int(round(price))))


def _side_prices(row: dict[str, Any]) -> tuple[int, int, float, float]:
    """Chosen-side mid price, model fair price (cents) and win flag inputs.

    Returns ``(mid_price_cents, model_fair_cents, edge_cents, won_float)`` for
    the side the model prefers (the larger |model - market| direction), framed
    so a taker crossing the midpoint pays ``mid_price_cents``.
    """
    forecast = row["forecast"]
    market = row["market"]
    side = row["side"]
    if side == "yes":
        mid = _clamp_price(market * 100.0)
        fair = forecast * 100.0
        won = 1.0 if row["result"] else 0.0
    else:
        mid = _clamp_price((1.0 - market) * 100.0)
        fair = (1.0 - forecast) * 100.0
        won = 0.0 if row["result"] else 1.0
    edge_cents = abs(forecast - market) * 100.0
    return mid, fair, edge_cents, won


def _maker_trade(row: dict[str, Any]) -> dict[str, Any]:
    """Per-contract maker fill at the recorded fill price + maker fee."""
    price = _clamp_price(
        row["fill_price_cents"] if row["fill_price_cents"] is not None else row["price_cents"]
    )
    won = bool(row["result"]) if row["side"] == "yes" else (not bool(row["result"]))
    fee = kalshi_maker_fee_cents(price, 1, row["ticker"])
    return _trade_record(row, price, fee, won)


def _taker_trade(row: dict[str, Any]) -> dict[str, Any]:
    """Per-contract taker fill crossing the market midpoint + taker fee."""
    mid, _fair, _edge, _won = _side_prices(row)
    won = bool(row["result"]) if row["side"] == "yes" else (not bool(row["result"]))
    fee = kalshi_taker_fee_cents(mid, 1, row["ticker"])
    return _trade_record(row, mid, fee, won)


def _trade_record(
    row: dict[str, Any], price: int, fee: int, won: bool,
) -> dict[str, Any]:
    return {
        "cluster": row["cluster"],
        "ticker": row["ticker"],
        "price_cents": price,
        "fee_cents": fee,
        "pnl_cents": (100 - price if won else -price) - fee,
        "cost_cents": price + fee,
        "won": bool(won),
        "forecast": row["forecast"],
        "market": row["market"],
        "result": row["result"],
        "slippage_cents": _model_slippage(row, price),
    }


def _model_slippage(row: dict[str, Any], fill_price: int) -> float:
    """signal_price - fill_price for the traded side (positive = filled below fair)."""
    if row["side"] == "yes":
        signal_price = row["forecast"] * 100.0
    else:
        signal_price = (1.0 - row["forecast"]) * 100.0
    return signal_price - float(fill_price)


def _taker_ev_net_cents(row: dict[str, Any]) -> float:
    """Model EV per contract for crossing the midpoint, net of the taker fee."""
    mid, fair, _edge, _won = _side_prices(row)
    fee = kalshi_taker_fee_cents(mid, 1, row["ticker"])
    return fair - float(mid) - float(fee)


# --------------------------------------------------------------------------- #
# Per-cohort fill construction
# --------------------------------------------------------------------------- #


def _passes_taker_gate(row: dict[str, Any], policy: ExecutionPolicy) -> bool:
    """EV-net floor and (C2) minimum edge gate for a taker cross."""
    _mid, _fair, edge_cents, _won = _side_prices(row)
    if edge_cents < policy.taker_min_edge_cents:
        return False
    if policy.taker_min_ev_cents is not None:
        if _taker_ev_net_cents(row) < policy.taker_min_ev_cents:
            return False
    return True


def _control_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """C0: the witnessed maker fills, per-contract, as the incumbent realized."""
    return [_maker_trade(r) for r in rows if r["filled"]]


def _taker_trades(
    rows: list[dict[str, Any]], policy: ExecutionPolicy,
) -> list[dict[str, Any]]:
    """C1/C2: taker cross over the full actionable surface, EV/edge gated."""
    return [_taker_trade(r) for r in rows if _passes_taker_gate(r, policy)]


def _adverse_guard_trades(
    rows: list[dict[str, Any]], policy: ExecutionPolicy,
) -> list[dict[str, Any]]:
    """C3: witnessed maker fills censored by the fast-cross and divergence guards."""
    kept: list[dict[str, Any]] = []
    for r in rows:
        if not r["filled"]:
            continue
        if (
            policy.fast_cross_guard_seconds is not None
            and r["delay_seconds"] is not None
            and r["delay_seconds"] <= policy.fast_cross_guard_seconds
        ):
            continue
        if policy.divergence_cap_cents is not None:
            edge_cents = abs(r["forecast"] - r["market"]) * 100.0
            if edge_cents > policy.divergence_cap_cents:
                continue
        kept.append(_maker_trade(r))
    return kept


def _hybrid_trades(
    rows: list[dict[str, Any]], policy: ExecutionPolicy,
) -> list[dict[str, Any]]:
    """C4: maker fills inside the rest window; taker cross on everything else."""
    rest = policy.rest_seconds_before_take
    trades: list[dict[str, Any]] = []
    for r in rows:
        filled_in_window = (
            r["filled"]
            and rest is not None
            and r["delay_seconds"] is not None
            and r["delay_seconds"] <= rest
        )
        if filled_in_window:
            trades.append(_maker_trade(r))
        elif _passes_taker_gate(r, policy):
            # Unfilled, or filled only after the rest deadline: C4 would have
            # crossed at the deadline instead of waiting.
            trades.append(_taker_trade(r))
    return trades


def cohort_trades(
    rows: list[dict[str, Any]], policy: ExecutionPolicy,
) -> list[dict[str, Any]]:
    """Per-contract trades a cohort would book over the actionable surface."""
    if policy.cohort == COHORT_CONTROL:
        return _control_trades(rows)
    if policy.mode == "taker":
        return _taker_trades(rows, policy)
    if policy.cohort.startswith("C3"):
        return _adverse_guard_trades(rows, policy)
    if policy.mode == "hybrid":
        return _hybrid_trades(rows, policy)
    return _control_trades(rows)


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def _brier(p: float, outcome: int) -> float:
    return (p - outcome) ** 2


def _cohort_summary(
    trades: list[dict[str, Any]],
    *,
    actionable: int,
    seed: str,
) -> dict[str, Any]:
    if not trades:
        return {
            "fills": 0,
            "fill_event_clusters": 0,
            "fill_rate": 0.0 if actionable else None,
            "net_pnl_cents": 0,
            "mean_pnl_cents": None,
            "win_rate": None,
            "cluster_robust_mean_pnl_ci95": None,
            "fill_conditioned_forecast_brier": None,
            "fill_conditioned_market_brier": None,
            "fill_conditioned_brier_edge_vs_market": None,
            "cluster_robust_brier_edge_ci95": None,
            "mean_model_slippage_cents": None,
        }
    pnl_by_cluster: dict[str, list[float]] = {}
    edge_by_cluster: dict[str, list[float]] = {}
    net = 0
    wins = 0
    forecast_brier = 0.0
    market_brier = 0.0
    slippage = 0.0
    for t in trades:
        pnl_by_cluster.setdefault(t["cluster"], []).append(float(t["pnl_cents"]))
        fb = _brier(t["forecast"], t["result"])
        mb = _brier(t["market"], t["result"])
        edge_by_cluster.setdefault(t["cluster"], []).append(mb - fb)
        forecast_brier += fb
        market_brier += mb
        net += int(t["pnl_cents"])
        wins += 1 if t["won"] else 0
        slippage += float(t["slippage_cents"])
    n = len(trades)
    fb_mean = forecast_brier / n
    mb_mean = market_brier / n
    return {
        "fills": n,
        "fill_event_clusters": len(pnl_by_cluster),
        "fill_rate": round(n / actionable, 6) if actionable else None,
        "net_pnl_cents": net,
        "mean_pnl_cents": round(net / n, 4),
        "win_rate": round(wins / n, 6),
        "cluster_robust_mean_pnl_ci95": _cluster_ci(pnl_by_cluster, seed=f"{seed}-pnl"),
        "fill_conditioned_forecast_brier": round(fb_mean, 6),
        "fill_conditioned_market_brier": round(mb_mean, 6),
        "fill_conditioned_brier_edge_vs_market": round(mb_mean - fb_mean, 6),
        "cluster_robust_brier_edge_ci95": _cluster_ci(edge_by_cluster, seed=f"{seed}-brier"),
        "mean_model_slippage_cents": round(slippage / n, 4),
    }


def _paired_pnl_difference_vs_control(
    cohort_trades_list: list[dict[str, Any]],
    control_trades_list: list[dict[str, Any]],
    *,
    seed: str,
) -> dict[str, Any] | None:
    """Cluster-robust CI of (cohort - control) total P&L per event cluster.

    Paired at the cluster grain over the union of clusters either policy trades:
    a cluster where a policy holds no position contributes 0 P&L there, which is
    the honest comparison (the policy earned nothing on that event).
    """
    def per_cluster_total(trades: list[dict[str, Any]]) -> dict[str, float]:
        totals: dict[str, float] = {}
        for t in trades:
            totals[t["cluster"]] = totals.get(t["cluster"], 0.0) + float(t["pnl_cents"])
        return totals

    cohort_totals = per_cluster_total(cohort_trades_list)
    control_totals = per_cluster_total(control_trades_list)
    clusters = set(cohort_totals) | set(control_totals)
    if not clusters:
        return None
    diff_by_cluster = {
        cluster: [cohort_totals.get(cluster, 0.0) - control_totals.get(cluster, 0.0)]
        for cluster in clusters
    }
    return _cluster_ci(diff_by_cluster, seed=seed)


# --------------------------------------------------------------------------- #
# C2 walk-forward threshold selection
# --------------------------------------------------------------------------- #


def _temporal_folds(
    rows: list[dict[str, Any]], folds: int = WALK_FORWARD_FOLDS,
) -> list[list[dict[str, Any]]]:
    """Strictly chronological folds over the actionable surface (by fill order)."""
    ordered = sorted(rows, key=lambda r: (r.get("submitted_at") or "", r["ticker"]))
    count = min(folds, len(ordered))
    if count == 0:
        return []
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(count)]
    for index, row in enumerate(ordered):
        buckets[min(count - 1, index * count // len(ordered))].append(row)
    return buckets


def _select_edge_threshold(training: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    """Pick the taker edge threshold maximizing training net taker P&L.

    Mirrors the backtest walk-forward selector: sweep 0-10c, prefer >=10 trades,
    tie-break on net P&L then the larger (more selective) threshold.
    """
    candidates: list[tuple[int, dict[str, Any]]] = []
    for threshold in range(0, 11):
        base = ExecutionPolicy.taker_walk_forward().with_edge_threshold(threshold)
        trades = _taker_trades(training, base)
        net = sum(int(t["pnl_cents"]) for t in trades)
        candidates.append((threshold, {"threshold_cents": threshold,
                                       "trades": len(trades), "net_pnl_cents": net}))
    eligible = [c for c in candidates if c[1]["trades"] >= 10]
    pool = eligible or [c for c in candidates if c[1]["trades"] > 0] or candidates
    selected = max(pool, key=lambda c: (c[1]["net_pnl_cents"], c[0]))
    return selected[0], selected[1]


def _walk_forward_c2(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold-based C2 threshold selection; out-of-sample fills are the evidence."""
    folds = _temporal_folds(rows)
    if len(folds) < 2:
        return {
            "folds": 0,
            "note": "need at least two chronological folds for out-of-sample evidence",
            "out_of_sample_trades": [],
            "fold_selections": [],
        }
    history = list(folds[0])
    fold_selections: list[dict[str, Any]] = []
    out_of_sample: list[dict[str, Any]] = []
    for fold_number, test_rows in enumerate(folds[1:], start=2):
        threshold, training_summary = _select_edge_threshold(history)
        policy = ExecutionPolicy.taker_walk_forward().with_edge_threshold(threshold)
        test_trades = _taker_trades(test_rows, policy)
        out_of_sample.extend(test_trades)
        fold_selections.append({
            "fold": fold_number,
            "train_rows": len(history),
            "test_rows": len(test_rows),
            "selected_edge_threshold_cents": threshold,
            "training_result": training_summary,
            "out_of_sample_fills": len(test_trades),
            "out_of_sample_net_pnl_cents": sum(int(t["pnl_cents"]) for t in test_trades),
        })
        history.extend(test_rows)
    return {
        "method": "expanding_window_chronological_fold_taker_edge_threshold",
        "selection_objective": "maximize training net taker PnL; >=10 trades when possible",
        "folds": len(fold_selections),
        "fold_selections": fold_selections,
        "out_of_sample_trades": out_of_sample,
        "selected_thresholds_by_fold": [
            f["selected_edge_threshold_cents"] for f in fold_selections
        ],
    }


# --------------------------------------------------------------------------- #
# Top-level report
# --------------------------------------------------------------------------- #


def tournament_report(
    conn: sqlite3.Connection,
    cohorts: tuple[ExecutionPolicy, ...] | None = None,
) -> dict[str, Any]:
    """Score C0-C4 over the ledger's actionable surface (read-only)."""
    policies = cohorts or default_cohorts()
    rows = load_execution_rows(conn)
    generated_at = datetime.now(timezone.utc).isoformat()
    if not rows:
        return {
            "report_name": REPORT_NAME,
            "actionable_settled_decisions": 0,
            "note": "no submitted, settled, non-abstain decisions with a market prior",
            "min_fill_clusters_gate": MIN_FILL_CLUSTERS,
            "cohorts": [],
            "ranking": [],
            "policy_switch_authority": _policy_switch_note(),
            "generated_at": generated_at,
        }

    actionable = len(rows)
    actionable_clusters = len({r["cluster"] for r in rows})
    control_policy = next(
        (p for p in policies if p.cohort == COHORT_CONTROL),
        ExecutionPolicy.maker_only_control(),
    )
    control_trades = _control_trades(rows)

    walk_forward = _walk_forward_c2(rows)
    cohorts_out: list[dict[str, Any]] = []
    for policy in policies:
        if policy.cohort == "C2":
            trades = list(walk_forward.get("out_of_sample_trades") or [])
            evidence_basis = "walk_forward_out_of_sample"
        else:
            trades = cohort_trades(rows, policy)
            evidence_basis = "full_actionable_surface_replay"
        summary = _cohort_summary(trades, actionable=actionable, seed=policy.cohort)
        vs_control = (
            None
            if policy.cohort == COHORT_CONTROL
            else _paired_pnl_difference_vs_control(
                trades, control_trades, seed=f"{policy.cohort}-vs-c0",
            )
        )
        gate_ok = int(summary["fill_event_clusters"]) >= MIN_FILL_CLUSTERS
        cohorts_out.append({
            "policy": policy.to_dict(),
            "evidence_basis": evidence_basis,
            **summary,
            "gate_met": gate_ok,
            "gate_status": "eligible" if gate_ok else "insufficient_clusters",
            "pnl_vs_control_cents_ci95": vs_control,
        })

    ranking = _rank_cohorts(cohorts_out)
    return {
        "report_name": REPORT_NAME,
        "selection": "actionable_submitted_settled_decisions",
        "actionable_settled_decisions": actionable,
        "actionable_event_clusters": actionable_clusters,
        "control_cohort": COHORT_CONTROL,
        "min_fill_clusters_gate": MIN_FILL_CLUSTERS,
        "cohorts": cohorts_out,
        "ranking": ranking,
        "c2_walk_forward_threshold_selection": {
            key: value
            for key, value in walk_forward.items()
            if key != "out_of_sample_trades"
        },
        "control_policy": control_policy.to_dict(),
        "policy_switch_authority": _policy_switch_note(),
        "headline": _headline(cohorts_out, ranking),
        "caveats": [
            "All intervals are cluster-level; point estimates below the "
            f"{MIN_FILL_CLUSTERS}-cluster gate are directional only.",
            "C1/C2/C4 taker fills cross the recorded market midpoint and pay the "
            "taker fee -- a conservative counterfactual that never assumes a "
            "resting maker quote would have filled.",
            "C3 censors observed maker fills only; it cannot model fills a "
            "changed maker policy would newly attract or repel.",
            "Evidence only: this report ranks cohorts and does NOT switch the "
            "live execution policy.",
        ],
        "generated_at": generated_at,
    }


def _policy_switch_note() -> dict[str, Any]:
    from autonomy.execution_policy import POLICY_SWITCH_AUTHORITY

    return {
        "authority": POLICY_SWITCH_AUTHORITY,
        "auto_switch": False,
        "note": (
            "A tournament winner is evidence, not an action. Adopting a cohort "
            "as the live execution policy flows through the auto-promotion "
            "ladder (autonomy/auto_promotion.py) or an explicit, reviewed "
            "operator config change -- never automatically from this report."
        ),
    }


def _rank_cohorts(cohorts_out: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank by mean per-contract P&L; gate-eligible cohorts sort ahead."""
    def key(item: dict[str, Any]) -> tuple[Any, ...]:
        mean = item.get("mean_pnl_cents")
        return (
            0 if item.get("gate_met") else 1,
            -(mean if mean is not None else float("-inf")),
            item["policy"]["cohort"],
        )

    ranked = sorted(cohorts_out, key=key)
    return [
        {
            "rank": index,
            "cohort": item["policy"]["cohort"],
            "label": item["policy"]["label"],
            "mean_pnl_cents": item.get("mean_pnl_cents"),
            "net_pnl_cents": item.get("net_pnl_cents"),
            "fill_event_clusters": item.get("fill_event_clusters"),
            "gate_met": item.get("gate_met"),
        }
        for index, item in enumerate(ranked, start=1)
    ]


def _headline(
    cohorts_out: list[dict[str, Any]], ranking: list[dict[str, Any]],
) -> dict[str, Any]:
    by_cohort = {c["policy"]["cohort"]: c for c in cohorts_out}
    leader = ranking[0] if ranking else {}
    any_gate = any(c.get("gate_met") for c in cohorts_out)
    return {
        "leading_cohort": leader.get("cohort"),
        "leading_cohort_gate_met": leader.get("gate_met"),
        "any_cohort_gate_eligible": any_gate,
        "control_mean_pnl_cents": (
            by_cohort.get(COHORT_CONTROL, {}).get("mean_pnl_cents")
        ),
        "control_fill_event_clusters": (
            by_cohort.get(COHORT_CONTROL, {}).get("fill_event_clusters")
        ),
        "evidence_sufficient_for_promotion_review": any_gate,
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    """Atomic JSON write, matching the adverse-selection artifact pattern."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def summarize_tournament(report: dict[str, Any]) -> dict[str, Any]:
    """Compact view for the backtest summary / dashboard status payload."""
    return {
        "report_name": report.get("report_name"),
        "actionable_settled_decisions": report.get("actionable_settled_decisions"),
        "min_fill_clusters_gate": report.get("min_fill_clusters_gate"),
        "ranking": report.get("ranking", []),
        "headline": report.get("headline", {}),
        "c2_selected_thresholds_by_fold": (
            report.get("c2_walk_forward_threshold_selection", {})
            .get("selected_thresholds_by_fold", [])
        ),
        "policy_switch_authority": report.get("policy_switch_authority", {}),
        "generated_at": report.get("generated_at"),
    }


__all__ = [
    "MIN_FILL_CLUSTERS",
    "REPORT_NAME",
    "cohort_trades",
    "summarize_tournament",
    "tournament_report",
    "write_report",
]
