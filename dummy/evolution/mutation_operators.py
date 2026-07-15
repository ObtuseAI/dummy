"""Deterministic bounded operators that generate mutation proposals, not edits."""

from __future__ import annotations

import math

from dummy.genome import (
    ForecastGenome,
    GenomeValidationError,
    MutationOperation,
    MutationOperator,
)


def bounded_numeric_operations(
    base: ForecastGenome,
    *,
    gene_name: str,
    deltas: tuple[float, ...],
    minimum: float,
    maximum: float,
    version_prefix: str,
    rationale: str,
) -> tuple[MutationOperation, ...]:
    genes = {item.name: item for item in base.genes}
    if gene_name not in genes:
        raise GenomeValidationError(f"unknown numeric gene: {gene_name}")
    gene = genes[gene_name]
    if isinstance(gene.value, bool) or not isinstance(gene.value, (int, float)):
        raise GenomeValidationError("bounded numeric operator requires a numeric gene")
    if not deltas or not minimum <= float(gene.value) <= maximum:
        raise GenomeValidationError("numeric mutation bounds are invalid")
    operations = []
    for index, delta in enumerate(sorted(set(float(item) for item in deltas))):
        if not math.isfinite(delta):
            raise GenomeValidationError("numeric mutation delta must be finite")
        value = min(maximum, max(minimum, float(gene.value) + delta))
        if math.isclose(value, float(gene.value), abs_tol=1e-15):
            continue
        operations.append(
            MutationOperation(
                operator=MutationOperator.SET,
                gene_name=gene.name,
                category=gene.category,
                value=round(value, 12),
                gene_version=f"{version_prefix}.{index + 1}",
                rationale=rationale,
            )
        )
    return tuple(operations)


__all__ = ["bounded_numeric_operations"]
