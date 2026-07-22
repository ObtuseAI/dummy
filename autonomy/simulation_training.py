"""Leakage-resistant, report-only simulation curriculum for Dummy.

The trainer turns the ledger into champion/challenger evidence without
granting execution authority or promoting simulated outcomes into readiness
counts.  It deliberately separates three questions:

* forecast policy: which shrinkage/edge/uncertainty policy survives later,
  unseen event clusters after fees and slippage;
* execution policy: which recorded order features are associated with
  witnessed fills and settled P&L;
* compounding: how candidate risk fractions behave under clustered bootstrap
  and adverse slippage.

All SQLite access is read-only.  The only writes are atomic JSON reports.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from autonomy.capability_matrix import build_research_capability_matrix
from autonomy.correlation import group_key
from autonomy.fees import kalshi_taker_fee_cents
from autonomy.retention import install_signal_history
from autonomy.stats import mean_ci95 as _mean_ci95


@dataclass(frozen=True)
class ForecastPolicy:
    shrinkage: float
    edge_threshold_cents: int
    max_uncertainty: float


POLICY_GRID = tuple(
    ForecastPolicy(shrinkage, edge, uncertainty)
    for shrinkage in (0.50, 0.75, 1.00, 1.25)
    for edge in (3, 5, 7, 9, 12)
    for uncertainty in (0.15, 0.25, 0.35)
)
INCUMBENT_POLICY = ForecastPolicy(1.0, 3, 0.35)
RISK_FRACTIONS = (0.0025, 0.005, 0.01, 0.02)


EXECUTION_EXPERIMENT_PROTOCOL_VERSION = "execution_policy_three_way_holdout_v1"
EXECUTION_SELECTION_MINIMUMS = {
    "known_orders": 15,
    "settled_fills": 10,
    "positive_net_pnl": True,
    "positive_mean_pnl_lower95": True,
}
_LIVENESS_REQUIRED_TABLES = frozenset({
    "signals",
    "decisions",
    "settlements",
    "outcomes",
})


def connect_readonly(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30.0,
    )
    connection.row_factory = sqlite3.Row
    install_signal_history(connection)
    connection.execute("PRAGMA query_only=ON")
    return connection


def bounded_database_liveness(connection: sqlite3.Connection) -> dict[str, Any]:
    """Prove only bounded read access and required-schema presence.

    This deliberately does *not* run ``quick_check`` or ``integrity_check``.
    Both walk a healthy database and can hold a shared lock long enough to
    starve the ten-minute SHADOW writer on the multi-gigabyte DELETE-journal
    ledger.  Structural and index consistency therefore require a separately
    scheduled offline attestation; this hourly report makes no such claim.
    """
    scalar_row = connection.execute("SELECT 1").fetchone()
    schema_row = connection.execute("PRAGMA schema_version").fetchone()
    data_row = connection.execute("PRAGMA data_version").fetchone()
    present = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_schema "
            "WHERE type='table' AND name IN (?,?,?,?)",
            tuple(sorted(_LIVENESS_REQUIRED_TABLES)),
        )
    }
    missing = sorted(_LIVENESS_REQUIRED_TABLES - present)
    if (
        scalar_row is None
        or int(scalar_row[0]) != 1
        or schema_row is None
        or data_row is None
        or missing
    ):
        raise RuntimeError(
            "bounded database liveness probe failed"
            + (f"; missing tables: {','.join(missing)}" if missing else "")
        )
    return {
        "status": "PASS",
        "method": "bounded_readonly_scalar_schema_probe",
        "schema_version": int(schema_row[0]),
        "data_version": int(data_row[0]),
        "required_tables": sorted(_LIVENESS_REQUIRED_TABLES),
        "global_integrity_scan_performed": False,
        "structural_integrity_verified": False,
    }


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * min(1.0, max(0.0, fraction))
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight



def _wilson(successes: int, total: int) -> dict[str, Any] | None:
    if total <= 0:
        return None
    z = 1.96
    rate = successes / total
    denominator = 1.0 + z * z / total
    center = (rate + z * z / (2.0 * total)) / denominator
    half = z * math.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denominator
    return {"rate": round(rate, 6), "lower": round(max(0.0, center - half), 6),
            "upper": round(min(1.0, center + half), 6), "n": total,
            "method": "wilson_95"}


def load_forecast_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return one earliest, valid, pre-settlement decision per market."""
    raw = connection.execute(
        """
        SELECT d.market_ticker,d.probability_yes,d.market_implied_yes,
               d.forecast_uncertainty,d.created_at,s.result_yes,s.settled_at
        FROM decisions d JOIN settlements s USING(market_ticker)
        WHERE d.market_implied_yes IS NOT NULL
        ORDER BY d.created_at,d.decision_id
        """
    ).fetchall()
    earliest: dict[str, dict[str, Any]] = {}
    for record in raw:
        try:
            created_at = _parse_time(record["created_at"])
            settled_at = _parse_time(record["settled_at"])
            forecast = float(record["probability_yes"])
            market = float(record["market_implied_yes"])
            uncertainty = float(record["forecast_uncertainty"])
        except (TypeError, ValueError):
            continue
        if created_at >= settled_at:
            continue
        if not (0.0 < forecast < 1.0 and 0.0 < market < 1.0):
            continue
        ticker = str(record["market_ticker"])
        earliest.setdefault(ticker, {
            "ticker": ticker,
            "cluster": group_key(ticker),
            "forecast": forecast,
            "market": market,
            "uncertainty": uncertainty,
            "result": int(record["result_yes"]),
            "created_at": created_at,
            "settled_at": settled_at,
        })
    return sorted(earliest.values(), key=lambda row: (row["created_at"], row["ticker"]))


