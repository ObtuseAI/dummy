"""DUMMY vNext content-addressed forecast genomes and proposal-only mutation."""

from .catalog import genome_catalog_manifest, pilot_genomes
from .fitness import GenomeFitness
from .inheritance import inherit_genome
from .lineage import lineage_report
from .mutation import (
    GenomeMutationProposal,
    MutationLevel,
    MutationOperation,
    MutationOperator,
    propose_mutation,
)
from .registry import GenomeRegistry
from .retirement import RetirementAction, RetirementRecord
from .schema import (
    ForecastGenome,
    Gene,
    GeneCategory,
    GenomeStatus,
    GenomeValidationError,
)

__all__ = [
    "ForecastGenome",
    "Gene",
    "GeneCategory",
    "GenomeFitness",
    "GenomeMutationProposal",
    "GenomeRegistry",
    "GenomeStatus",
    "GenomeValidationError",
    "MutationLevel",
    "MutationOperation",
    "MutationOperator",
    "RetirementAction",
    "RetirementRecord",
    "inherit_genome",
    "genome_catalog_manifest",
    "lineage_report",
    "pilot_genomes",
    "propose_mutation",
]
