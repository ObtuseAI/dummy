"""Point-in-time, settlement-backed evaluation of shadow exit policies.

Exit advisories are observations, not orders. This module joins only v2
advisories received after a witnessed fill and before settlement, chooses the
first trigger for each pre-registered policy, and compares a quoted-bid
counterfactual with the verified hold-to-settlement P&L. Displayed bids are
stress-tested for slippage; they are never relabeled as witnessed fills.
"""
from __future__ import annotations

import json
import random
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from autonomy.correlation import group_key
from autonomy.fees import kalshi_taker_fee_cents
from autonomy.retention import install_signal_history


EVALUATOR_VERSION = "exit_policy_evaluator_v1"
POLICIES = (
    "model_value_v1",
    "adverse_model_combo_v1",
    "stop_loss_10c_v1",
    "take_profit_10c_v1",
    "time_exit_6h_v1",
)
SLIPPAGE_STRESS_CENTS = (0, 1, 3, 5)
MIN_FORWARD_DECISIONS = 50
MIN_EVENT_CLUSTERS = 20


@dataclass(frozen=True)
class ExitEvidenceSnapshot:
    decision_id: str
    market_ticker: str
    event_group: str
    snapshot_at: str
    side: str
    filled_count: int
    quoted_exit_bid_cents: int
    entry_cost_cents: int
    entry_cost_source: str
    hold_pnl_cents: int
    action: str
    mark_change_cents: int
    time_to_close_hours: float | None
    exit_advantage_cents: float | None
    exit_depth_verified: bool


