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
from autonomy.stats import mean_ci95 as _mean_ci95


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


def crossover_genomes(
    parent_a: ResearchGenome, parent_b: ResearchGenome,
) -> list[ResearchGenome]:
    """Deterministic recombinant children mixing two parents' genes.

    Single-parent grid mutation cannot reach a genome that combines proven
    building blocks from two DIFFERENT lineages -- e.g. one parent's tight
    shrinkage with another's permissive entry price. Uniform crossover emits
    the two complementary allele swaps; the midpoint blend covers the
    recombinant centre. All children are clamped into the valid genome box,
    so a cross never produces an out-of-bounds architecture. Deterministic
    (no RNG) to preserve the lab's causal-replay reproducibility.
    """
    children = [
        # Two complementary uniform-crossover children (alternate the source
        # of each gene between the parents).
        _bounded_genome(
            parent_a.shrinkage, parent_b.edge_threshold_cents,
            parent_a.max_uncertainty, parent_b.max_entry_price_cents,
        ),
        _bounded_genome(
            parent_b.shrinkage, parent_a.edge_threshold_cents,
            parent_b.max_uncertainty, parent_a.max_entry_price_cents,
        ),
        # Midpoint blend of every gene -- the recombinant centroid.
        _bounded_genome(
            (parent_a.shrinkage + parent_b.shrinkage) / 2.0,
            round((parent_a.edge_threshold_cents + parent_b.edge_threshold_cents) / 2.0),
            (parent_a.max_uncertainty + parent_b.max_uncertainty) / 2.0,
            round((parent_a.max_entry_price_cents + parent_b.max_entry_price_cents) / 2.0),
        ),
    ]
    return children


