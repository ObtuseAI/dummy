"""Parameter-jitter robustness test for research genomes.

A candidate that only performs at its exact parameter values is overfit: a
tiny change to any threshold collapses the edge. A robust candidate keeps a
positive edge across a small neighborhood of nearby parameters. This module
builds that neighborhood (perturb each gene one step in each direction,
clamped into the valid box), replays every neighbor against the SAME settled
rows, and reports whether the candidate's edge survives -- so the evolution
lab can flag (and refuse to advance) fragile winners.

Deterministic and research-only: it reuses the lab's causal replay and never
touches live weights.
"""
from __future__ import annotations

from typing import Any, Sequence

from autonomy.evolution_lab import (
    ResearchGenome,
    _bounded_genome,
    genome_trades,
    summarize_trades,
)

# One jitter step per gene (in the gene's native units). Small, deliberate
# perturbations -- large enough to expose a knife-edge fit, small enough that a
# genuinely good region still passes.
JITTER_STEPS = {
    "shrinkage": 0.10,
    "edge_threshold_cents": 1,
    "max_uncertainty": 0.03,
    "max_entry_price_cents": 5,
}
MIN_NEIGHBOR_TRADES = 10
# A candidate is robust when at least this fraction of its evaluable neighbors
# keep a positive mean-PnL lower bound (event-cluster CI), and the center is
# itself positive.
ROBUST_NEIGHBOR_FRACTION = 0.60


def jitter_neighborhood(genome: ResearchGenome) -> list[ResearchGenome]:
    """Axis neighbors: each gene perturbed one step each way, clamped, deduped."""
    base = (
        genome.shrinkage, genome.edge_threshold_cents,
        genome.max_uncertainty, genome.max_entry_price_cents,
    )
    neighbors: dict[str, ResearchGenome] = {}
    for direction in (-1.0, 1.0):
        for gene, step in JITTER_STEPS.items():
            values = list(base)
            index = ("shrinkage", "edge_threshold_cents",
                     "max_uncertainty", "max_entry_price_cents").index(gene)
            values[index] = values[index] + direction * step
            candidate = _bounded_genome(*values)
            if candidate != genome:
                neighbors[candidate.genome_id] = candidate
    return list(neighbors.values())


def _positive_lower_bound(summary: dict[str, Any]) -> bool:
    ci = summary.get("mean_pnl_ci95")
    if isinstance(ci, dict) and ci.get("lower") is not None:
        return float(ci["lower"]) > 0.0
    # No dispersion estimate -> fall back to a positive point mean.
    mean = summary.get("average_pnl_cents")
    return isinstance(mean, (int, float)) and mean > 0.0


def parameter_jitter_robustness(
    rows: Sequence[dict[str, Any]],
    genome: ResearchGenome,
    *,
    scenario_name: str = "baseline",
) -> dict[str, Any]:
    """Evaluate a genome and its jitter neighbors on the same rows.

    Returns the center's edge, the fraction of evaluable neighbors that keep a
    positive mean-PnL lower bound, and a ROBUST/FRAGILE verdict.
    """
    center = summarize_trades(genome_trades(rows, genome, scenario_name=scenario_name))
    center_positive = center["trades"] > 0 and _positive_lower_bound(center)

    neighbors = jitter_neighborhood(genome)
    evaluable = 0
    surviving = 0
    neighbor_rois: list[float] = []
    for neighbor in neighbors:
        summary = summarize_trades(
            genome_trades(rows, neighbor, scenario_name=scenario_name)
        )
        if summary["trades"] < MIN_NEIGHBOR_TRADES:
            continue
        evaluable += 1
        if _positive_lower_bound(summary):
            surviving += 1
        roi = summary.get("roi_on_entry_cost")
        if isinstance(roi, (int, float)):
            neighbor_rois.append(float(roi))

    survival_fraction = surviving / evaluable if evaluable else 0.0
    robust = (
        center_positive
        and evaluable >= 2
        and survival_fraction >= ROBUST_NEIGHBOR_FRACTION
    )
    return {
        "version": "parameter_jitter_robustness_v1",
        "genome_id": genome.genome_id,
        "center_positive": center_positive,
        "center_roi": center.get("roi_on_entry_cost"),
        "center_trades": center["trades"],
        "neighbors_evaluated": evaluable,
        "neighbors_surviving": surviving,
        "neighbor_survival_fraction": round(survival_fraction, 4),
        "neighbor_roi_min": round(min(neighbor_rois), 6) if neighbor_rois else None,
        "neighbor_roi_mean": (
            round(sum(neighbor_rois) / len(neighbor_rois), 6) if neighbor_rois else None
        ),
        "verdict": "ROBUST" if robust else "FRAGILE",
        "execution_authority": False,
    }
