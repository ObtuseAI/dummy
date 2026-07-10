"""Quarantined recursive research evolution for Dummy.

This module evolves *research genomes*, not production code.  A genome is a
small, auditable forecast-selection policy.  Every generation is evaluated by
causal replay, event-cluster purging, fee/slippage stress, and later forward
evidence.  The lab may rotate its own report-only research candidate, but it
cannot write weights, alter risk, place orders, deploy code, or authorize
capital.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import product
from typing import Any, Iterable, Sequence

from autonomy.fees import kalshi_taker_fee_cents


@dataclass(frozen=True)
class ResearchGenome:
    """Bounded forecast/execution-selection parameters for offline replay."""

    shrinkage: float
    edge_threshold_cents: int
    max_uncertainty: float
    max_entry_price_cents: int

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> ResearchGenome | None:
        if not isinstance(value, dict):
            return None
        try:
            genome = cls(
                shrinkage=round(float(value["shrinkage"]), 4),
                edge_threshold_cents=int(value["edge_threshold_cents"]),
                max_uncertainty=round(float(value["max_uncertainty"]), 4),
                max_entry_price_cents=int(value["max_entry_price_cents"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return genome if genome.is_bounded() else None

    def is_bounded(self) -> bool:
        return (
            0.20 <= self.shrinkage <= 1.35
            and 3 <= self.edge_threshold_cents <= 20
            and 0.08 <= self.max_uncertainty <= 0.40
            and 40 <= self.max_entry_price_cents <= 90
        )

    @property
    def genome_id(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return f"rg-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]}"


INCUMBENT_GENOME = ResearchGenome(1.0, 3, 0.35, 90)
STRESS_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "name": "baseline",
        "slippage_cents": 1,
        "fee_multiplier": 1.0,
        "edge_retention": 1.0,
        "uncertainty_multiplier": 1.0,
    },
    {
        "name": "wide_spread",
        "slippage_cents": 5,
        "fee_multiplier": 1.0,
        "edge_retention": 1.0,
        "uncertainty_multiplier": 1.0,
    },
    {
        "name": "edge_decay",
        "slippage_cents": 3,
        "fee_multiplier": 1.0,
        "edge_retention": 0.5,
        "uncertainty_multiplier": 1.25,
    },
    {
        "name": "severe_liquidity",
        "slippage_cents": 10,
        "fee_multiplier": 1.5,
        "edge_retention": 0.75,
        "uncertainty_multiplier": 1.5,
    },
)


def _time(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
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


def _mean_ci95(values: Sequence[float]) -> dict[str, Any] | None:
    if not values:
        return None
    numbers = [float(value) for value in values]
    mean = sum(numbers) / len(numbers)
    if len(numbers) < 2:
        return {
            "mean": round(mean, 6),
            "lower": None,
            "upper": None,
            "n": len(numbers),
            "method": "normal_mean_95",
        }
    variance = sum((value - mean) ** 2 for value in numbers) / (len(numbers) - 1)
    half = 1.96 * math.sqrt(variance / len(numbers))
    return {
        "mean": round(mean, 6),
        "lower": round(mean - half, 6),
        "upper": round(mean + half, 6),
        "n": len(numbers),
        "method": "normal_mean_95",
    }


def evidence_fingerprint(rows: Sequence[dict[str, Any]]) -> str:
    """Hash only immutable, point-in-time replay inputs and settlements."""
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: (str(item["ticker"]), _time(item["created_at"]))):
        payload = {
            "ticker": str(row["ticker"]),
            "cluster": str(row["cluster"]),
            "forecast": round(float(row["forecast"]), 10),
            "market": round(float(row["market"]), 10),
            "uncertainty": round(float(row["uncertainty"]), 10),
            "result": int(row["result"]),
            "created_at": _time(row["created_at"]).isoformat(),
            "settled_at": _time(row["settled_at"]).isoformat(),
        }
        digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _bounded_genome(
    shrinkage: float,
    edge: int,
    uncertainty: float,
    max_price: int,
) -> ResearchGenome:
    return ResearchGenome(
        shrinkage=round(min(1.35, max(0.20, shrinkage)), 4),
        edge_threshold_cents=min(20, max(3, int(edge))),
        max_uncertainty=round(min(0.40, max(0.08, uncertainty)), 4),
        max_entry_price_cents=min(90, max(40, int(max_price))),
    )


def candidate_population(
    previous_active: ResearchGenome | None,
    *,
    generation: int,
    limit: int = 96,
) -> tuple[ResearchGenome, ...]:
    """Create deterministic bounded mutations plus broad lattice exploration."""
    unique: dict[str, ResearchGenome] = {}

    def add(genome: ResearchGenome) -> None:
        if genome.is_bounded():
            unique.setdefault(genome.genome_id, genome)

    add(INCUMBENT_GENOME)
    parent = previous_active or INCUMBENT_GENOME
    add(parent)
    for ds, de, du, dp in product(
        (-0.20, -0.08, 0.08, 0.20),
        (-3, 0, 3),
        (-0.08, 0.0, 0.08),
        (-15, 0, 15),
    ):
        add(_bounded_genome(
            parent.shrinkage + ds,
            parent.edge_threshold_cents + de,
            parent.max_uncertainty + du,
            parent.max_entry_price_cents + dp,
        ))

    lattice = [
        ResearchGenome(s, e, u, p)
        for s, e, u, p in product(
            (0.25, 0.50, 0.75, 1.00, 1.25),
            (3, 5, 8, 12, 16),
            (0.12, 0.18, 0.25, 0.35),
            (50, 65, 75, 90),
        )
    ]
    # Vary the broad exploratory sample by generation without nondeterminism.
    lattice.sort(key=lambda genome: hashlib.sha256(
        f"{generation}:{genome.genome_id}".encode()
    ).hexdigest())
    for genome in lattice:
        add(genome)
        if len(unique) >= max(8, int(limit)):
            break
    return tuple(list(unique.values())[:max(8, int(limit))])


def _scenario(name: str) -> dict[str, Any]:
    for scenario in STRESS_SCENARIOS:
        if scenario["name"] == name:
            return scenario
    raise ValueError(f"unknown stress scenario: {name}")


def genome_trades(
    rows: Iterable[dict[str, Any]],
    genome: ResearchGenome,
    *,
    scenario_name: str = "baseline",
) -> list[dict[str, Any]]:
    """Replay a bounded genome against factual outcomes under one scenario."""
    scenario = _scenario(scenario_name)
    trades: list[dict[str, Any]] = []
    for row in rows:
        uncertainty = float(row["uncertainty"]) * float(scenario["uncertainty_multiplier"])
        if uncertainty > genome.max_uncertainty:
            continue
        market = float(row["market"])
        model_edge = (float(row["forecast"]) - market) * genome.shrinkage
        stressed_edge = model_edge * float(scenario["edge_retention"])
        if abs(stressed_edge) * 100.0 < genome.edge_threshold_cents:
            continue
        buy_yes = stressed_edge > 0
        base_price = round((market if buy_yes else 1.0 - market) * 100.0)
        price = min(99, max(1, int(base_price) + int(scenario["slippage_cents"])))
        if price > genome.max_entry_price_cents:
            continue
        won = bool(row["result"]) if buy_yes else not bool(row["result"])
        fee = math.ceil(
            kalshi_taker_fee_cents(price, 1, str(row["ticker"]))
            * float(scenario["fee_multiplier"])
        )
        pnl = (100 - price if won else -price) - fee
        trades.append({
            "ticker": str(row["ticker"]),
            "cluster": str(row["cluster"]),
            "created_at": _time(row["created_at"]),
            "base_price_cents": int(base_price),
            "price_cents": price,
            "fee_cents": fee,
            "pnl_cents": pnl,
            "cost_cents": price + fee,
            "won": won,
            "scenario": scenario_name,
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
    return {
        "trades": len(trades),
        "event_clusters": len({str(trade["cluster"]) for trade in trades}),
        "net_pnl_cents": sum(pnl),
        "entry_cost_cents": sum(costs),
        "average_pnl_cents": round(sum(pnl) / len(pnl), 6) if pnl else None,
        "mean_pnl_ci95": _mean_ci95(pnl),
        "win_rate": round(sum(value > 0 for value in pnl) / len(pnl), 6) if pnl else None,
        "roi_on_entry_cost": round(sum(pnl) / sum(costs), 6) if costs and sum(costs) else None,
        "max_drawdown_cents": max_drawdown,
    }


def _temporal_folds(
    rows: Sequence[dict[str, Any]], requested: int = 5
) -> list[list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: (_time(row["created_at"]), str(row["ticker"])))
    count = min(requested, len(ordered))
    if count == 0:
        return []
    folds: list[list[dict[str, Any]]] = [[] for _ in range(count)]
    for index, row in enumerate(ordered):
        folds[min(count - 1, index * count // len(ordered))].append(row)
    return folds


def _complexity(genome: ResearchGenome) -> float:
    return round(
        abs(genome.shrinkage - 1.0)
        + abs(genome.edge_threshold_cents - 3) / 20.0
        + abs(genome.max_uncertainty - 0.35) * 2.0
        + abs(genome.max_entry_price_cents - 90) / 100.0,
        6,
    )


def _rank(summary: dict[str, Any], genome: ResearchGenome) -> tuple[Any, ...]:
    lower = (summary.get("mean_pnl_ci95") or {}).get("lower")
    return (
        float(lower) if lower is not None else float("-inf"),
        int(summary.get("net_pnl_cents") or 0),
        -int(summary.get("max_drawdown_cents") or 0),
        -_complexity(genome),
        genome.genome_id,
    )


def _cluster_advantage_ci(
    challenger: Sequence[dict[str, Any]],
    incumbent: Sequence[dict[str, Any]],
    *,
    seed: int = 20260710,
    simulations: int = 1000,
) -> dict[str, Any] | None:
    challenger_clusters: dict[str, int] = {}
    incumbent_clusters: dict[str, int] = {}
    for trade in challenger:
        key = str(trade["cluster"])
        challenger_clusters[key] = challenger_clusters.get(key, 0) + int(trade["pnl_cents"])
    for trade in incumbent:
        key = str(trade["cluster"])
        incumbent_clusters[key] = incumbent_clusters.get(key, 0) + int(trade["pnl_cents"])
    clusters = sorted(set(challenger_clusters) | set(incumbent_clusters))
    if not clusters:
        return None
    differences = [challenger_clusters.get(key, 0) - incumbent_clusters.get(key, 0)
                   for key in clusters]
    rng = random.Random(seed)
    samples = [
        sum(rng.choice(differences) for _ in differences)
        for _ in range(max(200, int(simulations)))
    ]
    return {
        "observed": sum(differences),
        "lower": round(_percentile(samples, 0.025) or 0.0, 6),
        "upper": round(_percentile(samples, 0.975) or 0.0, 6),
        "event_clusters": len(clusters),
        "simulations": max(200, int(simulations)),
        "method": "paired_event_cluster_bootstrap_total_pnl_advantage",
    }


def trace_replay_audit(order_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Fingerprint witnessed order truth and expose replay completeness gaps."""
    canonical = []
    for row in sorted(order_rows, key=lambda item: str(item.get("decision_id"))):
        canonical.append({
            "decision_id": str(row.get("decision_id")),
            "ticker": str(row.get("ticker")),
            "price_cents": row.get("price_cents"),
            "ev_cents": row.get("ev_cents"),
            "uncertainty": row.get("uncertainty"),
            "submitted_at": row.get("submitted_at"),
            "queue_ahead": row.get("queue_ahead"),
            "filled": bool(row.get("filled")),
            "known": bool(row.get("known")),
            "settled_pnl_cents": row.get("settled_pnl_cents"),
        })
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    missing_queue = sum(row["queue_ahead"] is None for row in canonical)
    unresolved = sum(not row["known"] for row in canonical)
    filled = sum(row["filled"] for row in canonical)
    settled = sum(row["settled_pnl_cents"] is not None for row in canonical)
    losing = sum((row["settled_pnl_cents"] or 0) < 0 for row in canonical)
    impossible = sum(
        row["settled_pnl_cents"] is not None and not row["filled"] for row in canonical
    )
    return {
        "method": "canonical_witnessed_shadow_order_trace_replay",
        "trace_fingerprint": hashlib.sha256(payload.encode()).hexdigest(),
        "orders": len(canonical),
        "known_outcomes": len(canonical) - unresolved,
        "unresolved_orders": unresolved,
        "orders_with_queue_snapshot": len(canonical) - missing_queue,
        "orders_missing_queue_snapshot": missing_queue,
        "witnessed_fills": filled,
        "settled_fills": settled,
        "settled_losses": losing,
        "settlement_without_fill_anomalies": impossible,
        "complete_for_execution_optimization": bool(
            canonical and missing_queue == 0 and unresolved == 0 and impossible == 0
        ),
        "execution_authority": False,
    }


