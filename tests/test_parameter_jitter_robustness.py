"""Parameter-jitter robustness distinguishes durable from knife-edge genomes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.evolution_lab import ResearchGenome
from autonomy.robustness import (
    JITTER_STEPS,
    jitter_neighborhood,
    parameter_jitter_robustness,
)


def _rows(n=200, *, edge=0.26, start=datetime(2025, 1, 1, tzinfo=timezone.utc)):
    """Rows where the forecast has a real, wide edge over the market."""
    rows = []
    for i in range(n):
        result = i % 5 != 0  # 80% YES
        rows.append({
            "ticker": f"EV-{i:05d}", "cluster": f"c-{i:05d}",
            "forecast": (0.5 + edge) if result else (0.5 - edge),
            "market": 0.5, "uncertainty": 0.10, "result": int(result),
            "created_at": start + timedelta(hours=2 * i),
            "settled_at": start + timedelta(hours=2 * i + 1),
        })
    return rows


def test_jitter_neighborhood_perturbs_each_gene_both_ways_bounded():
    genome = ResearchGenome(0.75, 8, 0.20, 70)
    neighbors = jitter_neighborhood(genome)
    # 4 genes x 2 directions = up to 8 distinct bounded neighbors.
    assert 6 <= len(neighbors) <= 8
    assert genome not in neighbors
    assert all(g.is_bounded() for g in neighbors)
    # A shrinkage step of +0.10 must appear.
    assert any(abs(g.shrinkage - (0.75 + JITTER_STEPS["shrinkage"])) < 1e-9
               for g in neighbors)


def test_wide_edge_genome_is_robust():
    genome = ResearchGenome(0.75, 5, 0.25, 80)
    report = parameter_jitter_robustness(_rows(edge=0.30), genome)
    assert report["center_positive"] is True
    assert report["neighbors_evaluated"] >= 2
    assert report["verdict"] == "ROBUST"
    assert report["neighbor_survival_fraction"] >= 0.6


def test_knife_edge_genome_is_fragile():
    # A genome whose edge threshold sits right at the margin: rows carry only a
    # thin ~2c edge, so a +1c threshold step drops most trades -> fragile.
    rows = _rows(edge=0.015)   # ~1.5c raw edge
    genome = ResearchGenome(1.0, 1, 0.30, 90)
    report = parameter_jitter_robustness(rows, genome)
    # Either the center can't sustain a positive lower bound or the neighbors
    # collapse; both are FRAGILE.
    assert report["verdict"] == "FRAGILE"


def test_empty_rows_is_fragile_not_crash():
    report = parameter_jitter_robustness([], ResearchGenome(0.75, 8, 0.20, 70))
    assert report["verdict"] == "FRAGILE"
    assert report["center_trades"] == 0
    assert report["execution_authority"] is False