def _utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_exit_evidence(
    connection: sqlite3.Connection,
) -> tuple[list[ExitEvidenceSnapshot], dict[str, int]]:
    """Load strict forward evidence and return transparent exclusion counts."""
    exclusions: Counter[str] = Counter()
    decisions = {
        str(row[0]): {
            "ticker": str(row[1]),
            "side": str(row[2]).lower(),
            "created_at": str(row[3]),
        }
        for row in connection.execute(
            "SELECT decision_id,market_ticker,side,created_at FROM decisions"
        )
    }
    settlements = {
        str(row[0]): {"result_yes": bool(row[1]), "settled_at": str(row[2])}
        for row in connection.execute(
            "SELECT market_ticker,result_yes,settled_at FROM settlements"
        )
    }

    fill_rows: dict[str, dict[str, Any]] = {}
    settled_rows: dict[str, dict[str, Any]] = {}
    for row in connection.execute(
        "SELECT id,decision_id,kind,fill_count,fill_price_cents,pnl_cents,detail,created_at "
        "FROM outcomes ORDER BY id"
    ):
        outcome_id, decision_id, kind, fill_count, fill_price, pnl, detail, created_at = row
        decision_id = str(decision_id)
        count = int(fill_count or 0)
        if (
            str(kind) in {"SHADOW", "PARTIALLY_FILLED", "FILLED"}
            and count > 0 and fill_price is not None
        ):
            current = fill_rows.get(decision_id)
            rank = (count, int(outcome_id))
            if current is None or rank > current["rank"]:
                fill_rows[decision_id] = {
                    "rank": rank,
                    "count": count,
                    "price": int(fill_price),
                    "detail": _json_object(detail),
                    "created_at": str(created_at),
                }
        if str(kind) in {"SETTLED_WIN", "SETTLED_LOSS"} and pnl is not None:
            settled_rows[decision_id] = {
                "id": int(outcome_id),
                "count": count,
                "pnl": int(pnl),
                "detail": _json_object(detail),
                "created_at": str(created_at),
            }

    evidence: list[ExitEvidenceSnapshot] = []
    rows = connection.execute(
        "SELECT id,market_ticker,features,created_at,ingested_at "
        "FROM signal_history "
        "WHERE source='exit_advisor_shadow' AND mode='live' ORDER BY id"
    )
    for _signal_id, ticker, raw_features, created_at, ingested_at in rows:
        features = _json_object(raw_features)
        if features.get("evidence_version") != "exit_advisor_v2":
            exclusions["legacy_or_unknown_advisor_version"] += 1
            continue
        if features.get("observational_only") is not True:
            exclusions["not_observational"] += 1
            continue
        if features.get("policy_evidence_only") is not True or features.get(
            "probability_authority"
        ) is not False:
            exclusions["forecast_authority_not_quarantined"] += 1
            continue
        decision_id = str(features.get("decision_id") or "")
        decision = decisions.get(decision_id)
        fill = fill_rows.get(decision_id)
        settled = settled_rows.get(decision_id)
        settlement = settlements.get(str(ticker))
        if decision is None or fill is None or settled is None or settlement is None:
            exclusions["incomplete_lifecycle"] += 1
            continue
        if decision["ticker"] != str(ticker):
            exclusions["decision_ticker_mismatch"] += 1
            continue
        if features.get("entry_order_active") is not False:
            exclusions["entry_order_active_or_unknown"] += 1
            continue
        snapshot_time = _utc(created_at)
        receipt_time = _utc(ingested_at)
        quote_time = _utc(features.get("exit_quote_observed_at"))
        fill_time = _utc(fill["created_at"])
        settlement_time = _utc(settlement["settled_at"])
        if None in {snapshot_time, receipt_time, quote_time, fill_time, settlement_time}:
            exclusions["invalid_timestamp"] += 1
            continue
        assert snapshot_time is not None
        assert receipt_time is not None
        assert quote_time is not None
        assert fill_time is not None
        assert settlement_time is not None
        if not (fill_time <= quote_time <= snapshot_time <= receipt_time < settlement_time):
            exclusions["point_in_time_ordering_violation"] += 1
            continue
        if features.get("exit_quote_fresh") is not True:
            exclusions["stale_or_unverified_quote"] += 1
            continue
        quote_age = _number(features.get("exit_quote_age_seconds"))
        if quote_age is None or quote_age < 0 or quote_age > 120.0:
            exclusions["stale_or_unverified_quote"] += 1
            continue
        filled_count = _integer(features.get("filled_count"))
        if (
            filled_count is None
            or filled_count <= 0
            or filled_count != int(fill["count"])
            or filled_count != int(settled["count"])
        ):
            exclusions["fill_quantity_mismatch"] += 1
            continue
        quoted_bid = _integer(features.get("quoted_exit_bid_cents"))
        if quoted_bid is None or not 1 <= quoted_bid <= 99:
            exclusions["missing_quoted_bid"] += 1
            continue
        entry_cost = _integer(features.get("entry_cost_cents"))
        entry_cost_source = str(features.get("entry_cost_source") or "")
        if entry_cost is None or entry_cost < 0 or entry_cost_source not in {
            "witnessed_fill_cost",
            "witnessed_fee_plus_fill_price",
        }:
            exclusions["entry_cost_not_witnessed"] += 1
            continue
        side = str(features.get("position_side") or decision["side"]).lower()
        if side not in {"yes", "no"} or side != decision["side"]:
            exclusions["side_mismatch"] += 1
            continue
        mark_change = _integer(features.get("mark_change_cents"))
        if mark_change is None:
            exclusions["missing_mark"] += 1
            continue
        evidence.append(
            ExitEvidenceSnapshot(
                decision_id=decision_id,
                market_ticker=str(ticker),
                event_group=group_key(str(ticker)),
                snapshot_at=snapshot_time.isoformat(),
                side=side,
                filled_count=filled_count,
                quoted_exit_bid_cents=quoted_bid,
                entry_cost_cents=entry_cost,
                entry_cost_source=entry_cost_source,
                hold_pnl_cents=int(settled["pnl"]),
                action=str(features.get("action") or "HOLD").upper(),
                mark_change_cents=mark_change,
                time_to_close_hours=_number(features.get("time_to_close_hours")),
                exit_advantage_cents=_number(features.get("exit_advantage_cents")),
                exit_depth_verified=features.get("exit_depth_verified") is True,
            )
        )
    evidence.sort(key=lambda row: (row.snapshot_at, row.decision_id))
    return evidence, dict(sorted(exclusions.items()))