def _adjusted_forecast(row: dict[str, Any], policy: ForecastPolicy) -> float:
    adjusted = row["market"] + policy.shrinkage * (row["forecast"] - row["market"])
    return min(0.999, max(0.001, adjusted))


def policy_trades(
    rows: Iterable[dict[str, Any]], policy: ForecastPolicy, *, slippage_cents: int = 1,
) -> list[dict[str, Any]]:
    """Apply a directional policy with taker fees and explicit slippage."""
    trades: list[dict[str, Any]] = []
    for row in rows:
        if float(row["uncertainty"]) > policy.max_uncertainty:
            continue
        adjusted = _adjusted_forecast(row, policy)
        edge = adjusted - float(row["market"])
        if abs(edge) * 100.0 < policy.edge_threshold_cents:
            continue
        buy_yes = edge > 0
        base_price = round((row["market"] if buy_yes else 1.0 - row["market"]) * 100.0)
        price = min(99, max(1, int(base_price) + max(0, int(slippage_cents))))
        won = bool(row["result"]) if buy_yes else not bool(row["result"])
        fee = kalshi_taker_fee_cents(price, 1, str(row["ticker"]))
        pnl = (100 - price if won else -price) - fee
        trades.append({
            "ticker": row["ticker"], "cluster": row["cluster"],
            "created_at": row["created_at"], "base_price_cents": int(base_price),
            "price_cents": price, "fee_cents": fee, "pnl_cents": pnl,
            "cost_cents": price + fee, "won": won,
            "adjusted_forecast": adjusted, "market": row["market"],
        })
    return trades


def summarize_trades(trades: Sequence[dict[str, Any]]) -> dict[str, Any]:
    pnl = [int(trade["pnl_cents"]) for trade in trades]
    costs = [int(trade["cost_cents"]) for trade in trades]
    running = 0
    peak = 0
    max_drawdown = 0
    for value in pnl:
        running += value
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)
    gross_profit = sum(value for value in pnl if value > 0)
    gross_loss = -sum(value for value in pnl if value < 0)
    return {
        "trades": len(trades),
        "event_clusters": len({trade["cluster"] for trade in trades}),
        "net_pnl_cents": sum(pnl),
        "entry_cost_cents": sum(costs),
        "average_pnl_cents": round(sum(pnl) / len(pnl), 6) if pnl else None,
        "mean_pnl_ci95": _mean_ci95(pnl),
        "win_rate": round(sum(value > 0 for value in pnl) / len(pnl), 6) if pnl else None,
        "roi_on_entry_cost": round(sum(pnl) / sum(costs), 6) if costs and sum(costs) else None,
        "profit_factor": round(gross_profit / gross_loss, 6) if gross_loss else None,
        "max_drawdown_cents": max_drawdown,
    }


