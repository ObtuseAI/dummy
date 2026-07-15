"""Human-only, unapplied promotion review packets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from dummy.promotion.lifecycle import PromotionState, require_valid_transition
from dummy.world_model.models import digest_json, freeze_json, thaw_json


class PromotionEvidenceRequirement(str, Enum):
    POINT_IN_TIME_CORRECTNESS = "point_in_time_correctness"
    CALIBRATION = "calibration"
    CONTESTED_BRIER = "contested_brier"
    LOG_LOSS = "log_loss"
    EVENT_CLUSTER_CONFIDENCE = "event_cluster_confidence"
    HELD_OUT_WALK_FORWARD = "held_out_walk_forward"
    MARKET_PRIOR_COMPARISON = "market_prior_comparison"
    EXECUTION_REALISM = "execution_realism"
    FILL_CONDITIONED_OUTCOMES = "fill_conditioned_outcomes"
    DRAWDOWN = "drawdown"
    REGIME_ROBUSTNESS = "regime_robustness"
    MODEL_INDEPENDENCE = "model_independence"
    REPLAY_DETERMINISM = "replay_determinism"


@dataclass(frozen=True, slots=True)
class PromotionReviewPacket:
    packet_id: str
    component_id: str
    current_state: PromotionState
    requested_state: PromotionState
    claim_program_id: str
    evidence_status: Mapping[str, bool]
    blockers: tuple[str, ...]
    transition_eligible: bool
    human_review_required: bool = True
    human_review_requested: bool = False
    automatic_promotion: bool = False
    applied: bool = False

    def __post_init__(self) -> None:
        if not self.component_id.strip() or len(self.claim_program_id) != 64:
            raise ValueError("promotion review requires component and claim identities")
        require_valid_transition(self.current_state, self.requested_state)
        status = freeze_json(self.evidence_status)
        if set(status) != {item.value for item in PromotionEvidenceRequirement}:
            raise ValueError("promotion review evidence status is incomplete")
        blockers = tuple(sorted(str(item).strip() for item in self.blockers))
        all_evidence = all(bool(value) for value in status.values())
        if self.transition_eligible is not all_evidence:
            raise ValueError("promotion transition eligibility must require every evidence field")
        if not all_evidence and not blockers:
            raise ValueError("blocked promotion review requires blockers")
        if self.automatic_promotion or self.applied or not self.human_review_required:
            raise ValueError("promotion review must remain human-only and unapplied")
        object.__setattr__(self, "evidence_status", status)
        object.__setattr__(self, "blockers", blockers)
        if self.packet_id != digest_json(self.semantic_dict()):
            raise ValueError("promotion review packet ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "phase": 8,
            "component_id": self.component_id,
            "current_state": self.current_state.value,
            "requested_state": self.requested_state.value,
            "claim_program_id": self.claim_program_id,
            "evidence_status": thaw_json(self.evidence_status),
            "blockers": list(self.blockers),
            "transition_eligible": self.transition_eligible,
            "human_review_required": True,
            "human_review_requested": self.human_review_requested,
            "automatic_promotion": False,
            "promotion_authority": "HUMAN_ONLY",
            "applied": False,
            "incumbent_modified": False,
            "execution_authority": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"packet_id": self.packet_id, **self.semantic_dict()}


def build_promotion_review(claim_program: Mapping[str, Any]) -> PromotionReviewPacket:
    reviews = list(claim_program.get("reviews", []))
    review_by_code = {
        str(item["definition"]["code"]): item
        for item in reviews
        if isinstance(item, Mapping)
    }
    performance_supported = {
        code: review_by_code.get(code, {}).get("verdict") == "SUPPORTED"
        for code in (
            "claim_1_organism_outperformance",
            "claim_2_abstention_value",
            "claim_3_resource_efficiency",
            "claim_4_world_model_transfer",
            "claim_5_evolution_held_out_improvement",
            "claim_6_contested_clustered_performance",
        )
    }
    replay_supported = all(
        review_by_code.get(code, {}).get("verdict")
        in {"SUPPORTED", "SUPPORTED_GOVERNANCE_ONLY"}
        for code in (
            "claim_7_execution_truth_separation",
            "claim_8_governance_preservation",
        )
    )
    status = {item.value: False for item in PromotionEvidenceRequirement}
    status[PromotionEvidenceRequirement.REPLAY_DETERMINISM.value] = replay_supported
    blockers = [
        f"claim_not_supported:{code}"
        for code, supported in performance_supported.items()
        if not supported
    ]
    blockers.extend(
        f"promotion_evidence_missing:{name}"
        for name, satisfied in status.items()
        if not satisfied
    )
    semantic = {
        "schema_version": 1,
        "phase": 8,
        "component_id": "dummy-vnext-aggregate",
        "current_state": PromotionState.SHADOW_ONLY.value,
        "requested_state": PromotionState.REPLAY_VALIDATED.value,
        "claim_program_id": str(claim_program["program_id"]),
        "evidence_status": status,
        "blockers": sorted(blockers),
        "transition_eligible": all(status.values()),
        "human_review_required": True,
        "human_review_requested": False,
        "automatic_promotion": False,
        "promotion_authority": "HUMAN_ONLY",
        "applied": False,
        "incumbent_modified": False,
        "execution_authority": False,
    }
    return PromotionReviewPacket(
        packet_id=digest_json(semantic),
        component_id="dummy-vnext-aggregate",
        current_state=PromotionState.SHADOW_ONLY,
        requested_state=PromotionState.REPLAY_VALIDATED,
        claim_program_id=str(claim_program["program_id"]),
        evidence_status=status,
        blockers=tuple(blockers),
        transition_eligible=all(status.values()),
    )


__all__ = [
    "PromotionEvidenceRequirement",
    "PromotionReviewPacket",
    "build_promotion_review",
]
