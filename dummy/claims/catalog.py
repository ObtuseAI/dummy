"""The eight required internal claims and their non-negotiable evidence."""

from __future__ import annotations

from dummy.claims.schema import ClaimCode, ClaimDefinition, EvidenceRequirement as R


CLAIM_DEFINITIONS = (
    ClaimDefinition(
        ClaimCode.ORGANISM_OUTPERFORMANCE,
        "Dynamic forecast organisms outperform fixed orchestration.",
        (
            R.POINT_IN_TIME_HELD_OUT,
            R.MARKET_PRIOR_COMPARISON,
            R.EVENT_CLUSTER_UNCERTAINTY,
            R.CALIBRATION,
            R.DETERMINISTIC_REPLAY,
        ),
        True,
        20,
    ),
    ClaimDefinition(
        ClaimCode.ABSTENTION_VALUE,
        "Metacognitive abstention improves cumulative calibration and decision quality.",
        (
            R.POINT_IN_TIME_HELD_OUT,
            R.ABSTENTION_COMPARATOR,
            R.EVENT_CLUSTER_UNCERTAINTY,
            R.CALIBRATION,
            R.DETERMINISTIC_REPLAY,
        ),
        True,
        20,
    ),
    ClaimDefinition(
        ClaimCode.RESOURCE_EFFICIENCY,
        "Resource-aware analysis reduces cost without reducing forecast quality.",
        (
            R.POINT_IN_TIME_HELD_OUT,
            R.RESOURCE_COST,
            R.QUALITY_NONINFERIORITY,
            R.EVENT_CLUSTER_UNCERTAINTY,
        ),
        True,
        20,
    ),
    ClaimDefinition(
        ClaimCode.WORLD_MODEL_TRANSFER,
        "World-model context improves transfer across market regimes.",
        (
            R.POINT_IN_TIME_HELD_OUT,
            R.TRANSFER,
            R.MARKET_PRIOR_COMPARISON,
            R.EVENT_CLUSTER_UNCERTAINTY,
            R.CALIBRATION,
        ),
        True,
        20,
    ),
    ClaimDefinition(
        ClaimCode.EVOLUTION_HELD_OUT_IMPROVEMENT,
        "Recursive evolution produces held-out improvement, not merely backtest improvement.",
        (
            R.POINT_IN_TIME_HELD_OUT,
            R.TRANSFER,
            R.MULTIPLE_TESTING_CORRECTION,
            R.EVENT_CLUSTER_UNCERTAINTY,
            R.FORWARD_PAPER,
            R.DETERMINISTIC_REPLAY,
        ),
        True,
        20,
    ),
    ClaimDefinition(
        ClaimCode.CONTESTED_CLUSTERED_PERFORMANCE,
        "Contested-market performance remains positive after cluster correction.",
        (
            R.POINT_IN_TIME_HELD_OUT,
            R.CONTESTED_FILTER,
            R.EVENT_CLUSTER_UNCERTAINTY,
            R.MARKET_PRIOR_COMPARISON,
            R.MULTIPLE_TESTING_CORRECTION,
        ),
        True,
        20,
    ),
    ClaimDefinition(
        ClaimCode.EXECUTION_TRUTH_SEPARATION,
        "Execution-aware evidence remains distinct from forecast accuracy.",
        (
            R.FILL_TRUTH_SEPARATION,
            R.EXECUTION_REALISM,
            R.DETERMINISTIC_REPLAY,
        ),
        False,
        0,
    ),
    ClaimDefinition(
        ClaimCode.GOVERNANCE_PRESERVATION,
        "All improvements preserve fail-closed authority boundaries.",
        (
            R.GOVERNANCE_TESTS,
            R.AUTHORITY_NONEXPANSION,
            R.CREDENTIAL_ISOLATION,
            R.DETERMINISTIC_REPLAY,
        ),
        False,
        0,
    ),
)


__all__ = ["CLAIM_DEFINITIONS"]
