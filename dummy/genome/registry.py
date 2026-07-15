"""In-memory genome registry with strict lineage and scope validation."""

from __future__ import annotations

from .schema import ForecastGenome, GenomeValidationError


class GenomeRegistry:
    def __init__(self) -> None:
        self._genomes: dict[str, ForecastGenome] = {}

    def register(self, genome: ForecastGenome) -> str:
        existing = self._genomes.get(genome.genome_id)
        if existing is not None:
            if existing != genome:
                raise GenomeValidationError("genome ID collision has different content")
            return genome.genome_id
        parents = tuple(
            self._genomes.get(parent_id) for parent_id in genome.parent_genome_ids
        )
        if any(parent is None for parent in parents):
            raise GenomeValidationError("genome lineage references an unknown parent")
        if parents:
            known_parents = tuple(parent for parent in parents if parent is not None)
            if genome.generation != max(parent.generation for parent in known_parents) + 1:
                raise GenomeValidationError("genome generation does not follow its parents")
            if any(
                (parent.vertical, parent.market_type, parent.horizon)
                != (genome.vertical, genome.market_type, genome.horizon)
                for parent in known_parents
            ):
                raise GenomeValidationError("genome inheritance crosses an unreviewed scope")
        self._genomes[genome.genome_id] = genome
        return genome.genome_id

    def get(self, genome_id: str) -> ForecastGenome:
        try:
            return self._genomes[genome_id]
        except KeyError as exc:
            raise GenomeValidationError(f"unknown genome_id: {genome_id}") from exc

    def genomes(self) -> tuple[ForecastGenome, ...]:
        return tuple(
            sorted(
                self._genomes.values(),
                key=lambda item: (item.generation, item.genome_id),
            )
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "genome_count": len(self._genomes),
            "genomes": [item.to_dict() for item in self.genomes()],
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }


__all__ = ["GenomeRegistry"]