def run_evolution_lab(
    rows: Sequence[dict[str, Any]],
    *,
    previous_report: dict[str, Any] | None = None,
    as_of: datetime | None = None,
    population_size: int = 96,
    bootstrap_simulations: int = 1000,
) -> dict[str, Any]:
    """Run one deterministic research generation and update its forward epoch."""
    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    previous_lab = (
        (previous_report or {}).get("evolution_lab")
        if isinstance(previous_report, dict)
        else None
    ) or {}
    fingerprint = evidence_fingerprint(rows)
    previous_fingerprint = (previous_lab.get("evidence") or {}).get("fingerprint")
    previous_count = int((previous_lab.get("evidence") or {}).get("settled_markets") or 0)
    evidence_advanced = fingerprint != previous_fingerprint
    previous_generation = int(previous_lab.get("generation") or 0)
    generation = previous_generation + (1 if evidence_advanced else 0)

    previous_active_block = previous_lab.get("active_research_candidate") or {}
    previous_active = ResearchGenome.from_mapping(previous_active_block.get("genome"))
    population = candidate_population(
        previous_active,
        generation=max(1, generation),
        limit=population_size,
    )
    folds = _temporal_folds(rows)
    fold_reports: list[dict[str, Any]] = []
    challenger_oos: dict[str, list[dict[str, Any]]] = {
        scenario["name"]: [] for scenario in STRESS_SCENARIOS
    }
    incumbent_oos: dict[str, list[dict[str, Any]]] = {
        scenario["name"]: [] for scenario in STRESS_SCENARIOS
    }
    selected: list[ResearchGenome] = []
    history = list(folds[0]) if folds else []
    for fold_number, test_rows in enumerate(folds[1:], start=2):
        test_start = min(_time(row["created_at"]) for row in test_rows)
        training = [row for row in history if _time(row["settled_at"]) < test_start]
        training_clusters = {str(row["cluster"]) for row in training}
        purged_test = [row for row in test_rows if str(row["cluster"]) not in training_clusters]
        candidates: list[tuple[ResearchGenome, dict[str, Any]]] = []
        for genome in population:
            summary = summarize_trades(genome_trades(training, genome))
            if summary["trades"] >= 20:
                candidates.append((genome, summary))
        if not candidates:
            history.extend(test_rows)
            continue
        leader, training_summary = max(
            candidates,
            key=lambda item: _rank(item[1], item[0]),
        )
        selected.append(leader)
        scenario_results: dict[str, Any] = {}
        for scenario in challenger_oos:
            challenger = genome_trades(purged_test, leader, scenario_name=scenario)
            incumbent = genome_trades(purged_test, INCUMBENT_GENOME, scenario_name=scenario)
            challenger_oos[scenario].extend(challenger)
            incumbent_oos[scenario].extend(incumbent)
            scenario_results[scenario] = summarize_trades(challenger)
        fold_reports.append({
            "fold": fold_number,
            "selected_genome_id": leader.genome_id,
            "selected_genome": asdict(leader),
            "selected_complexity": _complexity(leader),
            "training_rows": len(training),
            "training_result": training_summary,
            "test_rows": len(test_rows),
            "purged_test_rows": len(test_rows) - len(purged_test),
            "scenario_results": scenario_results,
            "test_start": test_start.isoformat(),
            "test_end": max(_time(row["created_at"]) for row in test_rows).isoformat(),
            "training_latest_settlement": (
                max(_time(row["settled_at"]) for row in training).isoformat()
                if training else None
            ),
        })
        history.extend(test_rows)

    research_leader = selected[-1] if selected else previous_active
    baseline_summary = summarize_trades(challenger_oos["baseline"])
    incumbent_summary = summarize_trades(incumbent_oos["baseline"])
    advantage = _cluster_advantage_ci(
        challenger_oos["baseline"],
        incumbent_oos["baseline"],
        simulations=bootstrap_simulations,
    )
    stress_results = {
        name: summarize_trades(trades) for name, trades in challenger_oos.items()
    }
    lower = (baseline_summary.get("mean_pnl_ci95") or {}).get("lower")
    advantage_lower = (advantage or {}).get("lower")
    severe = stress_results.get("severe_liquidity") or {}
    retrospective_gate = bool(
        research_leader
        and len(fold_reports) >= 3
        and baseline_summary["trades"] >= 100
        and baseline_summary["event_clusters"] >= 20
        and lower is not None and lower > 0
        and advantage_lower is not None and advantage_lower > 0
        and baseline_summary["max_drawdown_cents"] <= incumbent_summary["max_drawdown_cents"]
        and int(severe.get("net_pnl_cents") or 0) > 0
    )

    active = previous_active or research_leader
    active_since = previous_active_block.get("epoch_started_at")
    rotation_reason = "retained_previous_research_candidate"
    if previous_active is None and active is not None:
        active_since = now.isoformat()
        rotation_reason = "initialized_first_research_epoch"
    try:
        epoch_start = _time(active_since) if active_since else now
    except (TypeError, ValueError):
        epoch_start = now
        active_since = now.isoformat()

    forward_rows = [row for row in rows if _time(row["created_at"]) >= epoch_start]
    forward_stress_trades = {
        scenario["name"]: genome_trades(
            forward_rows, active, scenario_name=scenario["name"]
        ) if active else []
        for scenario in STRESS_SCENARIOS
    }
    forward_active = forward_stress_trades["baseline"]
    forward_incumbent = genome_trades(forward_rows, INCUMBENT_GENOME)
    forward_stress = {
        name: summarize_trades(trades) for name, trades in forward_stress_trades.items()
    }
    forward_summary = forward_stress["baseline"]
    forward_incumbent_summary = summarize_trades(forward_incumbent)
    forward_advantage = _cluster_advantage_ci(
        forward_active,
        forward_incumbent,
        simulations=bootstrap_simulations,
    )
    forward_lower = (forward_summary.get("mean_pnl_ci95") or {}).get("lower")
    forward_advantage_lower = (forward_advantage or {}).get("lower")
    forward_gate = bool(
        forward_summary["trades"] >= 100
        and forward_summary["event_clusters"] >= 10
        and forward_lower is not None and forward_lower > 0
        and forward_advantage_lower is not None and forward_advantage_lower > 0
        and int((forward_stress.get("severe_liquidity") or {}).get("net_pnl_cents") or 0) > 0
    )

    forward_failed = bool(
        forward_summary["trades"] >= 30
        and forward_summary["event_clusters"] >= 5
        and int(forward_summary.get("net_pnl_cents") or 0) < 0
        and int((forward_advantage or {}).get("observed") or 0) < 0
    )

    # The lab can rotate only its quarantined research epoch.  It waits for a
    # minimally diverse forward audit of the current candidate so hourly runs
    # cannot churn candidates and erase unfavorable evidence.
    rotated = False
    if (
        previous_active is not None
        and research_leader is not None
        and research_leader.genome_id != previous_active.genome_id
        and retrospective_gate
        and forward_failed
    ):
        active = research_leader
        active_since = now.isoformat()
        forward_rows = []
        forward_summary = summarize_trades([])
        forward_incumbent_summary = summarize_trades([])
        forward_stress = {
            scenario["name"]: summarize_trades([]) for scenario in STRESS_SCENARIOS
        }
        forward_advantage = None
        forward_gate = False
        rotated = True
        rotation_reason = "retired_failed_forward_epoch_after_diverse_evidence"

    leader_counts: dict[str, int] = {}
    for genome in selected:
        leader_counts[genome.genome_id] = leader_counts.get(genome.genome_id, 0) + 1
    dominant_share = (
        max(leader_counts.values()) / len(selected) if selected else None
    )
    return {
        "lab_name": "DUMMY_EVOLUTION_LAB",
        "generation": generation,
        "status": (
            "READY_FOR_EXPLICIT_SHADOW_REVIEW"
            if forward_gate else "ACCUMULATING_FORWARD_EVIDENCE"
        ),
        "method": "causal_nested_replay_mutation_stress_and_forward_ratchet",
        "evidence": {
            "fingerprint": fingerprint,
            "previous_fingerprint": previous_fingerprint,
            "advanced": evidence_advanced,
            "settled_markets": len(rows),
            "new_settled_markets": max(0, len(rows) - previous_count),
            "event_clusters": len({str(row["cluster"]) for row in rows}),
        },
        "population": {
            "candidates_generated": len(population),
            "bounded": all(genome.is_bounded() for genome in population),
            "parent_genome_id": previous_active.genome_id if previous_active else None,
            "folds_completed": len(fold_reports),
            "distinct_fold_leaders": len(leader_counts),
            "dominant_leader_share": round(dominant_share, 6)
            if dominant_share is not None else None,
        },
        "folds": fold_reports,
        "research_leader": {
            "genome_id": research_leader.genome_id,
            "genome": asdict(research_leader),
        } if research_leader else None,
        "retrospective_out_of_sample": {
            "challenger": baseline_summary,
            "incumbent": incumbent_summary,
            "paired_pnl_advantage_ci95": advantage,
            "stress_scenarios": stress_results,
            "passes_research_epoch_gate": retrospective_gate,
        },
        "active_research_candidate": {
            "genome_id": active.genome_id,
            "genome": asdict(active),
            "epoch_started_at": active_since,
            "rotated_this_generation": rotated,
            "rotation_reason": rotation_reason,
        } if active else None,
        "forward_ratchet": {
            "availability_rule": "decision created at or after research epoch start",
            "candidate": forward_summary,
            "incumbent": forward_incumbent_summary,
            "paired_pnl_advantage_ci95": forward_advantage,
            "stress_scenarios": forward_stress,
            "failed_research_epoch": forward_failed,
            "ready_for_explicit_shadow_review": forward_gate,
            "minimums": {
                "trades": 100,
                "event_clusters": 10,
                "positive_mean_pnl_lower95": True,
                "positive_paired_advantage_lower95": True,
            },
        },
        "autonomous_actions": {
            "bounded_genomes_generated": len(population),
            "causal_folds_replayed": len(fold_reports),
            "stress_scenarios_replayed": len(STRESS_SCENARIOS),
            "research_epoch_rotated": rotated,
            "production_code_changed": False,
            "weights_changed": False,
            "risk_caps_changed": False,
            "orders_placed": False,
        },
        "authority": {
            "automatic_research_candidate_rotation": True,
            "code_mutation_authority": False,
            "deployment_authority": False,
            "weight_write_authority": False,
            "risk_write_authority": False,
            "execution_authority": False,
            "capital_authority": False,
        },
        "evidence_quarantine": {
            "tier": "recursive_simulation_challenger_only",
            "counts_toward_canary": False,
            "counts_toward_scale": False,
            "may_place_orders": False,
        },
    }
