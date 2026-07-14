"""Immutable constitutional invariant registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InvariantCode(str, Enum):
    NO_AUTONOMOUS_CAPITAL_EXPANSION = "no_autonomous_capital_expansion"
    NO_RESEARCH_CREDENTIAL_ACCESS = "no_research_credential_access"
    NO_UNSUPPORTED_SUBMISSION = "no_unsupported_submission"
    NO_MALFORMED_OR_STALE_FORECAST = "no_malformed_or_stale_forecast"
    NO_SYNTHETIC_AS_REALIZED = "no_synthetic_as_realized"
    NO_BACKFILLED_LOOKAHEAD = "no_backfilled_lookahead"
    NO_RETROACTIVE_DECISION_REWRITE = "no_retroactive_decision_rewrite"
    NO_PROTECTED_TRUTH_MUTATION = "no_protected_truth_mutation"
    NO_EXCLUSIVE_SELF_GRADING = "no_exclusive_self_grading"
    NO_CONSENSUS_OVERRIDE = "no_consensus_override"
    NO_MISSING_STATE_GUESS = "no_missing_state_guess"
    NO_FORCED_COVERAGE_PROMOTION = "no_forced_coverage_promotion"
    NO_DUPLICATE_CALIBRATION_GRAIN = "no_duplicate_calibration_grain"
    NO_UNVERIFIED_CAUSAL_TIMESTAMP = "no_unverified_causal_timestamp"


@dataclass(frozen=True, slots=True)
class ConstitutionalInvariant:
    code: InvariantCode
    statement: str
    protected_evidence: str


CONSTITUTIONAL_INVARIANTS = (
    ConstitutionalInvariant(
        InvariantCode.NO_AUTONOMOUS_CAPITAL_EXPANSION,
        "No autonomous component may expand capital authority.",
        "operator authorization and promotion review",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_RESEARCH_CREDENTIAL_ACCESS,
        "Research components may not access broker credentials.",
        "credential isolation",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_UNSUPPORTED_SUBMISSION,
        "No unsupported market or order type may be submitted.",
        "live firewall and market validation",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_MALFORMED_OR_STALE_FORECAST,
        "Malformed or stale evidence must produce abstention, not a forecast.",
        "point-in-time source validation",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_SYNTHETIC_AS_REALIZED,
        "Synthetic, simulated, or counterfactual evidence is never realized evidence.",
        "fill and settlement truth",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_BACKFILLED_LOOKAHEAD,
        "A backfilled feature may not influence an earlier decision.",
        "receipt-time provenance",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_RETROACTIVE_DECISION_REWRITE,
        "Later quotes or outcomes may not rewrite the frozen decision state.",
        "append-only decision truth",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_PROTECTED_TRUTH_MUTATION,
        "Evolution may not mutate fill truth, settlement truth, or promotion rules.",
        "protected-surface manifest",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_EXCLUSIVE_SELF_GRADING,
        "No source, agent, or evolution policy may grade itself exclusively.",
        "independent evaluator",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_CONSENSUS_OVERRIDE,
        "Agent consensus may not override market or settlement evidence.",
        "market prior and contested truth",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_MISSING_STATE_GUESS,
        "Missing live state may not silently degrade into a guess.",
        "fail-closed hydration",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_FORCED_COVERAGE_PROMOTION,
        "Forced-coverage samples may not influence promotion.",
        "evidence-lane isolation",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_DUPLICATE_CALIBRATION_GRAIN,
        "Unresolved duplicate market grains may not enter calibration.",
        "calibration data quality",
    ),
    ConstitutionalInvariant(
        InvariantCode.NO_UNVERIFIED_CAUSAL_TIMESTAMP,
        "Unverified provider timestamps may not enter causal replay.",
        "causal-time provenance",
    ),
)


def invariant_by_code(code: InvariantCode) -> ConstitutionalInvariant:
    """Return one invariant or fail if the registry is incomplete."""

    for invariant in CONSTITUTIONAL_INVARIANTS:
        if invariant.code is code:
            return invariant
    raise KeyError(code)