def _policy_triggers(policy: str, row: ExitEvidenceSnapshot) -> bool:
    if policy == "model_value_v1":
        return row.action == "EXIT"
    if policy == "adverse_model_combo_v1":
        return row.action == "EXIT" and row.mark_change_cents <= -3
    if policy == "stop_loss_10c_v1":
        return row.mark_change_cents <= -10
    if policy == "take_profit_10c_v1":
        return row.mark_change_cents >= 10
    if policy == "time_exit_6h_v1":
        return row.time_to_close_hours is not None and 0 <= row.time_to_close_hours <= 6
    raise ValueError(f"unknown exit policy: {policy}")


def _first_trigger(
    snapshots: Iterable[ExitEvidenceSnapshot], policy: str,
) -> list[ExitEvidenceSnapshot]:
    chosen: dict[str, ExitEvidenceSnapshot] = {}
    for row in sorted(snapshots, key=lambda item: (item.snapshot_at, item.decision_id)):
        if row.decision_id not in chosen and _policy_triggers(policy, row):
            chosen[row.decision_id] = row
    return list(chosen.values())


def _exit_pnl(row: ExitEvidenceSnapshot, slippage_cents: int) -> int:
    exit_price = max(1, row.quoted_exit_bid_cents - int(slippage_cents))
    fee = kalshi_taker_fee_cents(
        exit_price, row.filled_count, row.market_ticker
    )
    return exit_price * row.filled_count - fee - row.entry_cost_cents


def _cluster_bootstrap_ci(
    rows: list[ExitEvidenceSnapshot],
    *,
    slippage_cents: int,
    replicates: int = 2000,
    seed: int = 20260721,
) -> list[float] | None:
    grouped: dict[str, list[ExitEvidenceSnapshot]] = {}
    for row in rows:
        grouped.setdefault(row.event_group, []).append(row)
    groups = sorted(grouped)
    if len(groups) < 2:
        return None
    rng = random.Random(seed + slippage_cents)
    samples: list[float] = []
    for _ in range(replicates):
        sampled = [grouped[rng.choice(groups)] for _ in groups]
        flat = [row for group in sampled for row in group]
        contracts = sum(row.filled_count for row in flat)
        if contracts:
            delta = sum(
                _exit_pnl(row, slippage_cents) - row.hold_pnl_cents
                for row in flat
            )
            samples.append(delta / contracts)
    if not samples:
        return None
    samples.sort()
    low = samples[int(0.025 * (len(samples) - 1))]
    high = samples[int(0.975 * (len(samples) - 1))]
    return [round(low, 4), round(high, 4)]


def _scenario(rows: list[ExitEvidenceSnapshot], slippage_cents: int) -> dict[str, Any]:
    contracts = sum(row.filled_count for row in rows)
    exit_pnls = [_exit_pnl(row, slippage_cents) for row in rows]
    deltas = [pnl - row.hold_pnl_cents for pnl, row in zip(exit_pnls, rows)]
    return {
        "slippage_cents_per_contract": slippage_cents,
        "quoted_bid_is_fill": False,
        "decisions": len(rows),
        "contracts": contracts,
        "early_exit_pnl_cents": sum(exit_pnls),
        "hold_to_settlement_pnl_cents": sum(row.hold_pnl_cents for row in rows),
        "incremental_pnl_cents": sum(deltas),
        "incremental_pnl_per_contract_cents": (
            round(sum(deltas) / contracts, 4) if contracts else None
        ),
        "exit_beats_hold_rate": (
            round(sum(delta > 0 for delta in deltas) / len(deltas), 4)
            if deltas else None
        ),
        "event_cluster_bootstrap_95pct_ci_per_contract_cents": (
            _cluster_bootstrap_ci(rows, slippage_cents=slippage_cents)
        ),
    }


