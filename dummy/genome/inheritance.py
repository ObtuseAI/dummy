"""Explicit, conflict-aware genome inheritance; never silent gene blending."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .schema import ForecastGenome, Gene, GenomeValidationError


def inherit_genome(
    parents: tuple[ForecastGenome, ...],
    *,
    label: str,
    created_at: datetime,
    evidence_ids: tuple[str, ...],
    overrides: Mapping[str, Gene] | None = None,
) -> ForecastGenome:
    if len(parents) < 1:
        raise GenomeValidationError("inheritance requires at least one parent")
    scope = (parents[0].vertical, parents[0].market_type, parents[0].horizon)
    if any(
        (parent.vertical, parent.market_type, parent.horizon) != scope
        for parent in parents
    ):
        raise GenomeValidationError("inheritance cannot cross unreviewed scopes")
    by_name: dict[str, list[Gene]] = {}
    for parent in parents:
        for gene in parent.genes:
            by_name.setdefault(gene.name, []).append(gene)
    override_map = dict(overrides or {})
    unknown_overrides = set(override_map) - set(by_name)
    if unknown_overrides:
        raise GenomeValidationError(
            f"inheritance overrides unknown genes: {sorted(unknown_overrides)}"
        )
    genes = []
    for name, candidates in sorted(by_name.items()):
        if name in override_map:
            chosen = override_map[name]
            if chosen.name != name:
                raise GenomeValidationError("inheritance override name mismatch")
            genes.append(chosen)
            continue
        semantic = {str(candidate.to_dict()) for candidate in candidates}
        if len(semantic) != 1:
            raise GenomeValidationError(
                f"inheritance conflict requires explicit override: {name}"
            )
        genes.append(candidates[0])
    all_evidence = tuple(
        sorted(
            {
                *evidence_ids,
                *(item for parent in parents for item in parent.evidence_ids),
                *(parent.genome_id for parent in parents),
            }
        )
    )
    return ForecastGenome.create(
        label=label,
        vertical=scope[0],
        market_type=scope[1],
        horizon=scope[2],
        generation=max(parent.generation for parent in parents) + 1,
        parent_genome_ids=tuple(parent.genome_id for parent in parents),
        genes=tuple(genes),
        created_at=created_at,
        evidence_ids=all_evidence,
    )


__all__ = ["inherit_genome"]