def _temporal_folds(rows: Sequence[dict[str, Any]], requested: int = 5) -> list[list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: (row["created_at"], row["ticker"]))
    count = min(requested, len(ordered))
    if count == 0:
        return []
    folds: list[list[dict[str, Any]]] = [[] for _ in range(count)]
    for index, row in enumerate(ordered):
        folds[min(count - 1, index * count // len(ordered))].append(row)
    return folds


def _policy_rank(summary: dict[str, Any], policy: ForecastPolicy) -> tuple[Any, ...]:
    interval = summary.get("mean_pnl_ci95") or {}
    lower = interval.get("lower")
    return (
        float(lower) if lower is not None else float("-inf"),
        int(summary.get("net_pnl_cents") or 0),
        -int(summary.get("max_drawdown_cents") or 0),
        -abs(policy.shrinkage - 1.0),
        policy.edge_threshold_cents,
    )


def forecast_curriculum(rows: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Nested expanding-window policy training with event-cluster purge."""
    folds = _temporal_folds(rows)
    if len(folds) < 2:
        return ({"available": False, "reason": "need at least two temporal folds"}, [])
    history = list(folds[0])
    challenger_oos: list[dict[str, Any]] = []
    incumbent_oos: list[dict[str, Any]] = []
    fold_reports = []
    for fold_number, test_rows in enumerate(folds[1:], start=2):
        test_start = min(row["created_at"] for row in test_rows)
        training = [row for row in history if row["settled_at"] < test_start]
        training_clusters = {row["cluster"] for row in training}
        purged_test = [row for row in test_rows if row["cluster"] not in training_clusters]
        candidates = []
        for policy in POLICY_GRID:
            trades = policy_trades(training, policy, slippage_cents=1)
            summary = summarize_trades(trades)
            if summary["trades"] >= 20:
                candidates.append((policy, summary))
        if not candidates:
            history.extend(test_rows)
            continue
        policy, training_summary = max(candidates, key=lambda item: _policy_rank(item[1], item[0]))
        challenger = policy_trades(purged_test, policy, slippage_cents=1)
        incumbent = policy_trades(purged_test, INCUMBENT_POLICY, slippage_cents=1)
        challenger_oos.extend(challenger)
        incumbent_oos.extend(incumbent)
        fold_reports.append({
            "fold": fold_number,
            "selected_policy": asdict(policy),
            "training_rows": len(training),
            "training_result": training_summary,
            "test_rows": len(test_rows),
            "purged_test_rows": len(test_rows) - len(purged_test),
            "challenger_result": summarize_trades(challenger),
            "incumbent_result": summarize_trades(incumbent),
            "test_start": test_start.isoformat(),
            "test_end": max(row["created_at"] for row in test_rows).isoformat(),
            "training_latest_settlement": (
                max(row["settled_at"] for row in training).isoformat() if training else None
            ),
        })
        history.extend(test_rows)
    challenger_summary = summarize_trades(challenger_oos)
    incumbent_summary = summarize_trades(incumbent_oos)
    positive_folds = sum(
        int((fold["challenger_result"].get("net_pnl_cents") or 0) > 0)
        for fold in fold_reports
    )
    lower = (challenger_summary.get("mean_pnl_ci95") or {}).get("lower")
    eligible = bool(
        len(fold_reports) >= 3
        and positive_folds >= 2
        and lower is not None and lower > 0
        and challenger_summary["net_pnl_cents"] > incumbent_summary["net_pnl_cents"]
        and challenger_summary["max_drawdown_cents"] <= incumbent_summary["max_drawdown_cents"]
    )
    return ({
        "available": bool(fold_reports),
        "method": "nested_expanding_window_with_settlement_lag_and_event_cluster_purge",
        "training_availability_rule": "settled_at strictly before test_start",
        "execution_assumption": "market-implied taker entry plus fee and 1c slippage",
        "candidate_policies": len(POLICY_GRID),
        "folds": fold_reports,
        "positive_challenger_folds": positive_folds,
        "challenger_out_of_sample": challenger_summary,
        "incumbent_out_of_sample": incumbent_summary,
        "eligible_for_shadow_experiment": eligible,
        "auto_apply": False,
        "status": "SHADOW_EXPERIMENT_ELIGIBLE" if eligible else "HOLD",
    }, challenger_oos)


def load_order_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Collapse append-only outcomes to one truth row per shadow order."""
    rows = connection.execute(
        """
        SELECT o.id,o.decision_id,o.kind,o.fill_count,o.pnl_cents,o.detail,o.created_at,
               d.market_ticker,d.price_cents,d.ev_cents,d.forecast_uncertainty
        FROM outcomes o JOIN decisions d USING(decision_id)
        WHERE EXISTS (SELECT 1 FROM outcomes s WHERE s.decision_id=o.decision_id
                      AND s.kind='SHADOW')
        ORDER BY o.id
        """
    ).fetchall()
    grouped: dict[str, dict[str, Any]] = {}
    for record in rows:
        decision_id = str(record["decision_id"])
        item = grouped.setdefault(decision_id, {
            "decision_id": decision_id,
            "ticker": str(record["market_ticker"]),
            "cluster": group_key(str(record["market_ticker"])),
            "price_cents": int(record["price_cents"]),
            "ev_cents": float(record["ev_cents"]),
            "uncertainty": float(record["forecast_uncertainty"]),
            "submitted_at": None,
            "queue_ahead": None,
            "filled": False,
            "known": False,
            "known_at": None,
            "fill_at": None,
            "settled_at": None,
            "settled_pnl_cents": None,
        })
        try:
            detail = json.loads(record["detail"] or "{}")
        except (TypeError, json.JSONDecodeError):
            detail = {}
        kind = str(record["kind"])
        event_at = str(record["created_at"])
        if kind == "SHADOW" and item["submitted_at"] is None:
            item["submitted_at"] = str(record["created_at"])
            if detail.get("queue_snapshot_available"):
                try:
                    item["queue_ahead"] = float(detail.get("queue_ahead_contracts") or 0.0)
                except (TypeError, ValueError):
                    pass
        if kind in {"FILLED", "PARTIALLY_FILLED"} and int(record["fill_count"] or 0) > 0:
            item["filled"] = True
            item["known"] = True
            item["fill_at"] = item["fill_at"] or event_at
            item["known_at"] = item["known_at"] or event_at
        if kind in {"CANCELED", "EXPIRED", "REJECTED"}:
            item["known"] = True
            item["known_at"] = item["known_at"] or event_at
        if (kind in {"SETTLED_WIN", "SETTLED_LOSS"} and item["filled"]
                and record["pnl_cents"] is not None):
            item["settled_pnl_cents"] = int(record["pnl_cents"])
            item["settled_at"] = event_at
    return [row for row in grouped.values() if row["submitted_at"] is not None]


def _execution_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    known = [row for row in rows if row["known"]]
    filled = [row for row in known if row["filled"]]
    settled = [row for row in filled if row["settled_pnl_cents"] is not None]
    pnl = [int(row["settled_pnl_cents"]) for row in settled]
    return {
        "orders": len(rows), "known_outcomes": len(known), "fills": len(filled),
        "fill_rate_ci95": _wilson(len(filled), len(known)),
        "settled_fills": len(settled), "settled_net_pnl_cents": sum(pnl),
        "settled_mean_pnl_ci95": _mean_ci95(pnl),
    }


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _optional_time(value: Any) -> datetime | None:
    try:
        return _parse_time(value)
    except (TypeError, ValueError):
        return None


def _execution_policy_rows(
    rows: Sequence[dict[str, Any]], policy: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if float(row["uncertainty"]) <= float(policy["max_uncertainty"])
        and float(row["ev_cents"]) >= float(policy["min_ev_cents"])
        and int(row["price_cents"]) <= int(policy["max_price_cents"])
        and row.get("queue_ahead") is not None
        and float(row["queue_ahead"]) <= float(policy["max_queue_ahead"])
    ]


def _execution_candidates(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for max_uncertainty in (0.15, 0.25, 0.35):
        for min_ev in (3.0, 5.0, 8.0, 12.0):
            for max_queue in (0.0, 10.0, 25.0, 50.0):
                for max_price in (25, 50, 75, 90):
                    policy = {
                        "max_uncertainty": max_uncertainty,
                        "min_ev_cents": min_ev,
                        "max_queue_ahead": max_queue,
                        "max_price_cents": max_price,
                    }
                    summary = _execution_summary(
                        _execution_policy_rows(rows, policy)
                    )
                    if summary["known_outcomes"] < 10 or summary["fills"] < 3:
                        continue
                    interval = summary["fill_rate_ci95"] or {}
                    pnl_lower = (
                        summary["settled_mean_pnl_ci95"] or {}
                    ).get("lower")
                    candidates.append({
                        "policy": policy,
                        "summary": summary,
                        "rank": [
                            pnl_lower if pnl_lower is not None else -1e9,
                            interval.get("lower") or 0.0,
                            summary["fills"],
                        ],
                    })
    candidates.sort(key=lambda row: tuple(row["rank"]), reverse=True)
    return candidates


def _execution_partitions(
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Assign whole event clusters to 60/20/20 chronological partitions."""
    valid: list[dict[str, Any]] = []
    invalid_timestamps = 0
    for row in rows:
        submitted = _optional_time(row.get("submitted_at"))
        if submitted is None:
            invalid_timestamps += 1
            continue
        cluster = str(row.get("cluster") or group_key(str(row.get("ticker") or "")))
        item = dict(row)
        item["cluster"] = cluster
        item["_submitted_time"] = submitted
        valid.append(item)

    cluster_starts: dict[str, datetime] = {}
    for row in valid:
        cluster = str(row["cluster"])
        started = row["_submitted_time"]
        cluster_starts[cluster] = min(cluster_starts.get(cluster, started), started)
    ordered_clusters = sorted(cluster_starts, key=lambda key: (cluster_starts[key], key))
    if len(ordered_clusters) < 3:
        return {
            "available": False,
            "reason": "need at least three timestamped event clusters",
            "valid_rows": len(valid),
            "invalid_timestamp_rows": invalid_timestamps,
            "event_clusters": len(ordered_clusters),
        }

    training_count = max(1, math.floor(len(ordered_clusters) * 0.60))
    selection_count = max(1, math.floor(len(ordered_clusters) * 0.20))
    if training_count + selection_count >= len(ordered_clusters):
        selection_count = 1
        training_count = len(ordered_clusters) - 2
    training_clusters = set(ordered_clusters[:training_count])
    selection_clusters = set(
        ordered_clusters[training_count:training_count + selection_count]
    )
    holdout_clusters = set(ordered_clusters[training_count + selection_count:])

    def assigned(clusters: set[str]) -> list[dict[str, Any]]:
        return sorted(
            (row for row in valid if row["cluster"] in clusters),
            key=lambda row: (row["_submitted_time"], str(row.get("decision_id") or "")),
        )

    return {
        "available": True,
        "training": assigned(training_clusters),
        "selection": assigned(selection_clusters),
        "holdout": assigned(holdout_clusters),
        "invalid_timestamp_rows": invalid_timestamps,
    }


def _execution_rows_as_of(
    rows: Sequence[dict[str, Any]], cutoff: datetime,
) -> list[dict[str, Any]]:
    """Reconstruct only order truth received strictly before ``cutoff``."""
    snapshot: list[dict[str, Any]] = []
    for raw in rows:
        submitted = raw.get("_submitted_time") or _optional_time(raw.get("submitted_at"))
        if submitted is None or submitted >= cutoff:
            continue
        known_at = _optional_time(raw.get("known_at"))
        fill_at = _optional_time(raw.get("fill_at"))
        settled_at = _optional_time(raw.get("settled_at"))
        row = dict(raw)
        row["known"] = bool(raw.get("known") and known_at and known_at < cutoff)
        row["filled"] = bool(
            row["known"] and raw.get("filled") and fill_at and fill_at < cutoff
        )
        if not (
            row["filled"]
            and settled_at
            and settled_at < cutoff
            and raw.get("settled_pnl_cents") is not None
        ):
            row["settled_pnl_cents"] = None
        snapshot.append(row)
    return snapshot


def _execution_manifest(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    clusters = sorted({str(row.get("cluster") or "") for row in rows})
    submitted = [
        row.get("_submitted_time") or _optional_time(row.get("submitted_at"))
        for row in rows
    ]
    submitted = [value for value in submitted if value is not None]
    return {
        "orders": len(rows),
        "event_clusters": len(clusters),
        "cluster_set_sha256": _canonical_hash(clusters),
        "submitted_start": min(submitted).isoformat() if submitted else None,
        "submitted_end": max(submitted).isoformat() if submitted else None,
    }


def _execution_gate(
    summary: dict[str, Any], *, min_known: int, min_settled: int,
) -> bool:
    lower = (summary.get("settled_mean_pnl_ci95") or {}).get("lower")
    return bool(
        int(summary.get("known_outcomes") or 0) >= min_known
        and int(summary.get("settled_fills") or 0) >= min_settled
        and int(summary.get("settled_net_pnl_cents") or 0) > 0
        and lower is not None
        and float(lower) > 0.0
    )


def execution_curriculum(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Discover, validate, and close execution-filter experiments safely.

    Candidate search sees only the training partition. The selected policy
    must pass a later validation partition before the final holdout is even
    inspected. Whole event clusters are assigned to exactly one partition,
    and outcome truth is receipt-bounded at both selection boundaries.
    """
    overall = _execution_summary(rows)
    protocol = {
        "version": EXECUTION_EXPERIMENT_PROTOCOL_VERSION,
        "partition_rule": "chronological_whole_event_clusters_60_20_20",
        "training_truth_cutoff": "strictly_before_validation_start",
        "validation_truth_cutoff": "strictly_before_holdout_start",
        "candidate_grid_size": 3 * 4 * 4 * 4,
        "validation_minimums": EXECUTION_SELECTION_MINIMUMS,
        "holdout_minimums": EXECUTION_SELECTION_MINIMUMS,
        "combined_minimums": {
            "known_orders": 30,
            "settled_fills": 20,
            "positive_net_pnl": True,
            "positive_mean_pnl_lower95": True,
        },
        "holdout_access_rule": "inspect_only_after_validation_gate_passes",
    }
    protocol_hash = _canonical_hash(protocol)
    partitions = _execution_partitions(rows)
    base = {
        "method": "preregistered_three_way_event_cluster_execution_filter_grid",
        "overall": overall,
        "candidate_policies_evaluated": 3 * 4 * 4 * 4,
        "promotion_minimums": protocol["combined_minimums"],
        "auto_apply": False,
        "authority": {
            "research_retirement": True,
            "promotion": False,
            "weight_write": False,
            "execution": False,
            "capital": False,
        },
    }
    if not partitions.get("available"):
        return {
            **base,
            "qualified_candidates": 0,
            "top_candidates": [],
            "eligible_for_shadow_experiment": False,
            "status": "HOLD",
            "experiment": {
                "protocol_version": EXECUTION_EXPERIMENT_PROTOCOL_VERSION,
                "protocol_sha256": protocol_hash,
                "registration_state": "NOT_REGISTERED_INSUFFICIENT_EVIDENCE",
                "lifecycle_state": "OPEN_ACCUMULATING_TRAINING",
                "candidate_state": "CHALLENGER_ONLY_ACCUMULATING",
                "closed": False,
                "reason": partitions.get("reason"),
                "partition_diagnostics": partitions,
                "holdout_evaluated": False,
                "execution_authority": False,
                "capital_authority": False,
            },
        }

    training_raw = partitions["training"]
    selection_raw = partitions["selection"]
    holdout_raw = partitions["holdout"]
    selection_start = min(row["_submitted_time"] for row in selection_raw)
    holdout_start = min(row["_submitted_time"] for row in holdout_raw)
    training = _execution_rows_as_of(training_raw, selection_start)
    selection = _execution_rows_as_of(selection_raw, holdout_start)

    training_clusters = {str(row["cluster"]) for row in training}
    selection_clusters = {str(row["cluster"]) for row in selection}
    holdout_clusters = {str(row["cluster"]) for row in holdout_raw}
    intersections = {
        "training_validation": len(training_clusters & selection_clusters),
        "training_holdout": len(training_clusters & holdout_clusters),
        "validation_holdout": len(selection_clusters & holdout_clusters),
    }
    ordered_truth = bool(
        all(row["_submitted_time"] < selection_start for row in training)
        and all(row["_submitted_time"] < holdout_start for row in selection)
    )
    evidence_separation = {
        "verified": ordered_truth and not any(intersections.values()),
        "whole_event_cluster_assignment": True,
        "strict_receipt_bounded_outcome_truth": True,
        "cluster_intersections": intersections,
        "training": _execution_manifest(training),
        "validation": _execution_manifest(selection),
        "holdout": _execution_manifest(holdout_raw),
        "validation_start": selection_start.isoformat(),
        "holdout_start": holdout_start.isoformat(),
        "invalid_timestamp_rows_excluded": partitions["invalid_timestamp_rows"],
    }

    candidates = _execution_candidates(training)
    best = candidates[0] if candidates else None
    selected_policy = best["policy"] if best else None
    experiment_id = "exec-" + _canonical_hash({
        "protocol_sha256": protocol_hash,
        "selected_policy": selected_policy,
        "evidence_separation": evidence_separation,
    })[:20]
    lifecycle_state = "OPEN_ACCUMULATING_TRAINING"
    candidate_state = "CHALLENGER_ONLY_ACCUMULATING"
    reason = "no training policy has enough point-in-time outcomes"
    validation_summary: dict[str, Any] | None = None
    holdout_summary: dict[str, Any] | None = None
    combined_summary: dict[str, Any] | None = None
    holdout_evaluated = False
    eligible = False

    if best is not None and evidence_separation["verified"]:
        validation_rows = _execution_policy_rows(selection, selected_policy)
        validation_summary = _execution_summary(validation_rows)
        validation_has_minimums = bool(
            validation_summary["known_outcomes"]
            >= EXECUTION_SELECTION_MINIMUMS["known_orders"]
            and validation_summary["settled_fills"]
            >= EXECUTION_SELECTION_MINIMUMS["settled_fills"]
        )
        if not validation_has_minimums:
            lifecycle_state = "OPEN_ACCUMULATING_VALIDATION"
            reason = "validation partition has not reached fixed evidence minimums"
        elif not _execution_gate(
            validation_summary,
            min_known=EXECUTION_SELECTION_MINIMUMS["known_orders"],
            min_settled=EXECUTION_SELECTION_MINIMUMS["settled_fills"],
        ):
            lifecycle_state = "CLOSED_RETIRED_VALIDATION_FAILURE"
            candidate_state = "RETIRED"
            reason = "selected policy failed the preregistered validation gate"
        else:
            holdout_evaluated = True
            holdout_rows = _execution_policy_rows(holdout_raw, selected_policy)
            holdout_summary = _execution_summary(holdout_rows)
            holdout_has_minimums = bool(
                holdout_summary["known_outcomes"]
                >= EXECUTION_SELECTION_MINIMUMS["known_orders"]
                and holdout_summary["settled_fills"]
                >= EXECUTION_SELECTION_MINIMUMS["settled_fills"]
            )
            if not holdout_has_minimums:
                lifecycle_state = "OPEN_ACCUMULATING_HOLDOUT"
                reason = "untouched holdout has not reached fixed evidence minimums"
            elif not _execution_gate(
                holdout_summary,
                min_known=EXECUTION_SELECTION_MINIMUMS["known_orders"],
                min_settled=EXECUTION_SELECTION_MINIMUMS["settled_fills"],
            ):
                lifecycle_state = "CLOSED_RETIRED_HOLDOUT_FAILURE"
                candidate_state = "RETIRED"
                reason = "selected policy failed the untouched holdout gate"
            else:
                combined_rows = validation_rows + holdout_rows
                combined_summary = _execution_summary(combined_rows)
                eligible = _execution_gate(
                    combined_summary, min_known=30, min_settled=20,
                )
                if eligible:
                    lifecycle_state = "CLOSED_PASSED_SHADOW_REVIEW_ELIGIBLE"
                    candidate_state = "SHADOW_CHALLENGER_ONLY"
                    reason = (
                        "validation and untouched holdout passed; candidate remains "
                        "research-only pending a separate shadow experiment review"
                    )
                else:
                    lifecycle_state = "CLOSED_RETIRED_COMBINED_GATE_FAILURE"
                    candidate_state = "RETIRED"
                    reason = "combined validation and holdout evidence failed"

    closed = lifecycle_state.startswith("CLOSED_")
    status = "SHADOW_EXPERIMENT_ELIGIBLE" if eligible else (
        "RETIRED" if candidate_state == "RETIRED" else "HOLD"
    )
    return {
        **base,
        "qualified_candidates": len(candidates),
        "top_candidates": [
            {"policy": row["policy"], "summary": row["summary"]}
            for row in candidates[:10]
        ],
        "eligible_for_shadow_experiment": eligible,
        "status": status,
        "experiment": {
            "experiment_id": experiment_id,
            "protocol_version": EXECUTION_EXPERIMENT_PROTOCOL_VERSION,
            "protocol_sha256": protocol_hash,
            "registration_state": "PROTOCOL_PRECOMMITTED_IN_CODE",
            "lifecycle_state": lifecycle_state,
            "candidate_state": candidate_state,
            "closed": closed,
            "reason": reason,
            "selected_policy": selected_policy,
            "training_result": best["summary"] if best else None,
            "validation_result": validation_summary,
            "holdout_result": holdout_summary,
            "combined_confirmation_result": combined_summary,
            "holdout_evaluated": holdout_evaluated,
            "evidence_separation": evidence_separation,
            "multiple_testing_control": (
                "candidate grid is searched on training only; one frozen policy "
                "faces validation, then a conditionally sealed holdout"
            ),
            "automatic_production_change": False,
            "execution_authority": False,
            "capital_authority": False,
        },
    }


def _compound_path(
    trades: Sequence[dict[str, Any]], *, starting_bankroll_cents: int,
    risk_fraction: float, extra_slippage_cents: int,
) -> tuple[int, int, int]:
    bankroll = int(starting_bankroll_cents)
    peak = bankroll
    max_drawdown = 0
    positions = 0
    for trade in trades:
        price = min(99, int(trade["base_price_cents"]) + 1 + extra_slippage_cents)
        fee = kalshi_taker_fee_cents(price, 1, str(trade["ticker"]))
        per_contract_cost = price + fee
        risk_budget = math.floor(bankroll * risk_fraction)
        count = risk_budget // per_contract_cost
        if count <= 0:
            continue
        per_contract_pnl = (100 - price if trade["won"] else -price) - fee
        bankroll += count * per_contract_pnl
        bankroll = max(0, bankroll)
        positions += 1
        peak = max(peak, bankroll)
        max_drawdown = max(max_drawdown, peak - bankroll)
        if bankroll == 0:
            break
    return bankroll, max_drawdown, positions


def compounding_stress(
    trades: Sequence[dict[str, Any]], *, simulations: int = 1000,
    starting_bankroll_cents: int = 10_000, seed: int = 20260709,
) -> dict[str, Any]:
    """Cluster-bootstrap candidate risk fractions under adverse slippage."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        grouped.setdefault(str(trade["cluster"]), []).append(trade)
    clusters = list(grouped)
    if not clusters:
        return {"available": False, "reason": "no out-of-sample trades"}
    rng = random.Random(seed)
    results = []
    for risk_fraction in RISK_FRACTIONS:
        for slippage in (0, 2, 5):
            terminal: list[float] = []
            drawdowns: list[float] = []
            positions: list[float] = []
            for _ in range(max(100, int(simulations))):
                sampled = [rng.choice(clusters) for _ in range(len(clusters))]
                path = [trade for cluster in sampled for trade in grouped[cluster]]
                final, drawdown, used = _compound_path(
                    path, starting_bankroll_cents=starting_bankroll_cents,
                    risk_fraction=risk_fraction, extra_slippage_cents=slippage,
                )
                terminal.append(final)
                drawdowns.append(drawdown)
                positions.append(used)
            results.append({
                "risk_fraction": risk_fraction,
                "extra_slippage_cents": slippage,
                "terminal_bankroll_cents": {"p05": round(_percentile(terminal, 0.05) or 0, 2),
                                             "median": round(_percentile(terminal, 0.50) or 0, 2),
                                             "p95": round(_percentile(terminal, 0.95) or 0, 2)},
                "max_drawdown_cents_p95": round(_percentile(drawdowns, 0.95) or 0, 2),
                "probability_of_loss": round(sum(value < starting_bankroll_cents for value in terminal)
                                             / len(terminal), 6),
                "median_positions_used": round(_percentile(positions, 0.50) or 0, 2),
            })
    harsh = {row["risk_fraction"]: row for row in results if row["extra_slippage_cents"] == 5}
    minimum_positions = max(10, math.ceil(len(trades) * 0.50))
    safe = [fraction for fraction, row in harsh.items()
            if row["terminal_bankroll_cents"]["p05"] >= starting_bankroll_cents
            and row["max_drawdown_cents_p95"] <= starting_bankroll_cents * 0.10
            and row["probability_of_loss"] <= 0.25
            and row["median_positions_used"] >= minimum_positions]
    return {
        "available": True,
        "method": "event_cluster_bootstrap_with_dynamic_fractional_bankroll",
        "simulations_per_cell": max(100, int(simulations)),
        "starting_bankroll_cents": starting_bankroll_cents,
        "out_of_sample_trades": len(trades),
        "event_clusters": len(clusters),
        "results": results,
        "highest_stress_safe_fraction": max(safe) if safe else None,
        "minimum_median_positions": minimum_positions,
        "stress_safe_rule": (
            "5c extra slippage; p05>=start; p95 drawdown<=10%; P(loss)<=25%; "
            "median participation>=50% of OOS trades and at least 10"
        ),
        "recommended_for": "shadow sizing experiments only",
        "live_application": False,
    }


def build_improvement_queue(
    *,
    forecast: dict[str, Any],
    execution: dict[str, Any],
    compounding: dict[str, Any],
    crypto: dict[str, Any],
    trace_replay: dict[str, Any],
    evolution: dict[str, Any],
) -> dict[str, Any]:
    """Turn current weaknesses into a deterministic autonomous research queue."""
    items: list[dict[str, Any]] = []

    def add(
        priority: int,
        component: str,
        blocker: str,
        evidence: dict[str, Any],
        autonomous_action: str,
        exit_gate: str,
    ) -> None:
        items.append({
            "priority": priority,
            "component": component,
            "blocker": blocker,
            "evidence": evidence,
            "autonomous_action": autonomous_action,
            "exit_gate": exit_gate,
        })

    ensemble_brier = crypto.get("ensemble_brier")
    market_brier = crypto.get("market_brier")
    crypto_pnl = int(crypto.get("net_pnl_cents") or 0)
    crypto_fills = int(crypto.get("filled_settled_decisions") or 0)
    if (
        crypto_fills < 30
        or crypto_pnl <= 0
        or ensemble_brier is None
        or market_brier is None
        or float(ensemble_brier) >= float(market_brier)
    ):
        add(
            1,
            "crypto_operational_edge",
            "confirmed filled crypto decisions do not demonstrate positive edge",
            {
                "settled_fills": crypto_fills,
                "net_pnl_cents": crypto_pnl,
                "ensemble_brier": ensemble_brier,
                "market_brier": market_brier,
            },
            "continue hardened shadow collection and replay anchor/filter challengers",
            "at least 30 settled fills, positive P&L, and fill-conditioned Brier below market",
        )

    execution_overall = execution.get("overall") or {}
    execution_lower = (execution_overall.get("settled_mean_pnl_ci95") or {}).get("lower")
    if (
        int(execution_overall.get("settled_fills") or 0) < 20
        or execution_lower is None
        or float(execution_lower) <= 0
    ):
        add(
            2,
            "execution_selection",
            "execution filter lacks profitable settled-fill evidence",
            {
                "settled_fills": execution_overall.get("settled_fills"),
                "net_pnl_cents": execution_overall.get("settled_net_pnl_cents"),
                "mean_pnl_lower95": execution_lower,
            },
            "replay witnessed filters hourly and accumulate new transport-confirmed outcomes",
            "20 settled fills, positive net P&L, and positive mean-P&L lower95",
        )

    if not trace_replay.get("complete_for_execution_optimization"):
        add(
            3,
            "trace_completeness",
            "execution replay contains missing queue or unresolved witness state",
            {
                "orders_missing_queue_snapshot": trace_replay.get(
                    "orders_missing_queue_snapshot"
                ),
                "unresolved_orders": trace_replay.get("unresolved_orders"),
                "settlement_without_fill_anomalies": trace_replay.get(
                    "settlement_without_fill_anomalies"
                ),
            },
            "retain fail-closed trace audit and collect complete queue/fill witnesses",
            "zero impossible anomalies and a complete recent execution cohort",
        )

    forecast_oos = forecast.get("challenger_out_of_sample") or {}
    if (
        int(forecast_oos.get("trades") or 0) < 100
        or int(forecast_oos.get("event_clusters") or 0) < 20
    ):
        add(
            4,
            "forecast_generalization",
            "forecast challenger lacks diverse out-of-sample policy evidence",
            {
                "trades": forecast_oos.get("trades"),
                "event_clusters": forecast_oos.get("event_clusters"),
            },
            "continue settlement-lagged event-purged tournament replay",
            "100 out-of-sample trades across 20 event clusters and all forecast gates",
        )

    forward = evolution.get("forward_ratchet") or {}
    forward_summary = forward.get("candidate") or {}
    if not forward.get("ready_for_explicit_shadow_review"):
        add(
            5,
            "recursive_forward_ratchet",
            "active research genome has not passed genuinely later evidence",
            {
                "generation": evolution.get("generation"),
                "trades": forward_summary.get("trades"),
                "event_clusters": forward_summary.get("event_clusters"),
                "net_pnl_cents": forward_summary.get("net_pnl_cents"),
            },
            "preserve the epoch, grade new settlements, mutate, stress, and reject failures",
            "100 later trades across 10 clusters with positive lower95 P&L and advantage",
        )

    if compounding.get("highest_stress_safe_fraction") is None:
        add(
            6,
            "compounding_safety",
            "no candidate bankroll fraction survives the harsh stress gate",
            {
                "out_of_sample_trades": compounding.get("out_of_sample_trades"),
                "event_clusters": compounding.get("event_clusters"),
            },
            "rerun clustered bankroll stress as new out-of-sample evidence arrives",
            "non-null stress-safe fraction without underdeployment",
        )

    items.sort(key=lambda item: (int(item["priority"]), str(item["component"])))
    return {
        "status": "CLEAR" if not items else "ATTACKING_WEAKNESSES",
        "items": items,
        "automatic_actions_allowed": [
            "read_only_replay",
            "bounded_research_genome_mutation",
            "stress_simulation",
            "research_candidate_rotation",
            "report_generation",
        ],
        "automatic_actions_forbidden": [
            "production_code_rewrite",
            "weight_write",
            "risk_cap_write",
            "order_submission",
            "capital_allocation",
        ],
        "execution_authority": False,
    }


def run_simulation_training(
    db_path: Path | str = Path("runtime/autonomy/ledger.db"), *, simulations: int = 1000,
    previous_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc)
    connection = connect_readonly(db_path)
    try:
        database_liveness = bounded_database_liveness(connection)
        forecast_rows = load_forecast_rows(connection)
        order_rows = load_order_rows(connection)
        forecast, oos_trades = forecast_curriculum(forecast_rows)
        execution = execution_curriculum(order_rows)
        compounding = compounding_stress(oos_trades, simulations=simulations)
        from autonomy.backtest import _crypto_fill_diagnostics
        from autonomy.evolution_lab import run_evolution_lab, trace_replay_audit

        crypto = _crypto_fill_diagnostics(connection)
        trace_replay = trace_replay_audit(order_rows)
        evolution = run_evolution_lab(
            forecast_rows,
            previous_report=previous_report,
            as_of=created_at,
            bootstrap_simulations=simulations,
        )
        improvement_queue = build_improvement_queue(
            forecast=forecast,
            execution=execution,
            compounding=compounding,
            crypto=crypto,
            trace_replay=trace_replay,
            evolution=evolution,
        )
        capability_matrix = build_research_capability_matrix(
            forecast=forecast,
            execution=execution,
            evolution=evolution,
        )
        latest = {
            "signals": int(connection.execute("SELECT COUNT(*) FROM signal_history").fetchone()[0]),
            "decisions": int(connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]),
            "settlements": int(connection.execute("SELECT COUNT(*) FROM settlements").fetchone()[0]),
            "outcomes": int(connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]),
        }
    finally:
        connection.close()
    return {
        "report_name": "DUMMY_SIMULATION_TRAINING",
        "created_at": created_at.isoformat(),
        "source_database": str(Path(db_path).resolve()),
        "sqlite_access": "mode=ro; PRAGMA query_only=ON",
        "database_liveness": database_liveness,
        # Backward-compatible fields are explicit that this hourly path did
        # not perform a database-wide structural/index scan.
        "integrity_check": "NOT_RUN",
        "integrity_check_method": "offline_maintenance_only",
        "offline_integrity_attestation": {
            "status": "NOT_VERIFIED_BY_HOURLY_TRAINER",
            "full_scan_performed": False,
            "evidence_path": None,
            "required_for_structural_integrity_claim": True,
            "counts_toward_readiness": False,
        },
        "execution_authority": False,
        "weights_written": False,
        "risk_caps_written": False,
        "readiness_evidence_written": False,
        "ledger_counts": latest,
        "forecast_training": forecast,
        "execution_training": execution,
        "compounding_stress": compounding,
        "crypto_execution_truth": crypto,
        "execution_trace_replay": trace_replay,
        "evolution_lab": evolution,
        "improvement_queue": improvement_queue,
        "research_capability_matrix": capability_matrix,
        "evidence_quarantine": {
            "tier": "simulation_challenger_only",
            "counts_toward_canary": False,
            "counts_toward_scale": False,
            "may_place_orders": False,
            "promotion_path": "later unseen shadow experiment then verified settled fills",
        },
    }


def write_simulation_training_report(
    report: dict[str, Any], out_dir: Path | str = Path("artifacts/dummy/simulation_training"),
) -> Path:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"SIMULATION_TRAINING_{stamp}.json"
    temporary = path.with_suffix(".tmp")
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
    latest = directory / "LATEST.json"
    latest_tmp = latest.with_suffix(".tmp")
    latest_tmp.write_text(payload, encoding="utf-8")
    latest_tmp.replace(latest)
    return path