def evaluate_exit_policies(
    snapshots: Iterable[ExitEvidenceSnapshot],
    *,
    exclusions: dict[str, int] | None = None,
) -> dict[str, Any]:
    rows = list(snapshots)
    decision_count = len({row.decision_id for row in rows})
    policies: dict[str, Any] = {}
    for policy in POLICIES:
        selected = _first_trigger(rows, policy)
        scenarios = {
            str(slippage): _scenario(selected, slippage)
            for slippage in SLIPPAGE_STRESS_CENTS
        }
        stressed = scenarios["3"]
        ci = stressed["event_cluster_bootstrap_95pct_ci_per_contract_cents"]
        clusters = len({row.event_group for row in selected})
        depth_rate = (
            sum(row.exit_depth_verified for row in selected) / len(selected)
            if selected else 0.0
        )
        forward_gate = (
            len(selected) >= MIN_FORWARD_DECISIONS
            and clusters >= MIN_EVENT_CLUSTERS
            and ci is not None
            and ci[0] > 0
            and depth_rate >= 0.9
        )
        policies[policy] = {
            "selection": "first_point_in_time_trigger_per_decision",
            "triggered_decisions": len(selected),
            "event_clusters": clusters,
            "depth_verified_fraction": round(depth_rate, 4),
            "scenarios": scenarios,
            "passes_forward_research_gate": forward_gate,
            "execution_authority": False,
        }
    passing = [name for name, row in policies.items() if row["passes_forward_research_gate"]]
    return {
        "version": EVALUATOR_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "RESEARCH_ONLY" if decision_count else "NO_ELIGIBLE_FORWARD_EVIDENCE",
        "execution_authority": False,
        "live_sell_authorized": False,
        "capital_authority_changed": False,
        "eligible_snapshots": len(rows),
        "eligible_decisions": decision_count,
        "eligible_event_clusters": len({row.event_group for row in rows}),
        "exclusions": dict(sorted((exclusions or {}).items())),
        "pre_registered_policies": list(POLICIES),
        "slippage_stress_cents": list(SLIPPAGE_STRESS_CENTS),
        "policies": policies,
        "passing_research_candidates": passing,
        "methodology": {
            "evidence_lane": "live_receipt_bounded_exit_advisor_v2",
            "benchmark": "verified_hold_to_settlement_pnl",
            "counterfactual": "displayed_bid_minus_taker_fee_and_slippage",
            "displayed_bid_is_witnessed_fill": False,
            "selection": "first_trigger_only_no_per_decision_hindsight",
            "dependence": "event_cluster_bootstrap",
            "entry_cost": "witnessed_only",
        },
        "blockers_before_any_sell_path": [
            "forward research gate must pass under 3c slippage",
            "displayed depth must cover at least 90% of selected exits",
            "sell submission and partial-fill reconciliation require separate proof",
            "central live firewall and explicit operator authority remain mandatory",
        ],
    }


def exit_policy_report(connection: sqlite3.Connection) -> dict[str, Any]:
    snapshots, exclusions = load_exit_evidence(connection)
    return evaluate_exit_policies(snapshots, exclusions=exclusions)


def open_read_only_ledger(path: Path | str) -> sqlite3.Connection:
    source = Path(path).resolve()
    connection = sqlite3.connect(
        f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30.0
    )
    try:
        install_signal_history(connection)
        connection.execute("PRAGMA query_only=ON")
    except Exception:
        connection.close()
        raise
    return connection


__all__ = [
    "ExitEvidenceSnapshot",
    "evaluate_exit_policies",
    "exit_policy_report",
    "load_exit_evidence",
    "open_read_only_ledger",
]
