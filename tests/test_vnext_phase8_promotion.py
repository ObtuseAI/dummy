from __future__ import annotations

from dataclasses import replace

import pytest

from dummy.promotion import (
    PromotionEvidenceRequirement,
    PromotionState,
    build_promotion_review,
    require_valid_transition,
    transition_allowed,
)
from scripts.run_vnext_phase8_audit import build_outputs


def test_promotion_lifecycle_contains_all_states_and_forbids_skips() -> None:
    assert [item.value for item in PromotionState] == [
        "EXPERIMENTAL",
        "QUARANTINED",
        "SHADOW_ONLY",
        "REPLAY_VALIDATED",
        "FORWARD_PAPER",
        "CONTESTED_VALIDATED",
        "FILL_VALIDATED",
        "CANARY_ELIGIBLE",
        "PROMOTED",
        "DEGRADED",
        "RETIRED",
    ]
    assert transition_allowed(PromotionState.EXPERIMENTAL, PromotionState.SHADOW_ONLY)
    assert transition_allowed(PromotionState.SHADOW_ONLY, PromotionState.REPLAY_VALIDATED)
    assert transition_allowed(PromotionState.PROMOTED, PromotionState.DEGRADED)
    assert not transition_allowed(PromotionState.SHADOW_ONLY, PromotionState.FORWARD_PAPER)
    with pytest.raises(ValueError, match="skip a gate"):
        require_valid_transition(PromotionState.SHADOW_ONLY, PromotionState.FORWARD_PAPER)


def test_current_promotion_review_is_complete_human_only_and_blocked() -> None:
    outputs = build_outputs()
    packet = build_promotion_review(outputs["VNEXT_PHASE8_CLAIM_REVIEW.json"])
    assert packet.current_state is PromotionState.SHADOW_ONLY
    assert packet.requested_state is PromotionState.REPLAY_VALIDATED
    assert set(packet.evidence_status) == {
        item.value for item in PromotionEvidenceRequirement
    }
    assert sum(bool(value) for value in packet.evidence_status.values()) == 1
    assert packet.transition_eligible is False
    assert packet.human_review_required is True
    assert packet.human_review_requested is False
    assert packet.automatic_promotion is False
    assert packet.applied is False
    assert packet.blockers


def test_promotion_packet_rejects_authority_bypass_or_application() -> None:
    outputs = build_outputs()
    packet = build_promotion_review(outputs["VNEXT_PHASE8_CLAIM_REVIEW.json"])
    with pytest.raises(ValueError, match="human-only and unapplied"):
        replace(packet, automatic_promotion=True)
    with pytest.raises(ValueError, match="human-only and unapplied"):
        replace(packet, applied=True)
    with pytest.raises(ValueError, match="human-only and unapplied"):
        replace(packet, human_review_required=False)
