"""Deterministic lineage views over a validated genome registry."""

from __future__ import annotations

from .registry import GenomeRegistry


def lineage_report(registry: GenomeRegistry) -> dict[str, object]:
    genomes = registry.genomes()
    children: dict[str, list[str]] = {item.genome_id: [] for item in genomes}
    for genome in genomes:
        for parent in genome.parent_genome_ids:
            children[parent].append(genome.genome_id)
    roots = tuple(item.genome_id for item in genomes if not item.parent_genome_ids)
    leaves = tuple(
        item.genome_id for item in genomes if not children[item.genome_id]
    )
    return {
        "schema_version": 1,
        "roots": sorted(roots),
        "leaves": sorted(leaves),
        "nodes": [
            {
                "genome_id": item.genome_id,
                "generation": item.generation,
                "parents": list(item.parent_genome_ids),
                "children": sorted(children[item.genome_id]),
            }
            for item in genomes
        ],
        "deterministic": True,
    }


__all__ = ["lineage_report"]