def candidate_population(
    previous_active: ResearchGenome | None,
    *,
    generation: int,
    limit: int = 96,
    archive_parents: Sequence[ResearchGenome] = (),
    mutation_scale: float = 1.0,
) -> tuple[ResearchGenome, ...]:
    """Create deterministic bounded mutations plus broad lattice exploration."""
    unique: dict[str, ResearchGenome] = {}
    scale = min(2.0, max(0.25, float(mutation_scale)))

    def add(genome: ResearchGenome) -> None:
        if genome.is_bounded():
            unique.setdefault(genome.genome_id, genome)

    add(INCUMBENT_GENOME)
    parent = previous_active or INCUMBENT_GENOME
    add(parent)
    for archive_parent in archive_parents:
        add(archive_parent)

    # Retained niche elites add narrow local probes before the larger parent
    # lattice so they cannot be crowded out by generation-order truncation.
    for archive_parent in archive_parents[:8]:
        for direction in (-1.0, 1.0):
            add(_bounded_genome(
                archive_parent.shrinkage + direction * 0.08 * scale,
                archive_parent.edge_threshold_cents + round(direction * 2 * scale),
                archive_parent.max_uncertainty + direction * 0.03 * scale,
                archive_parent.max_entry_price_cents + round(direction * 5 * scale),
            ))

    # Sexual recombination: cross the active parent with each retained elite,
    # and adjacent elites with each other, so building blocks from distinct
    # lineages combine before the broad lattice fills remaining slots. These
    # get priority over generic lattice exploration for exactly that reason.
    cross_partners = list(archive_parents[:8])
    for partner in cross_partners:
        for child in crossover_genomes(parent, partner):
            add(child)
    for left, right in zip(cross_partners, cross_partners[1:]):
        for child in crossover_genomes(left, right):
            add(child)
    for ds, de, du, dp in product(
        (-0.20, -0.08, 0.08, 0.20),
        (-3, 0, 3),
        (-0.08, 0.0, 0.08),
        (-15, 0, 15),
    ):
        add(_bounded_genome(
            parent.shrinkage + ds * scale,
            parent.edge_threshold_cents + round(de * scale),
            parent.max_uncertainty + du * scale,
            parent.max_entry_price_cents + round(dp * scale),
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


QUALITY_DIVERSITY_MAX_CELLS = 48
QUALITY_DIVERSITY_POSSIBLE_CELLS = 81


def _genome_distance(left: ResearchGenome, right: ResearchGenome) -> float:
    return round(
        abs(left.shrinkage - right.shrinkage) / 1.15
        + abs(left.edge_threshold_cents - right.edge_threshold_cents) / 17.0
        + abs(left.max_uncertainty - right.max_uncertainty) / 0.32
        + abs(left.max_entry_price_cents - right.max_entry_price_cents) / 50.0,
        8,
    )


def _niche_cell(genome: ResearchGenome, trade_count: int) -> str:
    model = (
        "market_anchored" if genome.shrinkage <= 0.60
        else "balanced" if genome.shrinkage <= 1.00 else "model_forward"
    )
    risk = (
        "conservative"
        if genome.max_uncertainty <= 0.20 and genome.max_entry_price_cents <= 65
        else "balanced"
        if genome.max_uncertainty <= 0.30 and genome.max_entry_price_cents <= 75
        else "aggressive"
    )
    edge = (
        "broad" if genome.edge_threshold_cents <= 5
        else "selective" if genome.edge_threshold_cents <= 11 else "extreme"
    )
    activity = "sparse" if trade_count < 20 else "selective" if trade_count < 60 else "active"
    return f"model={model}|risk={risk}|edge={edge}|activity={activity}"


def _archive_rank(entry: dict[str, Any]) -> tuple[Any, ...]:
    fitness = entry.get("fitness") or {}
    lower = fitness.get("mean_pnl_lower95")
    advantage = fitness.get("paired_advantage_lower95")
    return (
        float(lower) if lower is not None else float("-inf"),
        float(advantage) if advantage is not None else float("-inf"),
        int(fitness.get("severe_net_pnl_cents") or 0),
        int(fitness.get("net_pnl_cents") or 0),
        -int(fitness.get("max_drawdown_cents") or 0),
        -float(entry.get("complexity") or 0),
        str(entry.get("genome_id") or ""),
    )


def _archive_entry(
    genome: ResearchGenome,
    baseline_trades: Sequence[dict[str, Any]],
    incumbent_trades: Sequence[dict[str, Any]],
    severe_trades: Sequence[dict[str, Any]],
    *,
    generation: int,
    bootstrap_simulations: int,
) -> dict[str, Any] | None:
    if not baseline_trades:
        return None
    baseline = summarize_trades(baseline_trades)
    severe = summarize_trades(severe_trades)
    advantage = _cluster_advantage_ci(
        baseline_trades,
        incumbent_trades,
        simulations=bootstrap_simulations,
    )
    lower = (baseline.get("mean_pnl_ci95") or {}).get("lower")
    advantage_lower = (advantage or {}).get("lower")
    eligible = bool(
        baseline["trades"] >= 100
        and baseline["event_clusters"] >= 20
        and lower is not None and lower > 0
        and advantage_lower is not None and advantage_lower > 0
        and int(severe.get("net_pnl_cents") or 0) > 0
    )
    return {
        "cell": _niche_cell(genome, int(baseline["trades"])),
        "genome_id": genome.genome_id,
        "genome": asdict(genome),
        "generation": generation,
        "complexity": _complexity(genome),
        "fitness": {
            "trades": baseline["trades"],
            "event_clusters": baseline["event_clusters"],
            "net_pnl_cents": baseline["net_pnl_cents"],
            "mean_pnl_lower95": lower,
            "paired_advantage_lower95": advantage_lower,
            "max_drawdown_cents": baseline["max_drawdown_cents"],
            "severe_net_pnl_cents": severe["net_pnl_cents"],
        },
        "paired_pnl_advantage_ci95": advantage,
        "eligible_for_forward_challenge": eligible,
        "evidence_source": "causal_preselected_purged_out_of_sample_folds",
        "execution_authority": False,
    }


def merge_quality_diversity_archive(
    previous_cells: Sequence[dict[str, Any]],
    candidates: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Keep one best out-of-sample genome per behavior niche."""
    cells: dict[str, dict[str, Any]] = {
        str(row["cell"]): dict(row)
        for row in previous_cells
        if isinstance(row, dict) and row.get("cell") and row.get("genome")
    }
    improvements = 0
    for candidate in candidates:
        cell = str(candidate["cell"])
        incumbent = cells.get(cell)
        if incumbent is None or _archive_rank(candidate) > _archive_rank(incumbent):
            cells[cell] = dict(candidate)
            improvements += 1
    ranked = sorted(cells.values(), key=_archive_rank, reverse=True)
    return ranked[:QUALITY_DIVERSITY_MAX_CELLS], improvements


def adaptive_mutation_pressure(
    previous: dict[str, Any] | None,
    *,
    evidence_advanced: bool,
    archive_improvements: int,
    candidates_evaluated: int,
) -> dict[str, Any]:
    current = min(2.0, max(0.25, float((previous or {}).get("next_scale") or 1.0)))
    success_rate = (
        archive_improvements / candidates_evaluated if candidates_evaluated else 0.0
    )
    if not evidence_advanced or candidates_evaluated == 0:
        next_scale = current
        action = "hold_no_new_settled_evidence"
    elif success_rate > 0.20:
        next_scale = min(2.0, current * 1.25)
        action = "expand_after_diverse_archive_success"
    elif success_rate < 0.10:
        next_scale = max(0.25, current * 0.70)
        action = "contract_after_low_archive_success"
    else:
        next_scale = current
        action = "hold_balanced_success_rate"
    return {
        "version": "settlement-ratcheted-mutation-pressure-v1",
        "applied_scale": round(current, 6),
        "next_scale": round(next_scale, 6),
        "archive_improvements": archive_improvements,
        "candidates_evaluated_out_of_sample": candidates_evaluated,
        "archive_success_rate": round(success_rate, 8),
        "action": action,
        "updates_without_new_settlements": not evidence_advanced,
        "code_mutation_authority": False,
    }


def candidate_lineage(
    population: Sequence[ResearchGenome],
    parents: Sequence[tuple[str, ResearchGenome]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for genome in population:
        if not parents:
            records.append({
                "genome_id": genome.genome_id,
                "parent_genome_id": None,
                "normalized_mutation_distance": None,
                "source": "broad_lattice",
            })
            continue
        parent_source, parent = min(
            parents,
            key=lambda item: (_genome_distance(genome, item[1]), item[1].genome_id),
        )
        distance = _genome_distance(genome, parent)
        records.append({
            "genome_id": genome.genome_id,
            "parent_genome_id": parent.genome_id,
            "normalized_mutation_distance": distance,
            "source": "retained_parent" if distance == 0 else f"mutation_from_{parent_source}",
        })
    return records


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


def _active_candidate_robustness(
    rows: Sequence[dict[str, Any]], genome: "ResearchGenome",
) -> dict[str, Any] | None:
    """Parameter-jitter robustness for the active candidate (lazy import)."""
    try:
        from autonomy.robustness import parameter_jitter_robustness

        return parameter_jitter_robustness(rows, genome)
    except Exception:  # noqa: BLE001 - disclosure must never break the lab
        return None


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
    previous_archive = previous_lab.get("quality_diversity_archive") or {}
    previous_cells = (
        previous_archive.get("cells")
        if isinstance(previous_archive.get("cells"), list)
        else []
    )
    archive_parents: list[ResearchGenome] = []
    for cell in previous_cells:
        genome = ResearchGenome.from_mapping(
            cell.get("genome") if isinstance(cell, dict) else None
        )
        if genome is not None and genome not in archive_parents:
            archive_parents.append(genome)
    previous_pressure = previous_lab.get("adaptive_mutation_pressure") or {}
    mutation_scale = min(
        2.0,
        max(0.25, float(previous_pressure.get("next_scale") or 1.0)),
    )
    population = candidate_population(
        previous_active,
        generation=max(1, generation),
        limit=population_size,
        archive_parents=archive_parents,
        mutation_scale=mutation_scale,
    )
    lineage_parents: list[tuple[str, ResearchGenome]] = []
    if previous_active is not None:
        lineage_parents.append(("active", previous_active))
    lineage_parents.extend(("archive", genome) for genome in archive_parents[:8])
    lineage = candidate_lineage(population, lineage_parents)
    folds = _temporal_folds(rows)
    fold_reports: list[dict[str, Any]] = []
    challenger_oos: dict[str, list[dict[str, Any]]] = {
        scenario["name"]: [] for scenario in STRESS_SCENARIOS
    }
    incumbent_oos: dict[str, list[dict[str, Any]]] = {
        scenario["name"]: [] for scenario in STRESS_SCENARIOS
    }
    archive_oos: dict[str, dict[str, Any]] = {}
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
        # A bounded contender set is chosen solely from prior settled training
        # data, then scored on this purged future fold. That lets the archive
        # retain diverse specialists without testing into the selection rule.
        archive_contenders = sorted(
            candidates,
            key=lambda item: _rank(item[1], item[0]),
            reverse=True,
        )[:24]
        archive_incumbent = genome_trades(
            purged_test, INCUMBENT_GENOME, scenario_name="baseline",
        )
        for contender, _training_summary in archive_contenders:
            contender_id = contender.genome_id
            evidence = archive_oos.setdefault(contender_id, {
                "genome": contender,
                "baseline": [],
                "incumbent": [],
                "severe_liquidity": [],
                "folds": [],
            })
            evidence["baseline"].extend(
                genome_trades(purged_test, contender, scenario_name="baseline")
            )
            evidence["incumbent"].extend(archive_incumbent)
            evidence["severe_liquidity"].extend(
                genome_trades(
                    purged_test, contender, scenario_name="severe_liquidity",
                )
            )
            evidence["folds"].append(fold_number)
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

    current_archive_entries = [
        entry
        for evidence in archive_oos.values()
        if (entry := _archive_entry(
            evidence["genome"],
            evidence["baseline"],
            evidence["incumbent"],
            evidence["severe_liquidity"],
            generation=generation,
            bootstrap_simulations=bootstrap_simulations,
        )) is not None
    ]
    archive_cells, archive_improvements = merge_quality_diversity_archive(
        previous_cells, current_archive_entries,
    )
    mutation_pressure = adaptive_mutation_pressure(
        previous_pressure,
        evidence_advanced=evidence_advanced,
        archive_improvements=archive_improvements,
        candidates_evaluated=len(current_archive_entries),
    )

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
            "archive_parents_seeded": len(archive_parents),
            "mutation_scale": mutation_pressure["applied_scale"],
            "folds_completed": len(fold_reports),
            "distinct_fold_leaders": len(leader_counts),
            "dominant_leader_share": round(dominant_share, 6)
            if dominant_share is not None else None,
        },
        "quality_diversity_archive": {
            "version": "oos-research-niche-archive-v1",
            "method": (
                "preselect contenders on settled training data, score on purged future "
                "folds, retain one best genome per behavior niche"
            ),
            "cells": archive_cells,
            "cell_count": len(archive_cells),
            "possible_cells": QUALITY_DIVERSITY_POSSIBLE_CELLS,
            "occupancy": round(
                len(archive_cells) / QUALITY_DIVERSITY_POSSIBLE_CELLS, 8,
            ),
            "current_generation_candidates_evaluated": len(current_archive_entries),
            "current_generation_cell_improvements": archive_improvements,
            "forward_challenge_eligible_cells": sum(
                bool(cell.get("eligible_for_forward_challenge"))
                for cell in archive_cells
            ),
            "archive_seeds_next_research_population": True,
            "automatic_production_selection": False,
            "execution_authority": False,
            "capital_authority": False,
        },
        "adaptive_mutation_pressure": mutation_pressure,
        "candidate_lineage": {
            "version": "research-genome-lineage-v1",
            "records": lineage,
            "record_count": len(lineage),
            "evidence_fingerprint": fingerprint,
            "automatic_code_mutation": False,
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
            # Parameter-jitter robustness: is the active candidate durable, or
            # a knife-edge fit that collapses under a small parameter change?
            # Disclosure only (lazy import avoids the module cycle).
            "robustness": _active_candidate_robustness(rows, active),
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
            "quality_diversity_cells_retained": len(archive_cells),
            "adaptive_mutation_pressure_updated": evidence_advanced,
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
