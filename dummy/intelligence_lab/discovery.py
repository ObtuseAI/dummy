"""Evidence-grounded opportunity discovery and computational creativity."""

from __future__ import annotations

from collections.abc import Iterable

from .models import (
    CognitiveHypothesis,
    CognitiveOperator,
    ExperimentProtocol,
    GraphKind,
    ResearchOpportunity,
    ScientificObservation,
    make_experiment,
    make_hypothesis,
    make_opportunity,
)


def discover_opportunities(
    observations: Iterable[ScientificObservation],
) -> tuple[ResearchOpportunity, ...]:
    """Turn explicit unknowns/failures into ranked scientific questions."""
    opportunities: list[ResearchOpportunity] = []
    for observation in sorted(observations, key=lambda item: item.observation_id):
        if observation.graph_kind not in {
            GraphKind.UNKNOWN,
            GraphKind.FAILURE,
            GraphKind.OPPORTUNITY,
            GraphKind.PROBLEM,
        }:
            continue
        missing = observation.attributes.get("missing_evidence", ())
        if not isinstance(missing, tuple):
            missing = tuple(missing) if isinstance(missing, list) else ()
        question = f"Which cognitive method most reliably resolves: {observation.statement}"
        opportunities.append(
            make_opportunity(
                domain_id=observation.domain_id,
                question=question,
                importance=float(observation.attributes.get("importance", 0.8)),
                tractability=float(observation.attributes.get("tractability", 0.6)),
                novelty=float(observation.attributes.get("novelty", 0.5)),
                source_observation_ids=(observation.observation_id,),
                missing_evidence=tuple(str(item) for item in missing),
            )
        )
    return tuple(
        sorted(
            opportunities,
            key=lambda item: (
                -(item.importance * item.tractability * (0.5 + item.novelty / 2)),
                item.opportunity_id,
            ),
        )
    )


_OPERATOR_METHODS: dict[CognitiveOperator, tuple[str, str]] = {
    CognitiveOperator.ANALOGY: (
        "transfer the strongest independently validated method from an analogous cohort",
        "the transferred method fails to improve the private metric under equal cost",
    ),
    CognitiveOperator.INVERSION: (
        "optimize identification of failure conditions before selecting a solution",
        "failure-first selection is not more robust than the control",
    ),
    CognitiveOperator.MORPHOLOGICAL_SEARCH: (
        "search a bounded matrix of representation, decomposition, and evaluation choices",
        "the preregistered matrix produces no private survivor",
    ),
    CognitiveOperator.CROSS_DOMAIN_TRANSFER: (
        "test a method validated in a causally distinct experimental domain",
        "the method does not transfer on the external partition",
    ),
    CognitiveOperator.CONSTRAINT_RELAXATION: (
        "relax one nonconstitutional search constraint while holding cost fixed",
        "the relaxed search worsens calibration, stability, or cost efficiency",
    ),
    CognitiveOperator.CONSTRAINT_INVERSION: (
        "treat the dominant constraint as the search objective",
        "constraint-first search is Pareto-dominated by the control",
    ),
    CognitiveOperator.RECOMBINATION: (
        "recombine two noncorrelated cognitive methods on a bounded interface",
        "the combination has no incremental private benefit after complexity cost",
    ),
    CognitiveOperator.COUNTERFACTUAL: (
        "replay the exact problem under a preregistered alternative reasoning sequence",
        "causal replay finds no stable improvement across seeds",
    ),
    CognitiveOperator.FIRST_PRINCIPLES: (
        "reconstruct the method from explicit invariants and measurable primitives",
        "the reconstruction cannot reproduce or exceed the control",
    ),
    CognitiveOperator.ABSTRACTION: (
        "extract the minimal reusable pattern shared by successful cases",
        "the compressed pattern fails held-out transfer or loses the measured effect",
    ),
}


def generate_hypotheses(
    opportunities: Iterable[ResearchOpportunity],
    *,
    operators_per_opportunity: int = 3,
) -> tuple[CognitiveHypothesis, ...]:
    """Apply explicit creativity operators; every output is falsifiable."""
    if operators_per_opportunity < 1:
        raise ValueError("operators_per_opportunity must be positive")
    operators = tuple(CognitiveOperator)
    results: list[CognitiveHypothesis] = []
    for opportunity in opportunities:
        offset = int(opportunity.opportunity_id[:8], 16) % len(operators)
        for index in range(min(operators_per_opportunity, len(operators))):
            operator = operators[(offset + index) % len(operators)]
            method, falsifier = _OPERATOR_METHODS[operator]
            results.append(
                make_hypothesis(
                    domain_id=opportunity.domain_id,
                    opportunity_id=opportunity.opportunity_id,
                    operator=operator,
                    claim=f"Using {method} will improve resolution of the research question.",
                    prediction=(
                        "Under identical point-in-time evidence and compute, the method "
                        "will improve a protected private score without worse calibration."
                    ),
                    falsifier=falsifier,
                    target_metrics=(
                        "fixed_cost_private_score",
                        "calibration_noninferiority",
                        "cross_regime_transfer",
                        "replay_stability",
                        "complexity_adjusted_gain",
                    ),
                )
            )
    return tuple(sorted(results, key=lambda item: item.hypothesis_id))


def design_experiments(
    hypotheses: Iterable[CognitiveHypothesis],
    *,
    compute_budget: float = 1_000.0,
) -> tuple[ExperimentProtocol, ...]:
    return tuple(
        make_experiment(
            hypothesis_id=hypothesis.hypothesis_id,
            domain_id=hypothesis.domain_id,
            intervention=f"preregistered_{hypothesis.operator.value}_cognitive_pipeline",
            control="frozen_current_champion_cognitive_pipeline",
            private_metrics=hypothesis.target_metrics,
            required_partitions=(
                "visible_development",
                "private_selection",
                "external_generalization",
                "forward_validation",
            ),
            compute_budget=compute_budget,
            replication_seed_count=3,
        )
        for hypothesis in hypotheses
    )


__all__ = [
    "design_experiments",
    "discover_opportunities",
    "generate_hypotheses",
]
